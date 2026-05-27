"""
Flask web app — used for local development and as a fallback for /api/*
on Vercel. The main page is pre-built into ./public/ by build.py and
served as a static file directly from the edge CDN, so this app is no
longer on the critical path of the main page load.

Endpoints:
  GET /              the 3D viewer page (re-renders on each request — for local dev)
  GET /api/packing   current packing result as JSON (cached in process)
  GET /img/<code>    product image as JPEG (cached in process)
"""

from __future__ import annotations

import io
import threading

from flask import Flask, abort, jsonify, make_response, send_file

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


# ---- Process-wide cache ----------------------------------------------------
# Vercel keeps an instance warm for ~5 min; this cache holds the packed
# solution and rendered HTML so we never re-run the algorithm per request.

_lock = threading.Lock()
_cache: dict = {"html": None, "payload": None}


def _ensure_cache() -> dict:
    if _cache["html"] is None:
        with _lock:
            if _cache["html"] is None:
                packer = MultiContainerPacker(
                    container_factory=_make_container, max_containers=20,
                )
                solution = packer.pack(create_sample_products(), verbose=False)
                _cache["html"]    = render_html(solution, include_images=False, image_base="/img")
                _cache["payload"] = build_payload(solution, include_images=False, image_base="/img")
    return _cache


# ---- Routes ----------------------------------------------------------------

@app.route("/")
def index():
    html = _ensure_cache()["html"]
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"
    return resp


@app.route("/api/packing")
def api_packing():
    resp = jsonify(_ensure_cache()["payload"])
    resp.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"
    return resp


@app.route("/img/<code>")
def image(code: str):
    data = load_image_bytes(code)
    if not data:
        abort(404)
    return send_file(
        io.BytesIO(data),
        mimetype="image/jpeg",
        download_name=f"{code}.jpg",
        max_age=31536000,
    )


if __name__ == "__main__":
    _ensure_cache()  # warm cache before serving requests
    app.run(host="127.0.0.1", port=5000, debug=False)
