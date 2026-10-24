"""Downloads the real DINOv2 model and checks it can tell bases apart. Run in CI (needs internet).

Pass = a re-shot of the same base scores clearly higher than a different base.
"""

import os
import sys
import time

from PIL import ImageEnhance, ImageOps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conftest import fake_base_image  # noqa: E402
from th18bot import vision  # noqa: E402

t0 = time.time()
emb = vision.Embedder()
a = fake_base_image("base-a")
a_reshot = ImageEnhance.Brightness(ImageOps.crop(a.resize((1280, 720)), 30)).enhance(0.8)
b = fake_base_image("base-b")

va, va2, vb = emb(a), emb(a_reshot), emb(b)
load_s = time.time() - t0
t1 = time.time()
for _ in range(5):
    emb(a)
per_image = (time.time() - t1) / 5

same, diff = float(va @ va2), float(va @ vb)
print(f"vector size: {va.shape[0]}  model load+3 images: {load_s:.1f}s  per image: {per_image * 1000:.0f} ms")
print(f"same base re-shot: {same:.3f}   different base: {diff:.3f}")
assert va.shape[0] == 768, "unexpected vector size"
assert same > diff + 0.05, "model can't separate same vs different base"
print("OK")
