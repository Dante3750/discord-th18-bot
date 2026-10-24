"""Image fingerprints used to match a screenshot back to a known base.

A. phash  - 64-bit perceptual hash. Survives resize/recompress/small crops, so it catches
            reposts of the SAME picture. Tiny and instant.
B. embed  - 768-number DINOv2-small vector (CLS + mean patch) (Meta, Apache-2.0). Captures how the base *looks*,
            so a different screenshot of the same layout scores high. Runs on CPU.

The heavy model is only imported when first needed, so the rest of the bot works without torch.
"""

import base64
import io

import numpy as np
import requests
from PIL import Image

MODEL_ID = "facebook/dinov2-small"
SIZE = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def open_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def download(url: str, timeout=30) -> bytes:
    if "pbs.twimg.com/media/" in url and "name=" not in url:
        url += ("&" if "?" in url else "?") + "name=medium"  # ~1200px is plenty, saves bandwidth
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "th18-base-finder"})
    r.raise_for_status()
    return r.content


# --- A: perceptual hash ----------------------------------------------------------

def phash(img: Image.Image) -> str:
    import imagehash
    return str(imagehash.phash(img))


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# --- B: DINOv2 embedding ---------------------------------------------------------

def letterbox(img: Image.Image, size=SIZE) -> np.ndarray:
    """Fit the whole screenshot into a square (no center crop: base edges matter)."""
    w, h = img.size
    scale = size / max(w, h)
    resized = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.BICUBIC)
    canvas = Image.new("RGB", (size, size), (0, 0, 0))
    canvas.paste(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    arr = (np.asarray(canvas, dtype=np.float32) / 255.0 - MEAN) / STD
    return arr.transpose(2, 0, 1)  # CHW


class Embedder:
    def __init__(self, model_id=MODEL_ID):
        self.model_id = model_id
        self._model = None

    def _load(self):
        if self._model is None:
            import torch
            from transformers import AutoModel
            torch.set_num_threads(2)
            self._torch = torch
            self._model = AutoModel.from_pretrained(self.model_id).eval()
        return self._model

    def __call__(self, img: Image.Image) -> np.ndarray:
        model = self._load()
        x = self._torch.from_numpy(letterbox(img)[None])
        with self._torch.no_grad():
            out = model(pixel_values=x).last_hidden_state
        # CLS token + mean of patch tokens: global look + layout detail
        vec = self._torch.cat([out[:, 0], out[:, 1:].mean(dim=1)], dim=1)[0].numpy()
        return normalize(vec)


def normalize(vec) -> np.ndarray:
    vec = np.asarray(vec, dtype=np.float32)
    return vec / (np.linalg.norm(vec) + 1e-8)


def encode_vec(vec: np.ndarray) -> str:
    return base64.b64encode(np.asarray(vec, dtype=np.float16).tobytes()).decode()


def decode_vec(s: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype=np.float16).astype(np.float32)


def fingerprint(img: Image.Image, embedder=None) -> dict:
    fp = {"phash": phash(img)}
    if embedder is not None:
        fp["emb"] = encode_vec(embedder(img))
        fp["model"] = getattr(embedder, "model_id", "custom")
    return fp


def make_embedder(enabled: bool = True):
    """Embedder if torch + transformers are installed, else None (phash-only mode)."""
    if not enabled:
        return None
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        print("  torch/transformers not installed: picture fingerprints only, no AI similarity")
        return None
    return Embedder()
