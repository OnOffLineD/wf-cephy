import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from PIL import Image

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

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

class YOLOSlotDetector:
    """
    Warframe UI 객체 탐지용 YOLOv8-nano 추론 및 기하학적 슬롯 분류기
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.is_loaded = False
        
        if YOLO is None:
            return

        if model_path is None:
            candidates = [
                Path(PathConfig.MODELS_DIR) / "slot_detector.pt",
                Path(PathConfig.ROOT_DIR) / "warframe_bot_runs" / "slot_detector" / "weights" / "best.pt",
                Path(PathConfig.ROOT_DIR) / "labeling" / "best.pt"
            ]
            for cand in candidates:
                if cand.exists():
                    model_path = str(cand)
                    break

        if model_path and Path(model_path).exists():
            try:
                self.model = YOLO(str(model_path))
                self.is_loaded = True
            except Exception as e:
                print(f"[YOLOSlotDetector] 모델 로드 실패: {e}")
                self.model = None
                self.is_loaded = False

    def is_available(self) -> bool:
        return self.is_loaded and self.model is not None

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
            # 직사각형 가로 비율 유지 추론 (1280px)
            results = self.model.predict(
                source=img,
                imgsz=1280,
                rect=True,
                conf=conf_threshold,
                verbose=False
            )[0]

            detected_boxes = []
            for box in results.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                cx, cy, bw, bh = box.xywhn[0].tolist()

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