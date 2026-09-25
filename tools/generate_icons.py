import cv2
import numpy as np
from PIL import Image

# 1. Read original source image
img = cv2.imread('icon.png')
h, w = img.shape[:2]

# 2. Create floodFill dedicated mask (+2 pixels padding in height and width)
mask = np.zeros((h + 2, w + 2), np.uint8)

# 3. Detect background white spreading inward from four corners (tolerance 18 for antialiasing noise)
floodflags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY
for pt in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
    cv2.floodFill(img, mask, pt, (0, 0, 0), loDiff=(18, 18, 18), upDiff=(18, 18, 18), flags=floodflags)

# 4. Generate Alpha transparency channel (outer background is 0, subject is 255)
bg_mask = mask[1:h+1, 1:w+1]
alpha = np.where(bg_mask == 255, 0, 255).astype(np.uint8)

# 5. Composite RGBA image and save
b, g, r = cv2.split(img)
rgba = cv2.merge([b, g, r, alpha])
cv2.imwrite('icon_transparent.png', rgba)

# 6. Generate multi-resolution Windows ICO file
pil_img = Image.fromarray(cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA))
pil_img.save('icon.ico', format='ICO', sizes=[(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)])

print("✅ Generated transparent PNG (icon_transparent.png) and icon (icon.ico)")