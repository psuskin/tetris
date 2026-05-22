"""
Interactive 3D visualizer for single- or multi-container packings.

Accepts a PackingConfiguration (one container) or a MultiContainerSolution
(any number) and renders an HTML page with container + step navigation.
"""

import json
import os
import re
import tempfile
import webbrowser
from typing import List, Union

import numpy as np
import plotly.graph_objects as go

from product import Product, ProductType
from packing_algorithm import PackingConfiguration, MultiContainerSolution


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

_COLOR_NAMES = {
    'lightblue':      'rgb(173, 216, 230)',
    'lightcoral':     'rgb(240, 128, 128)',
    'lightgreen':     'rgb(144, 238, 144)',
    'lightyellow':    'rgb(255, 255, 224)',
    'lightgray':      'rgb(211, 211, 211)',
    'lightcyan':      'rgb(224, 255, 255)',
    'skyblue':        'rgb(135, 206, 235)',
    'deepskyblue':    'rgb(0, 191, 255)',
    'paleturquoise':  'rgb(175, 238, 238)',
    'tan':            'rgb(210, 180, 140)',
    'wheat':          'rgb(245, 222, 179)',
    'burlywood':      'rgb(222, 184, 135)',
    'beige':          'rgb(245, 245, 220)',
    'ivory':          'rgb(255, 255, 240)',
    'gold':           'rgb(255, 215, 0)',
    'yellow':         'rgb(255, 255, 0)',
    'blue':           'rgb(0, 0, 255)',
    'red':            'rgb(255, 0, 0)',
    'green':          'rgb(0, 128, 0)',
    'darkgreen':      'rgb(0, 100, 0)',
    'limegreen':      'rgb(50, 205, 50)',
    'olive':          'rgb(128, 128, 0)',
    'orange':         'rgb(255, 165, 0)',
    'purple':         'rgb(128, 0, 128)',
    'brown':          'rgb(139, 69, 19)',
    'chocolate':      'rgb(210, 105, 30)',
    'maroon':         'rgb(128, 0, 0)',
    'darkred':        'rgb(139, 0, 0)',
    'lavender':       'rgb(230, 230, 250)',
    'white':          'rgb(245, 245, 245)',
}

_PALETTE = [
    'rgb(31, 119, 180)', 'rgb(255, 127, 14)', 'rgb(44, 160, 44)',
    'rgb(214, 39, 40)',  'rgb(148, 103, 189)', 'rgb(140, 86, 75)',
    'rgb(227, 119, 194)', 'rgb(127, 127, 127)', 'rgb(188, 189, 34)',
    'rgb(23, 190, 207)',
]


def _to_rgb(color: str) -> str:
    return _COLOR_NAMES.get(color, color)


def _darken(rgb: str, factor: float = 0.6) -> str:
    m = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', rgb)
    if not m:
        return rgb
    r, g, b = (int(int(m.group(i)) * factor) for i in (1, 2, 3))
    return f'rgb({r}, {g}, {b})'


# ---------------------------------------------------------------------------
# Numpy-aware JSON encoder
# ---------------------------------------------------------------------------

class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):  return obj.tolist()
        if isinstance(obj, np.integer):  return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        return super().default(obj)


# ---------------------------------------------------------------------------
# Visualizer
# ---------------------------------------------------------------------------

class PackingVisualizerPlotly:
    """Renders a packing as an interactive HTML page."""

    def __init__(self, solution: Union[PackingConfiguration, MultiContainerSolution]):
        if isinstance(solution, MultiContainerSolution):
            self.solution = solution
        else:
            wrapped = MultiContainerSolution()
            wrapped.containers = [solution]
            wrapped.unpacked_products = solution.unpacked_products
            self.solution = wrapped
        self._product_colors = {}

    # ----- color assignment ---------------------------------------------------

    def _color_for(self, product: Product) -> str:
        if product.color:
            return _to_rgb(product.color)
        if product.id not in self._product_colors:
            self._product_colors[product.id] = _PALETTE[len(self._product_colors) % len(_PALETTE)]
        return self._product_colors[product.id]

    # ----- mesh builders ------------------------------------------------------

    @staticmethod
    def _box_mesh(position, dimensions, color, opacity, name, edge_color) -> go.Mesh3d:
        x, y, z = position
        l, w, h = dimensions
        verts = np.array([
            [x,   y,   z  ], [x+l, y,   z  ], [x+l, y+w, z  ], [x,   y+w, z  ],
            [x,   y,   z+h], [x+l, y,   z+h], [x+l, y+w, z+h], [x,   y+w, z+h],
        ])
        i = [0, 0, 1, 1, 2, 2, 3, 3, 0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
        j = [1, 3, 2, 0, 3, 1, 0, 2, 4, 1, 5, 0, 3, 4, 5, 2, 6, 3, 7, 0, 5, 7, 6, 4]
        k = [2, 2, 3, 3, 0, 0, 1, 1, 5, 5, 1, 1, 7, 7, 2, 2, 3, 3, 4, 4, 6, 6, 7, 7]
        return go.Mesh3d(
            x=verts[:, 0], y=verts[:, 1], z=verts[:, 2], i=i, j=j, k=k,
            color=color, opacity=opacity, name=name, text=name,
            showlegend=False, hoverinfo='text', flatshading=False,
            lighting=dict(ambient=0.6, diffuse=0.8, specular=0.2, roughness=0.5),
            lightposition=dict(x=100, y=100, z=200),
            contour=dict(show=True, color=edge_color, width=6),
        )

    @staticmethod
    def _cylinder_mesh(position, dimensions, orientation, color, opacity, name) -> go.Mesh3d:
        x, y, z = position
        d1, d2, d3 = dimensions
        n_theta, n_long = 20, 10
        theta = np.linspace(0, 2 * np.pi, n_theta)

        if orientation == 'M':
            # Horizontal cylinder: the z-extent is always the diameter.
            # The remaining two dims contain the diameter (again) and the cylinder length;
            # whichever matches d3 is the diameter, the other is the length.
            radius = d3 / 2
            if abs(d1 - d3) < 0.1:
                # d1 == diameter → cylinder lies along Y, length = d2
                long_axis = np.linspace(y, y + d2, n_long)
                tg, yg = np.meshgrid(theta, long_axis)
                xg = x + radius + radius * np.cos(tg)
                zg = z + radius + radius * np.sin(tg)
            else:
                # d2 == diameter → cylinder lies along X, length = d1
                long_axis = np.linspace(x, x + d1, n_long)
                tg, xg = np.meshgrid(theta, long_axis)
                yg = y + radius + radius * np.cos(tg)
                zg = z + radius + radius * np.sin(tg)
        else:
            radius = d1 / 2
            zc = np.linspace(z, z + d3, n_long)
            tg, zg = np.meshgrid(theta, zc)
            xg = x + radius + radius * np.cos(tg)
            yg = y + radius + radius * np.sin(tg)

        i, j, k = [], [], []
        for ti in range(n_long - 1):
            for tj in range(n_theta - 1):
                idx = ti * n_theta + tj
                i += [idx, idx + 1]
                j += [idx + 1, idx + n_theta + 1]
                k += [idx + n_theta, idx + n_theta]

        return go.Mesh3d(
            x=xg.flatten(), y=yg.flatten(), z=zg.flatten(), i=i, j=j, k=k,
            color=color, opacity=opacity, name=name, text=name,
            showlegend=False, hoverinfo='text', flatshading=False,
            lighting=dict(ambient=0.6, diffuse=0.8, specular=0.2, roughness=0.5),
            lightposition=dict(x=100, y=100, z=200),
            contour=dict(show=True, color='black', width=3),
        )

    @staticmethod
    def _fragile_marks(position, dimensions) -> List[go.Scatter3d]:
        x, y, z = position
        l, w, h = dimensions
        zt = z + h + 0.01
        line_kw = dict(mode='lines', line=dict(color='darkred', width=4),
                       showlegend=False, hoverinfo='skip')
        return [
            go.Scatter3d(x=[x, x + l], y=[y, y + w], z=[zt, zt], **line_kw),
            go.Scatter3d(x=[x + l, x], y=[y, y + w], z=[zt, zt], **line_kw),
        ]

    # ----- container chrome ---------------------------------------------------

    def _container_traces(self, cfg: PackingConfiguration, step_idx: int) -> List:
        container = cfg.container
        traces: List = []

        # Shelf levels that hold products RESTING ON them (not stacked above)
        used_shelves = set()
        for i in range(step_idx + 1):
            placed = cfg.placed_products[i]
            z = placed.position[2]
            if z > 0 and z % container.shelf_interval == 0:
                resting_on_product = False
                for j in range(step_idx + 1):
                    if j == i:
                        continue
                    other = cfg.placed_products[j]
                    if abs(other.z_max - z) < 0.1:
                        x_ov = (placed.position[0] < other.x_max and placed.x_max > other.position[0])
                        y_ov = (placed.position[1] < other.y_max and placed.y_max > other.position[1])
                        if x_ov and y_ov:
                            resting_on_product = True
                            break
                if not resting_on_product:
                    used_shelves.add(int(z))

        # Container hull
        traces.append(self._box_mesh(
            (0, 0, 0), (container.length, container.width, container.height),
            'rgb(200, 200, 200)', opacity=0.03, name="Container", edge_color='rgb(150,150,150)',
        ))

        traces.append(go.Scatter3d(
            x=[0, container.length, container.length, 0, 0, None,
               0, 0, None, container.length, container.length, None,
               container.length, container.length, None, 0, 0],
            y=[0, 0, container.width, container.width, 0, None,
               0, 0, None, 0, 0, None,
               container.width, container.width, None, container.width, container.width],
            z=[0, 0, 0, 0, 0, None,
               0, container.height, None, 0, container.height, None,
               0, container.height, None, 0, container.height],
            mode='lines', line=dict(color='gray', width=1),
            showlegend=False, hoverinfo='skip',
        ))

        # Only render shelves that are actually installed (have products resting on them).
        # Uninstalled shelf positions are invisible — they aren't physical structures.
        for z in used_shelves:
            traces.append(go.Mesh3d(
                x=[0, container.length, container.length, 0],
                y=[0, 0, container.width, container.width],
                z=[z, z, z, z], i=[0, 0], j=[1, 2], k=[2, 3],
                color='rgb(139, 90, 43)', opacity=0.4,
                showlegend=False, hoverinfo='skip',
            ))
            traces.append(go.Scatter3d(
                x=[0, container.length, container.length, 0, 0],
                y=[0, 0, container.width, container.width, 0],
                z=[z] * 5, mode='lines',
                line=dict(color='rgb(139, 90, 43)', width=2),
                showlegend=False, hoverinfo='skip',
            ))
            traces.append(go.Scatter3d(
                x=[container.length + 5], y=[container.width / 2], z=[z],
                mode='text', text=[f'{z}cm'],
                textfont=dict(size=10, color='gray'),
                showlegend=False, hoverinfo='skip',
            ))
        return traces

    # ----- per-step trace data ------------------------------------------------

    def _step_traces(self, cfg: PackingConfiguration, step_idx: int) -> List:
        traces = list(self._container_traces(cfg, step_idx))
        for i in range(step_idx + 1):
            placed = cfg.placed_products[i]
            color = 'rgb(240, 128, 128)' if placed.product.fragile else self._color_for(placed.product)
            opacity = 0.9 if i == step_idx else 0.65
            label = f"{placed.product.id} - {placed.product.name}"
            if placed.product.fragile:
                label = "FRAGILE " + label

            if placed.product.product_type == ProductType.CYLINDER:
                traces.append(self._cylinder_mesh(
                    placed.position, placed.dimensions, placed.orientation,
                    color, opacity, label,
                ))
            else:
                traces.append(self._box_mesh(
                    placed.position, placed.dimensions, color,
                    opacity, label, _darken(color),
                ))

            if placed.product.fragile:
                traces.extend(self._fragile_marks(placed.position, placed.dimensions))
        return traces

    # ----- HTML rendering -----------------------------------------------------

    def show(self, start_container: int = 0, start_step: int = 0) -> None:
        """Open the visualization in the browser, starting at step 1 of each container."""
        # Pre-compute all traces: containers[c].steps[s]
        all_data = []
        for cfg in self.solution.containers:
            steps = [self._step_traces(cfg, i) for i in range(len(cfg.placed_products))]
            all_data.append([[t.to_plotly_json() for t in step] for step in steps])

        # Layout per container (axes scale with container dims)
        layouts = []
        labels = []
        for ci, cfg in enumerate(self.solution.containers):
            c = cfg.container
            layouts.append({
                'scene': {
                    'xaxis': {'title': 'Length (cm)', 'range': [0, c.length * 1.1]},
                    'yaxis': {'title': 'Width (cm)',  'range': [0, c.width  * 1.1]},
                    'zaxis': {'title': 'Height (cm)', 'range': [0, c.height * 1.05]},
                    'aspectmode': 'manual',
                    'aspectratio': {
                        'x': c.length / c.height,
                        'y': c.width  / c.height,
                        'z': 1.0,
                    },
                    'camera': {
                        'eye':    {'x': 1.5, 'y': 1.5, 'z': 1.2},
                        'center': {'x': 0,   'y': 0,   'z': 0},
                        'up':     {'x': 0,   'y': 0,   'z': 1},
                    },
                },
                'showlegend': False,
                'height': 900,
                'margin': {'l': 60, 'r': 60, 't': 60, 'b': 90},
            })
            step_labels = []
            for j, placed in enumerate(cfg.placed_products):
                tag = "FRAGILE " if placed.product.fragile else ""
                step_labels.append(f"{tag}{placed.product.name}")
            labels.append(step_labels)

        # Clamp starting indices
        n_containers = len(self.solution.containers)
        if n_containers == 0:
            print("Nothing to visualize.")
            return
        start_container = max(0, min(start_container, n_containers - 1))
        n_steps = len(self.solution.containers[start_container].placed_products)
        start_step = max(0, min(start_step, n_steps - 1))

        unpacked_names = [p.name for p in self.solution.unpacked_products]

        payload = {
            'all_data':      all_data,
            'layouts':       layouts,
            'step_labels':   labels,
            'start_c':       start_container,
            'start_s':       start_step,
            'unpacked':      unpacked_names,
        }
        payload_json = json.dumps(payload, cls=_NumpyEncoder)

        html = _HTML_TEMPLATE.replace('__PAYLOAD__', payload_json)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            path = f.name
        webbrowser.open('file://' + os.path.abspath(path))
        print(f"\nVisualization opened: {path}")
        print("  Arrow keys: Left/Right step, Shift+Left/Right container")


# ---------------------------------------------------------------------------
# HTML template (Plotly UMD + custom controls)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Roll Container Packing</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif; background: #fafafa; }
    #plot { width: 100vw; height: calc(100vh - 88px); }
    #ctrl {
      position: fixed; bottom: 0; left: 0; right: 0; height: 88px;
      background: #f1f1f1; border-top: 1px solid #ccc;
      display: flex; align-items: center; justify-content: center;
      gap: 16px; padding: 0 24px;
    }
    .group { display: flex; align-items: center; gap: 8px; }
    .group .lbl { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
    button {
      padding: 8px 14px; font-size: 14px; font-weight: 600;
      border: 1px solid #888; border-radius: 4px;
      background: white; cursor: pointer;
    }
    button:hover:not(:disabled) { background: #e6e6e6; }
    button:disabled { opacity: 0.35; cursor: not-allowed; }
    #info { font-size: 14px; color: #222; min-width: 280px; text-align: center; }
    #info b { color: #000; }
    #unpacked { font-size: 11px; color: #b00; max-width: 320px; }
  </style>
</head>
<body>
  <div id="plot"></div>
  <div id="ctrl">
    <div class="group">
      <span class="lbl">Container</span>
      <button id="prevC">◀</button>
      <button id="nextC">▶</button>
    </div>
    <div id="info">…</div>
    <div class="group">
      <span class="lbl">Step</span>
      <button id="prevS">◀</button>
      <button id="nextS">▶</button>
    </div>
    <div id="unpacked"></div>
  </div>

<script>
const DATA = __PAYLOAD__;
let c = DATA.start_c;
let s = DATA.start_s;

function nSteps(ci) { return DATA.all_data[ci].length; }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function render(initial) {
  const layout = Object.assign({}, DATA.layouts[c], {
    title: `Container ${c+1} of ${DATA.all_data.length} — Step ${s+1} of ${nSteps(c)}: ${DATA.step_labels[c][s]}`,
  });
  const cfg = { responsive: true };
  if (initial) {
    Plotly.newPlot('plot', DATA.all_data[c][s], layout, cfg);
  } else {
    Plotly.react('plot', DATA.all_data[c][s], layout, cfg);
  }
  document.getElementById('info').innerHTML =
      `<b>Container ${c+1}/${DATA.all_data.length}</b> · Step ${s+1}/${nSteps(c)}`;
  document.getElementById('prevC').disabled = (c === 0);
  document.getElementById('nextC').disabled = (c === DATA.all_data.length - 1);
  document.getElementById('prevS').disabled = (s === 0);
  document.getElementById('nextS').disabled = (s === nSteps(c) - 1);

  const u = DATA.unpacked;
  if (u && u.length) {
    document.getElementById('unpacked').innerHTML =
        `<b>Unpacked (${u.length}):</b> ${u.join(', ')}`;
  }
}

function setContainer(nc) {
  nc = clamp(nc, 0, DATA.all_data.length - 1);
  if (nc === c) return;
  c = nc;
  s = 0;
  render(false);
}
function setStep(ns) {
  ns = clamp(ns, 0, nSteps(c) - 1);
  if (ns === s) return;
  s = ns;
  render(false);
}

document.getElementById('prevC').onclick = () => setContainer(c - 1);
document.getElementById('nextC').onclick = () => setContainer(c + 1);
document.getElementById('prevS').onclick = () => setStep(s - 1);
document.getElementById('nextS').onclick = () => setStep(s + 1);
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowLeft')  e.shiftKey ? setContainer(c - 1) : setStep(s - 1);
  if (e.key === 'ArrowRight') e.shiftKey ? setContainer(c + 1) : setStep(s + 1);
});

render(true);
</script>
</body>
</html>
"""
