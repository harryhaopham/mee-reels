"""Turn a Canva thumbnail of the MEE logo on its blue gradient into a white logo PNG with alpha.
  python key_logo.py logo_on_blue.png logo_white.png
Works because the logo is white/translucent-white and the background is a left->right blue gradient:
alpha = how much whiter each pixel is than the background of its column (sampled from the top rows)."""
import sys, numpy as np
from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(float)
bg = np.broadcast_to(np.median(a[0:60], axis=0), a.shape)
al = np.clip(((a - bg) / (255 - bg + 1e-6)).max(-1), 0, 1); al = np.clip((al - 0.04) / 0.96, 0, 1)
out = np.zeros(a.shape[:2] + (4,), np.uint8); out[..., :3] = 255; out[..., 3] = (al * 255).astype(np.uint8)
out[..., 3][out[..., 3] < 14] = 0
im = Image.fromarray(out); A = np.asarray(im.getchannel("A")); ys, xs = np.where(A > 60)
im.crop((max(0, xs.min() - 6), max(0, ys.min() - 6), xs.max() + 7, ys.max() + 7)).save(sys.argv[2]); print("ok")
