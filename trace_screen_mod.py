import sys
from PIL import Image
from scripts.screen_mod_analyzer import ScreenModAnalyzer

print("[1] Initializing ScreenModAnalyzer...", flush=True)
analyzer = ScreenModAnalyzer()
print("[2] Analyzer initialized.", flush=True)

img_path = "ocrTestImg/1792128102.jpg"
img = Image.open(img_path)
print(f"[3] Image opened: {img.size}", flush=True)

print("[4] Testing single ocr_image on header...", flush=True)
header = img.crop((0, 0, int(img.width * 0.65), int(img.height * 0.22)))
txt = analyzer.ocr_image(header)
print(f"[5] Header OCR done: {txt[:30]}", flush=True)

print("[6] Testing crop_and_ocr_mod_slots...", flush=True)
res_slots = analyzer.crop_and_ocr_mod_slots(img)
print(f"[7] crop_and_ocr_mod_slots done: {res_slots}", flush=True)

print("[8] Testing extract_left_panel_stats...", flush=True)
stats = analyzer.extract_left_panel_stats(img)
print(f"[9] Left panel stats done: {stats}", flush=True)

print("[10] Testing diagnose_screenshot...", flush=True)
diag = analyzer.diagnose_screenshot(img_path)
print(f"[11] diagnose_screenshot done! Weapon={diag.get('weapon')}", flush=True)
