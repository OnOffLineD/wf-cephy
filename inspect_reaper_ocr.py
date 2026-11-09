import os
import sys
from PIL import Image
from scripts.screen_mod_analyzer import ScreenModAnalyzer

analyzer = ScreenModAnalyzer()
p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "ocrTestImg", "1792128122.jpg")
if not os.path.isfile(p):
    print(f"[NOTICE] Image not found: {p}")
    print("Usage: python inspect_reaper_ocr.py <image_path>")
    sys.exit(0)
img = Image.open(p)
w, h = img.size
y_max = int(h * 0.90) if (w / h > 2.0) else int(h * 0.52)
crop = img.crop((int(w * 0.28), int(h * 0.05), int(w * 0.98), y_max))

txt = analyzer.ocr_image(crop)
print("=== REAPER PRIME EQUIPPED CROP OCR ===")
for line in txt.splitlines():
    print("  ", line)
