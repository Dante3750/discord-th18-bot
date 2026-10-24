"""Downloads the real DINOv2 model and checks it can tell bases apart. Run in CI (needs internet).

Pass = a re-shot of the same base scores clearly higher than a different base.
Results are also emitted as GitHub annotations (::notice:: / ::error::) so they show on the PR.
"""

import os
import sys
import time
import traceback

from PIL import ImageEnhance, ImageOps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conftest import fake_base_image  # noqa: E402
from th18bot import vision  # noqa: E402


def report(kind, msg):
    print(msg)
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{kind}::{msg}".replace("\n", "%0A"))


def main():
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
    report("notice", f"DINOv2 ok: vector {va.shape[0]}, load+3 imgs {load_s:.1f}s, {per_image * 1000:.0f} ms/img, "
                     f"same-base {same:.3f} vs different-base {diff:.3f}")
    assert va.shape[0] == 768, f"unexpected vector size {va.shape[0]}"
    assert same > diff + 0.05, f"can't separate same ({same:.3f}) vs different ({diff:.3f})"


if __name__ == "__main__":
    try:
        main()
    except Exception:
        report("error", "model check failed: " + traceback.format_exc()[-900:])
        sys.exit(1)
