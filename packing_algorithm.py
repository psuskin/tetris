"""
3D Tetris-style bin packing algorithm.

Core idea: place each product at the LOWEST valid position (minimise z+h).
Tries multiple sort orders and keeps the best result.

Constraints enforced:
  - No collisions between products
  - Products must be fully supported (floor, shelf, or >=50% footprint on non-fragile products)
  - Fragile products above floor must sit on a shelf level
  - No product may span vertically through an occupied shelf level
  - Weight and dimension limits respected
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from product import Product
from container import RollContainer


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlacedProduct:
    product: Product
    orientation: str
    position: Tuple[float, float, float]      # (x, y, z)
    dimensions: Tuple[float, float, float]     # oriented (l, w, h)

    def get_bounds(self):
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
    def __init__(self, container: RollContainer):
        self.container = container
        self.placed_products: List[PlacedProduct] = []
        self.unpacked_products: List[Product] = []
        self.total_weight: float = 0.0

    def add_placement(self, p: PlacedProduct) -> bool:
        if self.total_weight + p.product.weight > self.container.max_weight:
            return False
        _, (mx, my, mz) = p.get_bounds()
        EPS = 0.01
        if mx > self.container.length + EPS or my > self.container.width + EPS or mz > self.container.height + EPS:
            return False
        for e in self.placed_products:
            if p.overlaps_with(e):
                return False
        self.placed_products.append(p)
        self.total_weight += p.product.weight
        return True

    def get_utilization(self) -> float:
        used = sum(p.product.volume() for p in self.placed_products)
        return (used / self.container.volume()) * 100.0


# ---------------------------------------------------------------------------
# Algorithm
# ---------------------------------------------------------------------------

class ProperPackingAlgorithm:
    """
    Lowest-point-first 3D packing with multi-strategy optimisation.

    For each product (in sort order) we try EVERY viable z-level from bottom
    to top and pick the position that results in the lowest product top (z+h).
    Ties are broken by wall/neighbour contact score.
    """

    SUPPORT_THRESHOLD = 0.50   # 50 % footprint overlap required

    def __init__(self, container: RollContainer):
        self.container = container
        self.si = container.shelf_interval          # shelf interval (20 cm)

    # ----- orientation helpers -----

    @staticmethod
    def _orientation_variants(product: Product):
        """All unique (orient_label, dims) including 90-deg z-rotation."""
        seen = set()
        out = []
        for o in product.allowed_orientations:
            dims = product.get_oriented_dimensions(o)
            l, w, h = dims
            for d in ((l, w, h), (w, l, h)):
                key = (round(d[0], 2), round(d[1], 2), round(d[2], 2))
                if key not in seen:
                    seen.add(key)
                    out.append((o, d))
        return out

    # ----- sort strategies -----

    @staticmethod
    def _sort_strategies():
        return [
            ("volume_desc",    lambda p: p.volume(), True),
            ("footprint_desc", lambda p: p.dimensions[0] * p.dimensions[1], True),
            ("height_desc",    lambda p: p.dimensions[2], True),
            ("weight_desc",    lambda p: p.weight, True),
            ("volume_asc",     lambda p: p.volume(), False),
            ("fragile_first",  lambda p: (0 if p.fragile else 1, -p.volume()), False),
            ("heavy_bottom",   lambda p: (-p.weight, -p.volume()), False),
            ("tall_then_big",  lambda p: (-p.dimensions[2], -p.volume()), False),
            ("compact_first",  lambda p: -(p.dimensions[0] * p.dimensions[1]) / max(p.dimensions[2], 1), False),
        ]

    # ----- public API -----

    def optimize_packing(self, products: List[Product]) -> PackingConfiguration:
        best_cfg = None
        best_score = -1.0
        best_name = ""

        strategies = self._sort_strategies()
        for name, key_fn, rev in strategies:
            cfg = self._pack(sorted(products, key=key_fn, reverse=rev), verbose=False)
            score = len(cfg.placed_products) * 10000 + cfg.get_utilization()
            if score > best_score:
                best_score, best_cfg, best_name = score, cfg, name

        # Re-run winner with output
        print(f"\n=== BEST STRATEGY: {best_name} (of {len(strategies)} tried) ===")
        for sn, kf, rv in strategies:
            if sn == best_name:
                best_cfg = self._pack(sorted(products, key=kf, reverse=rv), verbose=True)
                break
        return best_cfg

    def pack_products(self, products: List[Product]) -> PackingConfiguration:
        return self._pack(sorted(products, key=lambda p: p.volume(), reverse=True), verbose=True)

    # ----- core loop -----

    def _pack(self, products: List[Product], verbose: bool) -> PackingConfiguration:
        cfg = PackingConfiguration(self.container)
        remaining = list(products)

        if verbose:
            print()
        made_progress = True
        while made_progress and remaining:
            made_progress = False
            left = []
            for prod in remaining:
                pl = self._find_best(prod, cfg)
                if pl and cfg.add_placement(pl):
                    made_progress = True
                    if verbose:
                        z, zt = pl.position[2], pl.position[2] + pl.dimensions[2]
                        tag = self._placement_tag(z, pl, cfg)
                        frag = " FRAGILE" if prod.fragile else ""
                        print(f"  + {prod.name}{frag}  ({pl.position[0]:.0f},{pl.position[1]:.0f},{z:.0f}) top={zt:.0f}cm  [{tag}]")
                else:
                    left.append(prod)
            remaining = left

        cfg.unpacked_products = remaining
        if verbose:
            print(f"\n  Placed {len(cfg.placed_products)}/{len(cfg.placed_products) + len(remaining)}"
                  f"  util={cfg.get_utilization():.1f}%  weight={cfg.total_weight:.1f}kg")
            if remaining:
                print(f"  Unpacked: {[p.name for p in remaining]}")
        return cfg

    # ----- lowest-point search -----

    def _placement_tag(self, z, placed, cfg):
        """Human-readable tag for where a product was placed."""
        if z < 0.1:
            return "floor"
        # Is this z a shelf level?
        sn = round(z / self.si)
        if sn > 0 and abs(z - sn * self.si) < 0.1:
            # Check if it's stacked on another product (not a shelf)
            for p in cfg.placed_products:
                if p is placed:
                    continue
                (_, _, pz), (_, _, pmz) = p.get_bounds()
                if abs(pmz - z) < 0.1:
                    # Overlap in x-y?
                    px, py = p.position[0], p.position[1]
                    pmx, pmy = px + p.dimensions[0], py + p.dimensions[1]
                    ox = max(0, min(placed.position[0] + placed.dimensions[0], pmx) - max(placed.position[0], px))
                    oy = max(0, min(placed.position[1] + placed.dimensions[1], pmy) - max(placed.position[1], py))
                    if ox > 0 and oy > 0:
                        return f"stacked z={z:.0f}"
            return f"shelf z={z:.0f}"
        return f"stacked z={z:.0f}"

    def _find_best(self, product: Product, cfg: PackingConfiguration) -> Optional[PlacedProduct]:
        """Return placement with the lowest z+h, ties broken by score."""
        z_levels = self._z_levels(cfg)
        best = None
        best_top = float('inf')
        best_sc = float('inf')

        for z in z_levels:
            # Early exit: no z-level from here on can beat best_top
            if z >= best_top:
                break

            for orient, dims in self._orientation_variants(product):
                ztop = z + dims[2]
                if ztop > self.container.height + 0.01:
                    continue
                if ztop > best_top + 0.01:
                    continue

                # Fragile above floor → must be on shelf
                if product.fragile and z > 0.1:
                    sn = round(z / self.si)
                    if abs(z - sn * self.si) > 0.1:
                        continue

                for pos in self._candidates(dims, z, cfg):
                    if not self._valid(pos, dims, cfg, product):
                        continue
                    sc = self._score(pos, dims, cfg)
                    top_r = round(ztop, 2)
                    if top_r < best_top or (top_r == best_top and sc < best_sc):
                        best_top, best_sc = top_r, sc
                        best = PlacedProduct(product=product, orientation=orient,
                                             position=pos, dimensions=dims)
        return best

    def _z_levels(self, cfg: PackingConfiguration):
        """All viable z-levels, sorted ascending."""
        levels = {0.0}
        for p in cfg.placed_products:
            levels.add(round(p.get_bounds()[1][2], 2))    # product tops
        for i in range(1, int(self.container.height / self.si) + 1):
            levels.add(i * self.si)                        # shelf levels
        return sorted(levels)

    # ----- candidate position generator -----

    def _candidates(self, dims, z, cfg):
        l, w, _ = dims
        cL, cW = self.container.length, self.container.width
        seen = set()
        out = []

        def add(x, y):
            k = (round(x, 1), round(y, 1))
            if k not in seen and 0 <= x and 0 <= y and x + l <= cL + 0.01 and y + w <= cW + 0.01:
                seen.add(k)
                out.append((x, y, z))

        # Container corners
        add(0, 0);  add(cL - l, 0);  add(0, cW - w);  add(cL - l, cW - w)

        # Edges of placed products
        for p in cfg.placed_products:
            (px, py, pz), (pmx, pmy, pmz) = p.get_bounds()
            if abs(pz - z) < 0.1:                    # product starts at this level
                add(pmx, py); add(px, pmy); add(pmx, pmy)
                add(pmx, 0);  add(0, pmy)
            if abs(pmz - z) < 0.1:                    # product top at this level
                add(px, py); add(pmx, py); add(px, pmy); add(pmx, pmy)
                add(px + (pmx - px - l) / 2, py + (pmy - py - w) / 2)   # centred

        # Wall-aligned at 1 cm
        for x in range(0, int(cL - l) + 1, 1):
            add(float(x), 0.0)
            add(float(x), cW - w)
        for y in range(0, int(cW - w) + 1, 1):
            add(0.0, float(y))
            add(cL - l, float(y))

        # Interior grid at 5 cm
        for x in range(0, int(cL - l) + 1, 5):
            for y in range(0, int(cW - w) + 1, 5):
                add(float(x), float(y))

        out.sort(key=lambda c: (c[1], c[0]))
        return out

    # ----- scoring (lower = better) -----

    def _score(self, pos, dims, cfg):
        x, y, z = pos
        l, w, h = dims
        cL, cW = self.container.length, self.container.width

        # Wall contact
        walls = sum([x < 0.1, y < 0.1, abs(x + l - cL) < 0.1, abs(y + w - cW) < 0.1])

        # Neighbour contact (side faces touching placed products)
        contact = 0
        for p in cfg.placed_products:
            (px, py, pz), (pmx, pmy, pmz) = p.get_bounds()
            # Must overlap in z
            if max(z, pz) >= min(z + h, pmz):
                continue
            # X-face adjacency
            if abs(x + l - px) < 0.1 or abs(pmx - x) < 0.1:
                if max(y, py) < min(y + w, pmy):
                    contact += 1
            # Y-face adjacency
            if abs(y + w - py) < 0.1 or abs(pmy - y) < 0.1:
                if max(x, px) < min(x + l, pmx):
                    contact += 1

        return y * 2 + x - walls * 60 - contact * 40

    # ----- validation -----

    def _valid(self, pos, dims, cfg, product):
        x, y, z = pos
        l, w, h = dims
        EPS = 0.01
        if x < -EPS or y < -EPS or z < -EPS:
            return False
        if x + l > self.container.length + EPS:
            return False
        if y + w > self.container.width + EPS:
            return False
        if z + h > self.container.height + EPS:
            return False

        test = PlacedProduct(product=product, orientation='B', position=pos, dimensions=dims)
        for e in cfg.placed_products:
            if test.overlaps_with(e):
                return False

        # Must not span through an occupied shelf level
        if self._spans_occupied_shelf(z, h, cfg):
            return False

        return self._supported(pos, dims, cfg, product)

    def _spans_occupied_shelf(self, z, h, cfg):
        """True if (z, z+h) straddles a shelf that already has products on it."""
        z_top = z + h
        for sn in range(1, int(self.container.height / self.si) + 1):
            sz = sn * self.si
            if z + 0.5 < sz < z_top - 0.5:
                # Product's z-range strictly contains this shelf level
                for p in cfg.placed_products:
                    if abs(p.position[2] - sz) < 0.5:
                        return True          # shelf is occupied → block
        return False

    def _supported(self, pos, dims, cfg, product):
        x, y, z = pos
        l, w, _ = dims

        # Floor
        if abs(z) < 0.01:
            return True

        # Shelf
        sn = round(z / self.si)
        if sn > 0 and abs(z - sn * self.si) < 0.01:
            if self._shelf_clear(sn * self.si, cfg):
                return True

        # Stacking: need SUPPORT_THRESHOLD of footprint on non-fragile products
        footprint = l * w
        supported = 0.0
        for p in cfg.placed_products:
            if p.product.fragile:
                continue
            (px, py, pz), (pmx, pmy, pmz) = p.get_bounds()
            if abs(pmz - z) > 0.1:
                continue
            ox = max(0.0, min(x + l, pmx) - max(x, px))
            oy = max(0.0, min(y + w, pmy) - max(y, py))
            supported += ox * oy

        return supported >= footprint * self.SUPPORT_THRESHOLD

    def _shelf_clear(self, sz, cfg):
        """True if no placed product straddles shelf_z."""
        for p in cfg.placed_products:
            (_, _, pz), (_, _, pmz) = p.get_bounds()
            if pz < sz - 0.5 < pmz:
                return False
        return True
