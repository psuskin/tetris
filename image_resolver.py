"""
Resolves product images from the "Artikel Bilder 360 KI - Filtered" folder.

Each product folder contains ~35 360-degree shots with no angle metadata;
we pick the largest valid JPEG as the representative image and cache the
resized result so the visualiser can embed or serve it.
"""

from __future__ import annotations

import base64
import io
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import Image


IMAGE_ROOT = Path(__file__).parent / "Artikel Bilder 360 KI - Filtered"
PREPARED_DIR = Path(__file__).parent / "static" / "img"
TEXTURE_SIZE = (512, 512)
JPEG_QUALITY = 78

_VALID_EXTS = {".jpg", ".jpeg", ".png"}
_SKIP_NAMES = {"thumbs.db"}


@lru_cache(maxsize=None)
def _folder_for(code: str) -> Optional[Path]:
    """Folder whose name begins with ``code`` followed by a space."""
    if not IMAGE_ROOT.exists():
        return None
    prefix = f"{code} "
    for child in IMAGE_ROOT.iterdir():
        if child.is_dir() and child.name.startswith(prefix):
            return child
    return None


@lru_cache(maxsize=None)
def find_image_path(code: str) -> Optional[Path]:
    """Pick the largest valid image in the product folder."""
    folder = _folder_for(code)
    if folder is None:
        return None
    candidates = []
    for f in folder.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in _VALID_EXTS:
            continue
        if f.name.lower() in _SKIP_NAMES:
            continue
        candidates.append(f)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def _load_and_resize(path: Path) -> bytes:
    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    # Square crop to centre, then resize — keeps the product framed.
    side = min(img.width, img.height)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize(TEXTURE_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


@lru_cache(maxsize=None)
def load_image_bytes(code: str) -> Optional[bytes]:
    """
    Return the resized JPEG bytes for a product.

    Prefers a pre-baked image at ``static/img/<code>.jpg`` (produced by
    ``prepare_images.py``) so production deploys don't need the 5+ GB
    source folder. Falls back to picking & resizing from the source.
    """
    prepared = PREPARED_DIR / f"{code}.jpg"
    if prepared.is_file():
        return prepared.read_bytes()

    path = find_image_path(code)
    if path is None:
        return None
    return _load_and_resize(path)


def load_image_dataurl(code: str) -> Optional[str]:
    """Return the resized image as a base64 ``data:`` URL, or None."""
    data = load_image_bytes(code)
    if data is None:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def base_code(product_id: str) -> str:
    """Strip the per-unit suffix from an expanded product id (e.g. '9508-2' → '9508')."""
    return product_id.split("-", 1)[0]
