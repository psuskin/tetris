"""
Tetris-style roll-container packing demo.

Runs the packing algorithm on sample products and opens
an interactive 3D visualization in the browser.
"""

from container import RollContainer
from sample_data import create_sample_products
from packing_algorithm import ProperPackingAlgorithm
from visualizer_plotly import PackingVisualizerPlotly


def main():
    # Container: 100×80×170 cm, 300 kg max, shelves every 20 cm
    container = RollContainer(
        length=100, width=80, height=170,
        max_weight=300, name="Roll Container"
    )

    products = create_sample_products()

    print(f"Container: {container}")
    print(f"Products to pack: {len(products)}")

    # Run multi-strategy packing
    algo = ProperPackingAlgorithm(container)
    config = algo.optimize_packing(products)

    # Summary
    print(f"\n{'='*50}")
    print(f"RESULTS")
    print(f"{'='*50}")
    print(f"  Packed:      {len(config.placed_products)}/{len(products)}")
    print(f"  Utilization: {config.get_utilization():.1f}%")
    print(f"  Weight:      {config.total_weight:.1f} / {container.max_weight} kg")

    if config.unpacked_products:
        print(f"\n  Could not pack:")
        for p in config.unpacked_products:
            print(f"    - {p.name} ({p.dimensions})")

    # Placement sequence
    print(f"\n{'='*50}")
    print(f"PLACEMENT SEQUENCE")
    print(f"{'='*50}")
    for i, placed in enumerate(config.placed_products, 1):
        x, y, z = placed.position
        l, w, h = placed.dimensions
        frag = " 🔴FRAGILE" if placed.product.fragile else ""
        print(f"  {i:2d}. {placed.product.name}{frag}")
        print(f"      pos=({x:.0f},{y:.0f},{z:.0f})  dims={l:.0f}×{w:.0f}×{h:.0f}  top={z+h:.0f}cm")

    # Launch 3D visualizer
    input("\nPress Enter to open 3D visualization...")
    visualizer = PackingVisualizerPlotly(config)
    visualizer.show(start_step=0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
