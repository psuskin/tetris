"""
Pre-resolve and resize product images into static/img/<code>.jpg.

Run once before deploying to Vercel so the 5+ GB source folder
("Artikel Bilder 360 KI - Filtered") can be excluded from the build.
The prepared images are small (~50 KB each) and are loaded directly
by image_resolver at runtime.

Usage:
    python prepare_images.py            # process all order codes
    python prepare_images.py 9505 9508  # process only specific codes
"""

from __future__ import annotations

import sys
from pathlib import Path

from image_resolver import (
    PREPARED_DIR,
    find_image_path,
    _load_and_resize,
)
from sample_data import RAW_ORDER


def codes_from_order() -> list[str]:
    return [entry["code"] for entry in RAW_ORDER]


def prepare(codes: list[str]) -> None:
    PREPARED_DIR.mkdir(parents=True, exist_ok=True)
    missing, written, skipped = [], 0, 0

    for code in codes:
        target = PREPARED_DIR / f"{code}.jpg"
        if target.exists():
            skipped += 1
            continue
        src = find_image_path(code)
        if src is None:
            missing.append(code)
            continue
        target.write_bytes(_load_and_resize(src))
        written += 1
        print(f"  {code}: {src.name} -> {target.name}")

    print(f"\nWrote {written}, already present {skipped}, missing {len(missing)}")
    if missing:
        print(f"  Missing codes: {', '.join(missing)}")


if __name__ == "__main__":
    codes = sys.argv[1:] or codes_from_order()
    print(f"Preparing {len(codes)} product image(s) -> {PREPARED_DIR}\n")
    prepare(codes)
