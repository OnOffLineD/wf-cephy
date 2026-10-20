import os
import asyncio
from PIL import Image
from scripts.screen_mod_analyzer import ScreenModAnalyzer
from scripts.jamo_matcher import match_mods_jamo, decompose_hangul

analyzer = ScreenModAnalyzer()

test_files = [
    "1792128102.jpg", # Sancti Magistar
    "1792128109.jpg", # Sibear
    "1792128122.jpg", # Arca Titron
    "1792128165.jpg", # Ruvox
]

for fname in test_files:
    p = os.path.join("ocrTestImg", fname)
    img = Image.open(p)
    w, h = img.size
    y_max = int(h * 0.90) if (w / h > 2.0) else int(h * 0.52)
    crop = img.crop((int(w * 0.28), int(h * 0.05), int(w * 0.98), y_max))
    txt = analyzer.ocr_image(crop)
    print(f"=== {fname} EQUIPPED OCR TEXT ===")
    for line in txt.splitlines():
        if line.strip():
            print("  ", line.strip())
    
    # Check jamo match
    diag = analyzer.diagnose_screenshot(p)
    print(f"Detected mods ({len(diag['detected_mods'])}): {diag['detected_mods']}\n")
