"""
Flask web app — designed to run locally and deploy to Vercel.

Endpoints:
  GET /              the 3D viewer page
  GET /api/packing   current packing result as JSON
  GET /img/<code>    product image (resized JPEG)

Vercel routes everything to this app via vercel.json.
"""

from __future__ import annotations

from flask import Flask, abort, jsonify, send_file
import io

from container import RollContainer
from sample_data import create_sample_products
from packing_algorithm import MultiContainerPacker
from image_resolver import load_image_bytes
from visualizer import build_payload, render_html


app = Flask(__name__)


def _make_container(index: int) -> RollContainer:
    return RollContainer(
        length=100, width=80, height=170,
        max_weight=300, name=f"Roll Container #{index}",
    )


def _pack():
    packer = MultiContainerPacker(container_factory=_make_container, max_containers=20)
    return packer.pack(create_sample_products(), verbose=False)


@app.route("/")
def index():
    solution = _pack()
    # In server mode, images load lazily via /img/<code>.
    return render_html(solution, include_images=False, image_base="/img")


@app.route("/api/packing")
def api_packing():
    solution = _pack()
    return jsonify(build_payload(solution, include_images=False, image_base="/img"))


@app.route("/img/<code>")
def image(code: str):
    data = load_image_bytes(code)
    if not data:
        abort(404)
    return send_file(
        io.BytesIO(data),
        mimetype="image/jpeg",
        download_name=f"{code}.jpg",
        max_age=86400,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
