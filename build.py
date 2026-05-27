"""
Pre-render the viewer as static files into ./public/.

This is what Vercel will actually serve, so the page comes off the
edge CDN with no Python cold start on the load path. Run:

    python prepare_images.py    # once, to slim the source images
    python build.py             # before each deploy
    git add public/ && git commit && git push
"""

from __future__ import annotations

import shutil
from pathlib import Path

from container import RollContainer
from sample_data import create_sample_products
from packing_algorithm import MultiContainerPacker
from visualizer import render_html


ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"
SRC_IMAGES = ROOT / "static" / "img"


def make_container(i: int) -> RollContainer:
    return RollContainer(
        length=100, width=80, height=170,
        max_weight=300, name=f"Roll Container #{i}",
    )


def build() -> None:
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    (PUBLIC / "img").mkdir(parents=True)

    # Copy prepared product images.
    if not SRC_IMAGES.exists():
        raise SystemExit(
            f"{SRC_IMAGES} is missing. Run `python prepare_images.py` first."
        )
    count = 0
    for jpg in sorted(SRC_IMAGES.glob("*.jpg")):
        shutil.copy(jpg, PUBLIC / "img" / jpg.name)
        count += 1

    # Pack and render once.
    packer = MultiContainerPacker(container_factory=make_container, max_containers=20)
    solution = packer.pack(create_sample_products(), verbose=False)
    html = render_html(solution, include_images=False, image_base="/img")
    (PUBLIC / "index.html").write_text(html, encoding="utf-8")

    print(f"  public/index.html  ({len(html)//1024} KB)")
    print(f"  public/img/        ({count} images)")
    print(f"\nContainers: {solution.container_count}")
    print(f"Placed:     {solution.total_placed}")
    print(f"Unpacked:   {len(solution.unpacked_products)}")


if __name__ == "__main__":
    print(f"Building {PUBLIC}...\n")
    build()
