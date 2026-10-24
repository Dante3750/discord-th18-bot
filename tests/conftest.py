import hashlib
import io
import os
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from th18bot import vision  # noqa: E402


def fake_base_image(seed: str, size=(960, 540)) -> Image.Image:
    """A 'base screenshot': random coloured tiles on a grid, unique per seed."""
    rng = np.random.default_rng(int(hashlib.md5(seed.encode()).hexdigest()[:8], 16))
    grid = rng.integers(0, 255, size=(18, 32, 3), dtype=np.uint8)
    return Image.fromarray(grid).resize(size, Image.NEAREST)


def jpeg_bytes(img: Image.Image, quality=90) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


class TinyEmbedder:
    """Stand-in for DINOv2 in tests: 16x16 grayscale thumbnail as the vector."""
    model_id = "tiny-test"

    def __call__(self, img):
        v = np.asarray(img.convert("L").resize((16, 16)), dtype=np.float32).ravel()
        return vision.normalize(v - v.mean())


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    """No network in tests: every image URL becomes a fake screenshot seeded by its URL."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VISION", "0")
    monkeypatch.setattr(vision, "download", lambda url, timeout=30: jpeg_bytes(fake_base_image(url)))
