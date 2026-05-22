"""
Tetris-style roll-container packing demo.

Packs the sample products into one or more roll containers and opens
an interactive 3D visualization in the browser.
"""

from container import RollContainer
from sample_data import create_sample_products
from packing_algorithm import MultiContainerPacker
from visualizer_plotly import PackingVisualizerPlotly


def make_container(index: int) -> RollContainer:
    """Factory for fresh roll containers (100×80×170 cm, 300 kg, shelves @ 20 cm)."""
    return RollContainer(
        length=100, width=80, height=170,
        max_weight=300, name=f"Roll Container #{index}",
    )


def main():
    template = make_container(1)
    products = create_sample_products()

    print(f"Container template: {template}")
    print(f"Products to pack:   {len(products)}")

    packer = MultiContainerPacker(container_factory=make_container, max_containers=20)
    solution = packer.pack(products)

    # ----- summary -----
    print(f"\n{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")
    print(f"  Containers used: {solution.container_count}")
    print(f"  Total placed:    {solution.total_placed}/{len(products)}")
    print(f"  Total weight:    {solution.total_weight:.1f} kg")
    print(f"  Avg utilization: {solution.average_utilization():.1f}%")

    for i, cfg in enumerate(solution.containers, 1):
        print(f"\n  Container #{i}: "
              f"{len(cfg.placed_products)} items, "
              f"{cfg.get_utilization():.1f}% util, "
              f"{cfg.total_weight:.1f}/{cfg.container.max_weight} kg")

    if solution.unpacked_products:
        print(f"\n  Could not pack ({len(solution.unpacked_products)}):")
        for p in solution.unpacked_products:
            print(f"    - {p.name} ({p.dimensions})")

    # ----- placement sequence (bottom→top per container) -----
    for i, cfg in enumerate(solution.containers, 1):
        print(f"\n{'=' * 60}")
        print(f"CONTAINER #{i} - PLACEMENT SEQUENCE (bottom to top)")
        print(f"{'=' * 60}")
        for n, placed in enumerate(cfg.placed_products, 1):
            x, y, z = placed.position
            l, w, h = placed.dimensions
            tag = " FRAGILE" if placed.product.fragile else ""
            print(f"  {n:2d}. {placed.product.name}{tag}")
            print(f"      pos=({x:.0f},{y:.0f},{z:.0f})  "
                  f"dims={l:.0f}×{w:.0f}×{h:.0f}  top={z+h:.0f}cm")

    input("\nPress Enter to open 3D visualization...")
    PackingVisualizerPlotly(solution).show()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        import traceback
        print(f"\nError: {e}")
        traceback.print_exc()
