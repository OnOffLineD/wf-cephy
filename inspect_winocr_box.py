import asyncio
import winocr
from PIL import Image

async def test_boxes():
    img = Image.open("ocrTestImg/1792128102.jpg")
    res = await winocr.recognize_pil(img, lang="ko")
    print(f"Total lines: {len(res.lines)}")
    for l in res.lines[:15]:
        print(f"Text: '{l.text}' | Box: {getattr(l, 'bounding_rect', None) or getattr(l, 'words', None)}")
        if hasattr(l, 'words'):
            for w in l.words[:2]:
                print(f"   Word: '{w.text}', rect: {getattr(w, 'bounding_rect', None)}")

asyncio.run(test_boxes())
