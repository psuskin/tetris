"""
3D Tetris-style bin packing algorithm.

Strategy: Fill floor → shelf levels → stack on products.
Tries multiple sort orders and keeps the best result.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from product import Product
from container import RollContainer


@dataclass
class PlacedProduct:
    """A product placed in the container."""
    product: Product
    orientation: str
    position: Tuple[float, float, float]  # (x, y, z) in cm
    dimensions: Tuple[float, float, float]  # Oriented (l, w, h)

    def get_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        x, y, z = self.position
        l, w, h = self.dimensions
        return (self.position, (x + l, y + w, z + h))

    def overlaps_with(self, other: 'PlacedProduct') -> bool:
        (x1, y1, z1), (mx1, my1, mz1) = self.get_bounds()
        (x2, y2, z2), (mx2, my2, mz2) = other.get_bounds()
        return not (mx1 <= x2 or mx2 <= x1 or
                    my1 <= y2 or my2 <= y1 or
                    mz1 <= z2 or mz2 <= z1)

    def __repr__(self):
        return f"{self.product.id} at {self.position}"


class PackingConfiguration:
    """A complete packing result."""

    def __init__(self, container: RollContainer):
        self.container = container
        self.placed_products: List[PlacedProduct] = []
        self.unpacked_products: List[Product] = []
        self.total_weight = 0.0

    def add_placement(self, placement: PlacedProduct) -> bool:
        if self.total_weight + placement.product.weight > self.container.max_weight:
            return False
        _, (mx, my, mz) = placement.get_bounds()
        if mx > self.container.length + 0.01 or my > self.container.width + 0.01 or mz > self.container.height + 0.01:
            return False
        for existing in self.placed_products:
            if placement.overlaps_with(existing):
                return False
        self.placed_products.append(placement)
        self.total_weight += placement.product.weight
        return True

    def get_utilization(self) -> float:
        used = sum(p.product.volume() for p in self.placed_products)
        return (used / self.container.volume()) * 100.0

    def __repr__(self):
        return f"<Config: {len(self.placed_products)} placed, {len(self.unpacked_products)} unpacked>"


class ProperPackingAlgorithm:
    """
    Tetris-style 3D packing with multi-strategy optimization.

    Tries multiple product sort orders and keeps the best result.
    Each attempt uses a 3-phase approach:
      Phase 1: Fill the floor (z=0)
      Phase 2: Fill shelf levels (20cm intervals)
      Phase 3: Stack on existing products
    """

    def __init__(self, container: RollContainer):
        self.container = container
        self.shelf_interval = container.shelf_interval

    # ------------------------------------------------------------------
    # Sort strategies
    # ------------------------------------------------------------------
    @staticmethod
    def _sort_strategies():
        return [
            ("volume_desc", lambda p: p.volume(), True),
            ("footprint_desc", lambda p: p.dimensions[0] * p.dimensions[1], True),
            ("height_desc", lambda p: p.dimensions[2], True),
            ("weight_desc", lambda p: p.weight, True),
            ("volume_asc", lambda p: p.volume(), False),
            ("fragile_first", lambda p: (0 if p.fragile else 1, -p.volume()), False),
            ("heavy_bottom", lambda p: (-p.weight, -p.volume()), False),
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def optimize_packing(self, products: List[Product]) -> PackingConfiguration:
        """Try multiple strategies and return the best packing."""
        best_config = None
        best_score = -1
        best_name = ""

        strategies = self._sort_strategies()
        for name, key_fn, reverse in strategies:
            sorted_prods = sorted(products, key=key_fn, reverse=reverse)
            config = self._pack_products(sorted_prods, verbose=False)
            score = len(config.placed_products) * 10000 + config.get_utilization()
            if score > best_score:
                best_score = score
                best_config = config
                best_name = name

        # Re-run the winner with verbose output
        print(f"\n=== PACKING STRATEGY: {best_name} (best of {len(strategies)} tried) ===")
        best_key = None
        best_rev = True
        for sname, key_fn, rev in strategies:
            if sname == best_name:
                best_key = key_fn
                best_rev = rev
                break
        sorted_prods = sorted(products, key=best_key, reverse=best_rev)
        best_config = self._pack_products(sorted_prods, verbose=True)
        return best_config

    def pack_products(self, products: List[Product]) -> PackingConfiguration:
        """Single-pass packing (volume descending)."""
        sorted_prods = sorted(products, key=lambda p: p.volume(), reverse=True)
        return self._pack_products(sorted_prods, verbose=True)

    # ------------------------------------------------------------------
    # Core packing
    # ------------------------------------------------------------------
    def _pack_products(self, products: List[Product], verbose: bool = False) -> PackingConfiguration:
        config = PackingConfiguration(self.container)
        remaining = list(products)

        if verbose:
            print("\n--- Phase 1: Floor (z=0) ---")
        remaining = self._fill_level(remaining, 0.0, config, verbose)

        if verbose:
            print(f"  Floor: {len(config.placed_products)} items")
            print("\n--- Phase 2: Shelf levels ---")

        shelf_levels = [i * self.shelf_interval
                        for i in range(1, int(self.container.height / self.shelf_interval) + 1)]
        for shelf_z in shelf_levels:
            if not remaining:
                break
            before = len(config.placed_products)
            remaining = self._fill_level(remaining, shelf_z, config, verbose)
            after = len(config.placed_products)
            if verbose and after > before:
                print(f"  z={shelf_z:.0f}cm: +{after - before} items")

        if remaining:
            if verbose:
                print(f"\n--- Phase 3: Stacking ({len(remaining)} left) ---")
            remaining = self._stack_remaining(remaining, config, verbose)

        config.unpacked_products = remaining
        return config

    def _fill_level(self, remaining, z, config, verbose):
        progress = True
        while progress and remaining:
            progress = False
            still_remaining = []
            for product in remaining:
                placed = self._try_place_at_level(product, z, config)
                if placed:
                    config.add_placement(placed)
                    progress = True
                    if verbose:
                        print(f"    ✓ {product.name} at {placed.position}")
                else:
                    still_remaining.append(product)
            remaining = still_remaining
        return remaining

    def _stack_remaining(self, remaining, config, verbose):
        progress = True
        while progress and remaining:
            progress = False
            still_remaining = []
            for product in remaining:
                placed = self._try_stack(product, config)
                if placed:
                    config.add_placement(placed)
                    progress = True
                    if verbose:
                        print(f"    ✓ {product.name} at {placed.position}")
                else:
                    still_remaining.append(product)
            remaining = still_remaining
        return remaining

    # ------------------------------------------------------------------
    # Placement logic
    # ------------------------------------------------------------------
    def _try_place_at_level(self, product, z, config):
        """Find best position on a Z level across all orientations."""
        best = None
        best_score = float('inf')

        for orient in product.allowed_orientations:
            dims = product.get_oriented_dimensions(orient)
            if z + dims[2] > self.container.height:
                continue
            if product.fragile and z > 0.1:
                sn = round(z / self.shelf_interval)
                if abs(z - sn * self.shelf_interval) > 0.1:
                    continue

            for pos in self._candidate_positions(dims, z, config):
                if self._is_valid(pos, dims, config, product):
                    score = self._score(pos, dims)
                    if score < best_score:
                        best_score = score
                        best = PlacedProduct(product=product, orientation=orient,
                                             position=pos, dimensions=dims)
        return best

    def _try_stack(self, product, config):
        z_tops = sorted({round(p.get_bounds()[1][2], 2) for p in config.placed_products})
        best = None
        best_score = float('inf')

        for z in z_tops:
            if z + 1 > self.container.height:
                continue
            for orient in product.allowed_orientations:
                dims = product.get_oriented_dimensions(orient)
                if z + dims[2] > self.container.height:
                    continue
                for pos in self._stacking_candidates(dims, z, config):
                    if self._is_valid(pos, dims, config, product):
                        score = self._score(pos, dims) + z  # prefer lower stacks
                        if score < best_score:
                            best_score = score
                            best = PlacedProduct(product=product, orientation=orient,
                                                 position=pos, dimensions=dims)
        return best

    # ------------------------------------------------------------------
    # Candidate generators
    # ------------------------------------------------------------------
    def _candidate_positions(self, dims, z, config):
        l, w, _ = dims
        cL, cW = self.container.length, self.container.width
        seen = set()
        result = []

        def add(x, y):
            key = (round(x, 1), round(y, 1))
            if key not in seen and 0 <= x and 0 <= y and x + l <= cL + 0.01 and y + w <= cW + 0.01:
                seen.add(key)
                result.append((x, y, z))

        add(0.0, 0.0)

        for placed in config.placed_products:
            (px, py, pz), (pmx, pmy, pmz) = placed.get_bounds()
            if abs(pz - z) < 0.1:
                add(pmx, py); add(px, pmy); add(pmx, pmy)
                add(pmx, 0.0); add(0.0, pmy)
            if abs(pmz - z) < 0.1:
                add(px, py); add(pmx, py); add(px, pmy); add(pmx, pmy)

        # Wall-aligned at 5cm intervals
        for x in range(0, int(cL - l) + 1, 5):
            add(float(x), 0.0)
            add(float(x), cW - w)
        for y in range(0, int(cW - w) + 1, 5):
            add(0.0, float(y))
            add(cL - l, float(y))

        # Sparse interior grid (10cm) if few candidates
        if len(result) < 50:
            for x in range(0, int(cL - l) + 1, 10):
                for y in range(0, int(cW - w) + 1, 10):
                    add(float(x), float(y))

        result.sort(key=lambda c: (c[1], c[0]))
        return result

    def _stacking_candidates(self, dims, z, config):
        l, w, _ = dims
        cL, cW = self.container.length, self.container.width
        seen = set()
        result = []

        def add(x, y):
            key = (round(x, 1), round(y, 1))
            if key not in seen and 0 <= x and 0 <= y and x + l <= cL + 0.01 and y + w <= cW + 0.01:
                seen.add(key)
                result.append((x, y, z))

        for placed in config.placed_products:
            (px, py, pz), (pmx, pmy, pmz) = placed.get_bounds()
            if abs(pmz - z) < 0.1:
                add(px, py); add(pmx, py); add(px, pmy); add(pmx, pmy)
                add(px + (pmx - px - l) / 2, py + (pmy - py - w) / 2)

        result.sort(key=lambda c: (c[1], c[0]))
        return result

    # ------------------------------------------------------------------
    # Scoring — prefer corners and wall contact
    # ------------------------------------------------------------------
    def _score(self, pos, dims):
        x, y, z = pos
        l, w, _ = dims
        cL, cW = self.container.length, self.container.width

        walls = sum([x < 0.1, y < 0.1, abs(x + l - cL) < 0.1, abs(y + w - cW) < 0.1])
        return y * 2 + x - walls * 50

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _is_valid(self, pos, dims, config, product):
        x, y, z = pos
        l, w, h = dims
        if x < -0.01 or y < -0.01 or z < -0.01:
            return False
        if x + l > self.container.length + 0.01:
            return False
        if y + w > self.container.width + 0.01:
            return False
        if z + h > self.container.height + 0.01:
            return False

        test = PlacedProduct(product=product, orientation='B', position=pos, dimensions=dims)
        for existing in config.placed_products:
            if test.overlaps_with(existing):
                return False

        return self._is_supported(pos, dims, config, product)

    def _is_supported(self, pos, dims, config, product):
        x, y, z = pos
        l, w, _ = dims

        if abs(z) < 0.01:
            return True

        sn = round(z / self.shelf_interval)
        if abs(z - sn * self.shelf_interval) < 0.01 and sn > 0:
            if self._is_shelf_clear(sn * self.shelf_interval, config):
                return True

        footprint = l * w
        supported = 0.0
        for placed in config.placed_products:
            if placed.product.fragile:
                continue
            (px, py, pz), (pmx, pmy, pmz) = placed.get_bounds()
            if abs(pmz - z) > 0.1:
                continue
            ox = max(0, min(x + l, pmx) - max(x, px))
            oy = max(0, min(y + w, pmy) - max(y, py))
            supported += ox * oy

        return supported >= footprint * 0.7

    def _is_shelf_clear(self, shelf_z, config):
        for placed in config.placed_products:
            (_, _, pz), (_, _, pmz) = placed.get_bounds()
            if pz < shelf_z - 0.5 < pmz:
                return False
        return True
