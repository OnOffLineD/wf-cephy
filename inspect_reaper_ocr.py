from PIL import Image
from scripts.screen_mod_analyzer import ScreenModAnalyzer

analyzer = ScreenModAnalyzer()
p = r"C:/Users/2doo2/.gemini/antigravity/brain/4a973225-cdb1-4064-b5f5-3904f03c0087/.user_uploaded/media_1792137178605_e8bee2af.jpg"
img = Image.open(p)
w, h = img.size
y_max = int(h * 0.90) if (w / h > 2.0) else int(h * 0.52)
crop = img.crop((int(w * 0.28), int(h * 0.05), int(w * 0.98), y_max))

txt = analyzer.ocr_image(crop)
print("=== REAPER PRIME EQUIPPED CROP OCR ===")
for line in txt.splitlines():
    print("  ", line)
