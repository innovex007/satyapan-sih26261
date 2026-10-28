"""Real sample photos (data/real_photos, metadata already stripped). The originals are never modified:
full-size uses copy the file bytes; variants are re-encoded copies."""
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = [ROOT / "data" / "real_photos" / "real_photos", ROOT / "data" / "real_photos"]


def photo_dir() -> Path:
    for p in CANDIDATES:
        if (p / "twin_a_physics_lab.jpg").exists():
            return p
    raise FileNotFoundError("data/real_photos/ with the 10 sample JPGs not found")


@lru_cache(maxsize=None)
def raw(name: str) -> bytes:
    return (photo_dir() / f"{name}.jpg").read_bytes()


@lru_cache(maxsize=None)
def _img(name: str) -> Image.Image:
    im = Image.open(photo_dir() / f"{name}.jpg")
    im.load()
    return im.convert("RGB")


def image(name: str) -> Image.Image:
    return _img(name).copy()


def half_variant(name: str, idx: int) -> Image.Image:
    """Non-overlapping variants of a small photo: left/right half x optional mirror (idx 0..3), upscaled, with a small colour shift."""
    im = _img(name)
    w, h = im.size
    half = im.crop((0, 0, w // 2, h)) if idx % 2 == 0 else im.crop((w // 2, 0, w, h))
    if idx >= 2:
        half = half.transpose(Image.FLIP_LEFT_RIGHT)
    half = half.resize((half.width * 2, half.height * 2), Image.LANCZOS)
    a = np.asarray(half, dtype=np.float32)
    shift = np.array([1.0 + 0.04 * (idx - 1.5), 1.0, 1.0 - 0.04 * (idx - 1.5)], dtype=np.float32)
    return Image.fromarray(np.clip(a * shift, 0, 255).astype(np.uint8))


def copy_variant(img: Image.Image, brightness: float) -> Image.Image:
    """A re-used photo: 4% of the frame cropped (2% per side), scaled back, brightness +/-10% (JPEG q70 is applied on save)."""
    w, h = img.size
    dx, dy = int(w * 0.02), int(h * 0.02)
    out = img.crop((dx, dy, w - dx, h - dy)).resize((w, h), Image.BICUBIC)
    return Image.fromarray(np.clip(np.asarray(out, dtype=np.float32) * (1 + brightness), 0, 255).astype(np.uint8))
