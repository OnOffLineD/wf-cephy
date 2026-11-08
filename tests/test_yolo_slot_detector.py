import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scripts.yolo_slot_detector import YOLOSlotDetector, decode_output, nms, _starts

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT_DIR / "models" / "slot_detector.onnx"
EXPECTED_KEYS = {"name_header_box", "special_slots", "main_slots", "arcane_slots",
                 "total_detected", "equipped_slot_count"}
# 1280x640 원본: 전체 패스 배율 (sx=2, sy=1), 타일 패스 배율 1 -> 창 x0 = 0, 320, 640 (y0 = 0)
IMG_W, IMG_H = 1280, 640


def _make_output(dets):
    """dets: [(cls_id, conf, (x1, y1, x2, y2) 모델 좌표)] -> (1, 9, 8400) 텐서."""
    out = np.zeros((1, 9, 8400), dtype=np.float32)
    for i, (cls_id, conf, (x1, y1, x2, y2)) in enumerate(dets):
        out[0, 0:4, i] = [(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1]
        out[0, 4 + cls_id, i] = conf
    return out


def _full_pass(dets):
    """원본 좌표 박스를 전체 화면(640x640 리사이즈) 패스의 모델 좌표로 변환."""
    return _make_output([(c, cf, (x1 / 2, y1, x2 / 2, y2)) for c, cf, (x1, y1, x2, y2) in dets])


class _FakeSession:
    def __init__(self, outputs):
        self.outputs, self.feeds = outputs, []

    def run(self, _names, feed):
        self.feeds.append(feed["images"])
        return [self.outputs.get(len(self.feeds) - 1, np.zeros((1, 9, 8400), dtype=np.float32))]


def _detector_with(outputs):
    det = YOLOSlotDetector(model_path=str(ROOT_DIR / "nonexistent.onnx"))
    det.model, det.input_name, det.is_loaded = _FakeSession(outputs), "images", True
    return det


def _layout_dets():
    dets = [(2, 0.95, (50, 20, 500, 70)), (3, 0.90, (1150, 100, 1250, 220))]  # 헤더, 아케인
    for row_y in (100, 240):
        for x in (100, 350, 600, 850):
            dets.append((1 if (row_y, x) == (240, 850) else 0, 0.88, (x, row_y, x + 200, row_y + 120)))
    return dets + [(0, 0.60, (102, 101, 301, 221))]  # NMS로 제거될 R1_C1 중복


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="models/slot_detector.onnx 없음")
def test_is_available_with_onnx_model():
    det = YOLOSlotDetector()
    assert det.is_available() is True
    assert type(det.model).__module__.startswith("onnxruntime")


def test_is_available_false_when_model_missing():
    det = YOLOSlotDetector(model_path=str(ROOT_DIR / "nonexistent.onnx"))
    assert det.is_available() is False
    with pytest.raises(RuntimeError):
        det.detect_layout(Image.new("RGB", (64, 64)))


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="models/slot_detector.onnx 없음")
def test_real_inference_without_torch_in_subprocess():
    code = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from PIL import Image\n"
        "from scripts.yolo_slot_detector import YOLOSlotDetector\n"
        "d = YOLOSlotDetector(); assert d.is_available()\n"
        "r = d.detect_layout(Image.new('RGB', (1280, 720), (20, 20, 20)))\n"
        "assert set(r) == %r, r.keys()\n"
        "assert 'torch' not in sys.modules and 'ultralytics' not in sys.modules\n"
        "print('OK')\n" % (str(ROOT_DIR), EXPECTED_KEYS)
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=180)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("OK")


def test_starts_cover_axis_with_half_overlap():
    assert (_starts(500), _starts(640), _starts(720), _starts(1280)) == ([0], [0], [0, 80], [0, 320, 640])


def test_decode_output_threshold_mapping_and_edge_cut():
    out = _make_output([(0, 0.9, (100, 100, 300, 220)),
                        (2, 0.2, (100, 300, 200, 400)),   # 임계값 미만
                        (1, 0.8, (500, 100, 639, 200))])  # 오른쪽 경계에 닿아 잘린 박스
    assert decode_output(out, 0.4, 2, 1, 10, 0) == [(0, pytest.approx(0.9), 210, 100, 610, 220),
                                                    (1, pytest.approx(0.8), 1010, 100, 1288, 200)]
    cut = decode_output(out, 0.4, edges=(False, False, True, False))
    assert [d[0] for d in cut] == [0]


def test_nms_classwise_and_clip():
    dets = [(0, 0.5, 105, 102, 302, 222), (0, 0.9, 100, 100, 300, 220),
            (1, 0.7, 105, 102, 302, 222), (2, 0.8, -50, -30, 2000, 100)]
    res = nms(dets, IMG_W, IMG_H)
    assert [(d[0], d[1]) for d in res] == [(0, 0.9), (2, 0.8), (1, 0.7)]
    assert res[1][2:] == (0, 0, IMG_W, 100)


def test_detect_layout_returns_classified_dict():
    det = _detector_with({0: _full_pass(_layout_dets())})
    res = det.detect_layout(Image.new("RGB", (IMG_W, IMG_H)))

    feeds = det.model.feeds
    assert len(feeds) == 4  # 전체 1회 + 타일 3회
    assert all(f.shape == (1, 3, 640, 640) and f.dtype == np.float32 for f in feeds)
    assert set(res) == EXPECTED_KEYS
    assert res["total_detected"] == 10
    assert res["name_header_box"] == (50, 20, 500, 70)
    assert len(res["arcane_slots"]) == 1 and res["arcane_slots"][0]["cls_name"] == "arcane_slot"
    assert res["special_slots"] == {"AuraStance": None, "Exilus": None}
    assert list(res["main_slots"]) == [f"R{r}_C{c}" for r in (1, 2) for c in range(1, 5)]
    assert res["main_slots"]["R1_C1"]["box"] == (100, 100, 300, 220)
    assert res["main_slots"]["R2_C4"]["is_empty"] is True
    assert res["equipped_slot_count"] == 7

    s = res["main_slots"]["R1_C2"]
    assert set(s) == {"cls_id", "cls_name", "conf", "box", "cx", "cy", "bw", "bh", "is_empty", "is_riven"}
    assert (s["cx"], s["cy"]) == (pytest.approx(450 / IMG_W), pytest.approx(160 / IMG_H))
    assert (s["bw"], s["bh"]) == (pytest.approx(200 / IMG_W), pytest.approx(120 / IMG_H))


def test_detect_layout_merges_tiles_and_drops_cut_boxes():
    tile = _make_output([(4, 0.9, (100, 100, 300, 220)), (0, 0.9, (560, 300, 640, 400))])
    det = _detector_with({1: tile, 2: tile, 3: tile})
    res = det.detect_layout(Image.new("RGB", (IMG_W, IMG_H)))
    boxes = sorted(s["box"] for s in res["main_slots"].values())
    # 창별 리벤 슬롯 3개 + 마지막 창(이미지 오른쪽 끝)의 박스만 유지, 내부 경계에서 잘린 박스는 제거
    assert boxes == [(100, 100, 300, 220), (420, 100, 620, 220), (740, 100, 940, 220), (1200, 300, 1280, 400)]
    assert res["total_detected"] == 4


def test_detect_layout_empty_output():
    res = _detector_with({}).detect_layout(Image.new("RGB", (IMG_W, IMG_H)))
    assert res == {"name_header_box": None, "special_slots": {"AuraStance": None, "Exilus": None},
                   "main_slots": {}, "arcane_slots": [], "total_detected": 0, "equipped_slot_count": 0}
