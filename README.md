# Tetris Packing Demo

3D bin-packing for roll containers with interactive step-by-step visualization.

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

## How It Works

1. **Algorithm** (`packing_algorithm.py`) — Tetris-style 3-phase packing:
   - Phase 1: Fill the floor
   - Phase 2: Fill shelf levels (every 20 cm)
   - Phase 3: Stack on existing products
   - Tries 7 sort strategies and keeps the best result

2. **Visualizer** (`visualizer_plotly.py`) — Plotly WebGL 3D with:
   - Step-by-step navigation (◀ Previous / Next ▶)
   - Keyboard arrows (← →) and dropdown
   - Fragile items marked red with ✕, shelves shown brown where used

## Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point — run this |
| `product.py` | Product model (Quader + Cylinder) |
| `container.py` | Roll container model |
| `packing_algorithm.py` | Multi-strategy 3D packing |
| `visualizer_plotly.py` | Interactive 3D visualization |
| `sample_data.py` | 24 sample food products |

## Container

100 × 80 × 170 cm, 300 kg max, shelves every 20 cm.

## Controls

| Key | Action |
|-----|--------|
| `→` | Next step |
| `←` | Previous step |
| Dropdown | Jump to any step |
| Mouse | Rotate / zoom / pan |
