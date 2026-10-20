import os
from PIL import Image

img_dir = "ocrTestImg"
for f in sorted(os.listdir(img_dir)):
    if f.lower().endswith(('.png', '.jpg', '.jpeg')):
        p = os.path.join(img_dir, f)
        im = Image.open(p)
        print(f"{f}: size={im.size}, aspect={im.width/im.height:.2f}")
