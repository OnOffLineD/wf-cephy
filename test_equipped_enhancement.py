import asyncio
import winocr
from PIL import Image, ImageEnhance, ImageOps

async def test_enhance():
    img = Image.open("ocrTestImg/1792128102.jpg")
    w, h = img.size
    
    # Equipped region
    equipped = img.crop((int(w * 0.28), int(h * 0.12), int(w * 0.98), int(h * 0.55)))
    
    # 1. Base 3x upscale
    up3 = equipped.resize((equipped.width * 3, equipped.height * 3), Image.Resampling.LANCZOS)
    
    # 2. Contrast enhanced
    enhancer = ImageEnhance.Contrast(up3)
    contrast_img = enhancer.enhance(1.5)
    
    # 3. Grayscale autocontrast
    gray_img = ImageOps.autocontrast(up3.convert("L"))
    
    for name, target in [("3x RGB", up3), ("3x Contrast", contrast_img), ("3x Gray Autocontrast", gray_img)]:
        res = await winocr.recognize_pil(target, lang="ko")
        lines = [l.text for l in res.lines]
        print(f"\n--- {name} (lines={len(lines)}) ---")
        for line in lines:
            print("  ", line)

asyncio.run(test_enhance())
