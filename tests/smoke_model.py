"""Downloads the real DINOv2 model and checks it can tell bases apart. Run in CI (needs internet).

Pass = the model loads and runs on CPU, and the layout check (verify.py) separates a re-shot of
the same base from a different base. The DINOv2 scores are reported, not asserted: a global
embedding can't tell Clash bases apart on its own; it only builds the shortlist.
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
from th18bot import verify, vision  # noqa: E402


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
    p_same, p_diff = verify.inliers(a, a_reshot), verify.inliers(a, b)
    report("notice", f"layout check: same base {p_same} points, different base {p_diff} (need {verify.SAME_BASE_INLIERS})")
    assert p_same >= verify.SAME_BASE_INLIERS > p_diff, "layout check can't separate bases"


if __name__ == "__main__":
    try:
        main()
    except Exception:
        report("error", "model check failed: " + traceback.format_exc()[-900:])
        sys.exit(1)
