"""
Three.js-based viewer for packing results.

Renders each placed product as a textured box/cylinder so the packer
can identify items by their actual photograph. The same payload format
is used for the standalone HTML output (embedded base64 textures) and
the Flask deployment (textures served via /img/<code>).
"""

from __future__ import annotations

import json
import os
import tempfile
import webbrowser
from pathlib import Path
from typing import Iterable, Union

from packing_algorithm import (
    EPS,
    MultiContainerSolution,
    PackingConfiguration,
    PlacedProduct,
)
from product import ProductType
from image_resolver import base_code, load_image_dataurl


TEMPLATE_PATH = Path(__file__).parent / "viewer_template.html"
_PAYLOAD_MARKER = "__PAYLOAD__"


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------

def _placed_to_dict(p: PlacedProduct) -> dict:
    shape = "cylinder" if p.product.product_type == ProductType.CYLINDER else "cuboid"
    return {
        "name":        p.product.name,
        "code":        base_code(p.product.id),
        "shape":       shape,
        "orientation": p.orientation,
        "position":    [float(v) for v in p.position],
        "dimensions":  [float(v) for v in p.dimensions],
        "weight":      float(p.product.weight),
        "fragile":     bool(p.product.fragile),
        "color":       p.product.color,
    }


def _installed_shelves(cfg: PackingConfiguration) -> list[float]:
    """Z-heights where a product physically rests on a shelf (not stacked)."""
    si = cfg.container.shelf_interval
    installed: set[float] = set()
    items = cfg.placed_products
    for p in items:
        z = p.position[2]
        if z <= 0 or abs(round(z / si) * si - z) > 0.1:
            continue
        stacked = False
        for q in items:
            if q is p:
                continue
            if abs(q.z_max - z) > 0.1:
                continue
            ox = max(0.0, min(p.x_max, q.x_max) - max(p.position[0], q.position[0]))
            oy = max(0.0, min(p.y_max, q.y_max) - max(p.position[1], q.position[1]))
            if ox > EPS and oy > EPS:
                stacked = True
                break
        if not stacked:
            installed.add(z)
    return sorted(installed)


def _container_to_dict(cfg: PackingConfiguration) -> dict:
    return {
        "container": {
            "length":         float(cfg.container.length),
            "width":          float(cfg.container.width),
            "height":         float(cfg.container.height),
            "shelf_interval": float(cfg.container.shelf_interval),
            "name":           cfg.container.name,
        },
        "shelves":      _installed_shelves(cfg),
        "utilization":  cfg.get_utilization(),
        "weight":       cfg.total_weight,
        "max_weight":   cfg.container.max_weight,
        "products":     [_placed_to_dict(p) for p in cfg.placed_products],
    }


def _collect_codes(solution: MultiContainerSolution) -> set[str]:
    codes = set()
    for cfg in solution.containers:
        for p in cfg.placed_products:
            codes.add(base_code(p.product.id))
    return codes


def build_payload(solution: MultiContainerSolution,
                  include_images: bool = True,
                  image_base: str = "") -> dict:
    """JSON-serialisable payload for the viewer template."""
    payload: dict = {
        "containers": [_container_to_dict(c) for c in solution.containers],
        "start_c":    0,
        "start_s":    0,
    }
    if include_images:
        payload["images"] = _build_image_map(_collect_codes(solution))
    else:
        payload["image_base"] = image_base
    return payload


def _build_image_map(codes: Iterable[str]) -> dict[str, str]:
    """Map product codes to base64 data URLs, skipping unresolved ones."""
    images: dict[str, str] = {}
    for code in codes:
        url = load_image_dataurl(code)
        if url:
            images[code] = url
    return images


# ---------------------------------------------------------------------------
# HTML assembly
# ---------------------------------------------------------------------------

def _serialise_payload(payload: dict) -> str:
    """JSON-encode the payload, safe for embedding inside <script>."""
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def render_html(solution: MultiContainerSolution,
                include_images: bool = True,
                image_base: str = "") -> str:
    payload = build_payload(solution, include_images=include_images, image_base=image_base)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace(_PAYLOAD_MARKER, _serialise_payload(payload))


# ---------------------------------------------------------------------------
# Convenience class
# ---------------------------------------------------------------------------

class PackingVisualizer:
    """Drop-in replacement for the old Plotly visualiser."""

    def __init__(self, solution: Union[PackingConfiguration, MultiContainerSolution]):
        if isinstance(solution, MultiContainerSolution):
            self.solution = solution
        else:
            wrapped = MultiContainerSolution()
            wrapped.containers = [solution]
            wrapped.unpacked_products = solution.unpacked_products
            self.solution = wrapped

    def show(self) -> str:
        """Write the viewer HTML to a temp file and open it in the browser."""
        html = render_html(self.solution, include_images=True)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            path = f.name
        webbrowser.open("file://" + os.path.abspath(path))
        print(f"\nViewer opened: {path}")
        print("  Controls: drag = orbit, scroll = zoom, arrow keys = step")
        return path
