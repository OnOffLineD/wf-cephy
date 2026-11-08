import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np
import cv2
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:
    ort = None

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.path_config import PathConfig

CLASS_NAMES = {
    0: "mod_slot",
    1: "empty_slot",
    2: "name_header",
    3: "arcane_slot",
    4: "riven_slot"
}

INPUT_SIZE = 640
TILE_SCALE_SIDE = 1280  # 기존 .pt 추론(imgsz=1280) 해상도를 640 타일로 재현
IOU_THRESHOLD = 0.7


def decode_output(output, conf_threshold, sx=1.0, sy=1.0, ox=0.0, oy=0.0, edges=(False,) * 4) -> List[tuple]:
    """(1, 4+nc, N) 출력 -> [(cls_id, conf, x1, y1, x2, y2)]. 원본 좌표 = 모델 좌표 * (sx, sy) + (ox, oy).
    edges=(좌, 상, 우, 하)가 True인 타일 내부 경계에 닿아 잘린 박스는 버린다 (인접 타일이 온전히 탐지)."""
    preds = np.asarray(output, dtype=np.float32)[0].T  # (N, 4+nc)
    cls_ids = preds[:, 4:].argmax(axis=1)
    confs = preds[np.arange(len(preds)), 4 + cls_ids]
    m, out = 16.0, []  # 잘린 박스는 경계 안쪽으로 약간 수축되어 예측되므로 여유를 둔다
    for i in np.flatnonzero(confs >= conf_threshold):
        cx, cy, bw, bh = preds[i, :4].tolist()
        x1, y1, x2, y2 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2
        cut = (edges[0] and x1 < m, edges[1] and y1 < m,
               edges[2] and x2 > INPUT_SIZE - m, edges[3] and y2 > INPUT_SIZE - m)
        if not any(cut):
            out.append((int(cls_ids[i]), float(confs[i]), x1 * sx + ox, y1 * sy + oy, x2 * sx + ox, y2 * sy + oy))
    return out


def nms(dets: List[tuple], img_w: int, img_h: int, iou_threshold: float = IOU_THRESHOLD) -> List[tuple]:
    """박스를 이미지 안으로 자른 뒤 클래스별 NMS (클래스마다 좌표 오프셋 부여). 신뢰도 내림차순 반환."""
    dets = [(c, cf, min(max(a, 0), img_w), min(max(b, 0), img_h), min(max(x, 0), img_w), min(max(y, 0), img_h))
            for c, cf, a, b, x, y in dets]
    off = max(img_w, img_h) + 1
    boxes = [[a + c * off, b + c * off, x - a, y - b] for c, _, a, b, x, y in dets]
    idxs = cv2.dnn.NMSBoxes(boxes, [d[1] for d in dets], 0.0, iou_threshold) if dets else []
    return sorted((dets[i] for i in np.array(idxs).reshape(-1)), key=lambda d: -d[1])


def _starts(length: int) -> List[int]:
    """길이 length 축을 겹침 >= 절반인 640 창으로 덮는 시작 좌표들."""
    if length <= INPUT_SIZE:
        return [0]
    n = int(np.ceil((length - INPUT_SIZE) / (INPUT_SIZE / 2))) + 1
    return [round(i * (length - INPUT_SIZE) / (n - 1)) for i in range(n)]


class YOLOSlotDetector:
    """
    Warframe UI 객체 탐지용 YOLOv8-nano(ONNX/onnxruntime) 추론 및 기하학적 슬롯 분류기
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.is_loaded = False

        if ort is None:
            return

        if model_path is None:
            candidates = [
                Path(PathConfig.MODELS_DIR) / "slot_detector.onnx",
            ]
            for cand in candidates:
                if cand.exists():
                    model_path = str(cand)
                    break

        if model_path and Path(model_path).exists():
            try:
                self.model = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
                self.input_name = self.model.get_inputs()[0].name
                self.is_loaded = True
            except Exception as e:
                print(f"[YOLOSlotDetector] 모델 로드 실패: {e}")
                self.model = None
                self.is_loaded = False

    def is_available(self) -> bool:
        return self.is_loaded and self.model is not None

    def _run(self, tile: np.ndarray) -> np.ndarray:
        blob = (tile.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]  # NCHW, [0, 1]
        return self.model.run(None, {self.input_name: blob})[0]

    def _infer(self, arr: np.ndarray, conf: float) -> List[tuple]:
        h, w = arr.shape[:2]
        # 1) 전체 화면 640x640 1회: 이름 헤더처럼 타일보다 큰 객체 담당
        full = cv2.resize(arr, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
        dets = decode_output(self._run(full), conf, w / INPUT_SIZE, h / INPUT_SIZE)
        # 2) 종횡비 유지, 장변 1280 스케일에서 640 타일 슬라이딩 (부족분은 114 패딩)
        s = TILE_SCALE_SIDE / max(w, h)
        big = cv2.resize(arr, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_LINEAR)
        big = cv2.copyMakeBorder(big, 0, max(0, INPUT_SIZE - big.shape[0]), 0, max(0, INPUT_SIZE - big.shape[1]),
                                 cv2.BORDER_CONSTANT, value=(114, 114, 114))
        bh, bw = big.shape[:2]
        for y0 in _starts(bh):
            for x0 in _starts(bw):
                out = self._run(big[y0:y0 + INPUT_SIZE, x0:x0 + INPUT_SIZE])
                edges = (x0 > 0, y0 > 0, x0 + INPUT_SIZE < bw, y0 + INPUT_SIZE < bh)
                dets += decode_output(out, conf, 1 / s, 1 / s, x0 / s, y0 / s, edges)
        return nms(dets, w, h)

    def detect_layout(self, img, conf_threshold: float = 0.4) -> Dict[str, Any]:
            """
            입력 이미지를 받아 UI 슬롯 및 헤더를 탐지하고 기하학적으로 분류된 딕셔너리를 반환합니다.
            """
            if not self.is_available():
                raise RuntimeError("YOLO 모델이 로드되지 않았습니다.")

            if isinstance(img, str):
                img = Image.open(img).convert("RGB")
            elif hasattr(img, "convert"):
                img = img.convert("RGB")

            orig_w, orig_h = img.size
            detected_boxes = []
            for cls_id, conf, fx1, fy1, fx2, fy2 in self._infer(np.asarray(img, dtype=np.uint8), conf_threshold):
                x1, y1, x2, y2 = int(fx1), int(fy1), int(fx2), int(fy2)
                cx, cy = (fx1 + fx2) / 2 / orig_w, (fy1 + fy2) / 2 / orig_h
                bw, bh = (fx2 - fx1) / orig_w, (fy2 - fy1) / orig_h

                # 경계 보호
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(orig_w, x2), min(orig_h, y2)

                detected_boxes.append({
                    "cls_id": cls_id,
                    "cls_name": CLASS_NAMES.get(cls_id, f"cls_{cls_id}"),
                    "conf": conf,
                    "box": (x1, y1, x2, y2),
                    "cx": cx,
                    "cy": cy,
                    "bw": bw,
                    "bh": bh,
                    "is_empty": (cls_id == 1),
                    "is_riven": (cls_id == 4)
                })

            # 1. 헤더 (cls 2)
            name_headers = [b for b in detected_boxes if b["cls_id"] == 2]
            name_header_box = name_headers[0]["box"] if name_headers else None

            # 2. 아케인 슬롯 (cls 3)
            arcanes = sorted([b for b in detected_boxes if b["cls_id"] == 3], key=lambda b: b["cy"])

            # 3. 모드 슬롯들 (cls 0: 장착, cls 1: 빈 슬롯, cls 4: 리벤 슬롯)
            slots = [b for b in detected_boxes if b["cls_id"] in (0, 1, 4)]
            special_slots, main_slots, equipped_count = self._classify_slots(slots, arcanes)

            return {
                "name_header_box": name_header_box,
                "special_slots": special_slots,
                "main_slots": main_slots,
                "arcane_slots": arcanes,
                "total_detected": len(detected_boxes),
                "equipped_slot_count": equipped_count
            }

    def _classify_slots(self, slots: List[Dict[str, Any]], arcanes: List[Dict[str, Any]]) -> Any:
        special_slots = {'AuraStance': None, 'Exilus': None}
        main_slots = {}
    
        if not slots:
            return special_slots, main_slots, 0
    
        s_max = max(slots, key=lambda x: x['cx'])
        sorted_cx = sorted([x['cx'] for x in slots])
    
        if (arcanes and abs(s_max['cx'] - arcanes[0]['cx']) < 0.08) or (len(slots) >= 5 and s_max['cx'] > 0.78 and (s_max['cx'] - sorted_cx[-2]) > 0.07):
            special_slots['Exilus'] = s_max
            grid_slots = [s for s in slots if s is not s_max]
        else:
            grid_slots = list(slots)
    
        grid_slots.sort(key=lambda x: x['cy'])
        med_bh = sorted([s['bh'] for s in grid_slots])[len(grid_slots) // 2] if grid_slots else 0.12
    
        rows = []
        for s in grid_slots:
            if not rows or (s['cy'] - rows[-1][0]['cy']) > 0.65 * med_bh:
                rows.append([s])
            else:
                rows[-1].append(s)
    
        for r in rows:
            r.sort(key=lambda x: x['cx'])
    
        if len(rows) >= 2 and len(rows[0]) <= 2 and len(rows[1]) >= 3:
            for s in rows[0]:
                if s['cx'] < 0.56 and special_slots['AuraStance'] is None:
                    special_slots['AuraStance'] = s
                elif special_slots['Exilus'] is None:
                    special_slots['Exilus'] = s
            main_rows = rows[1:]
        else:
            main_rows = rows
    
        r1 = main_rows[0][:4] if len(main_rows) >= 1 else []
        r2 = main_rows[1][:4] if (len(main_rows) >= 2 and (main_rows[1][0]['cy'] - main_rows[0][0]['cy']) < 1.65 * med_bh) else []
    
        for i, s in enumerate(r1, 1):
            main_slots[f'R1_C{i}'] = s
        for i, s in enumerate(r2, 1):
            main_slots[f'R2_C{i}'] = s
    
        equipped = sum(1 for s in list(main_slots.values()) + [v for v in special_slots.values() if v is not None] if not s.get('is_empty', False))
    
        return special_slots, main_slots, equipped

if __name__ == "__main__":
    detector = YOLOSlotDetector()
    print(f"YOLOSlotDetector Available: {detector.is_available()}")
    test_p = Path("labeling/warframemode/20260829011436_1.jpg")
    if test_p.exists() and detector.is_available():
        res = detector.detect_layout(Image.open(test_p))
        print(f"Name header box: {res['name_header_box']}")
        print(f"Special slots: {list(res['special_slots'].keys())}")
        print(f"Main slots: {list(res['main_slots'].keys())}")
        print(f"Equipped count: {res['equipped_slot_count']}")