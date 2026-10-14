"""Remove a flat magenta (#FF00FF) page background from a Canva thumbnail of a character -> RGBA PNG.
  python key_char.py char_on_magenta.png char.png"""
import sys, numpy as np
from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(float); r, g, b = a[..., 0], a[..., 1], a[..., 2]
al = np.clip(1 - ((np.minimum(r, b) - g) - 60) / 110, 0, 1)
lim = g + (np.maximum(r, b) - g) * al; a[..., 0] = np.minimum(r, np.maximum(g, lim)); a[..., 2] = np.minimum(b, np.maximum(g, lim))
im = Image.fromarray(np.dstack([a, al * 255]).astype(np.uint8), "RGBA"); im.crop(im.getbbox()).save(sys.argv[2]); print("ok")
