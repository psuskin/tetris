"""
3D Tetris-style bin packing for roll containers.

Core idea: place each product at the LOWEST valid position (minimise z+h).
Multiple sort strategies are tried; the winner is kept.

Constraints:
  - No collisions between products (AABB).
  - Each product must be supported: floor, shelf, or >=50% footprint
    overlap on the FLAT TOP of one or more placed products.
  - Curved tops do not support stacking — a cylinder lying on its side ('M')
    and any fragile product expose no flat top.
  - Fragile products above the floor must sit on a shelf level.
  - A product may not span vertically through an occupied shelf.
  - Container weight and dimensions are respected.

Multi-container packing spills any leftover products into additional
roll containers until everything fits (or the cap is hit).
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from product import Product, ProductType
from container import RollContainer


EPS = 0.01
SHELF_TOL = 0.1
SUPPORT_THRESHOLD = 0.50   # 50 % footprint overlap needed to stack


# ---------------------------------------------------------------------------
# Placement record
# ---------------------------------------------------------------------------

@dataclass
class PlacedProduct:
    product: Product
    orientation: str
    position: Tuple[float, float, float]      # (x, y, z)
    dimensions: Tuple[float, float, float]    # oriented (l, w, h)

    @property
    def x_max(self) -> float: return self.position[0] + self.dimensions[0]
    @property
    def y_max(self) -> float: return self.position[1] + self.dimensions[1]
    @property
    def z_max(self) -> float: return self.position[2] + self.dimensions[2]

    @property
    def has_flat_top(self) -> bool:
        """False if nothing may be stacked on this product's top face."""
        if self.product.fragile:
            return False
        if self.product.product_type == ProductType.CYLINDER and self.orientation == 'M':
            return False  # lying on its side — round top
        return True

    def overlaps_with(self, other: 'PlacedProduct') -> bool:
        x1, y1, z1 = self.position
        x2, y2, z2 = other.position
        return not (self.x_max <= x2 or other.x_max <= x1 or
                    self.y_max <= y2 or other.y_max <= y1 or
                    self.z_max <= z2 or other.z_max <= z1)

    def __repr__(self):
        return f"{self.product.id} @ {self.position}"


# ---------------------------------------------------------------------------
# Single-container configuration
# ---------------------------------------------------------------------------

class PackingConfiguration:
    def __init__(self, container: RollContainer):
        self.container = container
        self.placed_products: List[PlacedProduct] = []
        self.unpacked_products: List[Product] = []
        self.total_weight: float = 0.0

    def add(self, p: PlacedProduct) -> bool:
        if self.total_weight + p.product.weight > self.container.max_weight:
            return False
        if (p.x_max > self.container.length + EPS or
            p.y_max > self.container.width + EPS or
            p.z_max > self.container.height + EPS):
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

    def sort_bottom_to_top(self) -> None:
        """Order placements bottom→top for stepwise visualisation."""
        self.placed_products.sort(key=lambda p: (
            round(p.position[2], 2),
            round(p.position[1], 2),
            round(p.position[0], 2),
        ))


# ---------------------------------------------------------------------------
# Algorithm
# ---------------------------------------------------------------------------

class ProperPackingAlgorithm:
    """Lowest-point-first 3D packing with multi-strategy optimisation."""

    def __init__(self, container: RollContainer):
        self.container = container
        self.si = container.shelf_interval

    # ----- orientation helpers -------------------------------------------------

    @staticmethod
    def _orientation_variants(product: Product) -> List[Tuple[str, Tuple[float, float, float]]]:
        """All unique (orientation_code, dims) including 90° rotation about z."""
        seen, out = set(), []
        for o in product.allowed_orientations:
            l, w, h = product.get_oriented_dimensions(o)
            for d in ((l, w, h), (w, l, h)):
                key = (round(d[0], 2), round(d[1], 2), round(d[2], 2))
                if key not in seen:
                    seen.add(key)
                    out.append((o, d))
        return out

    # ----- sort strategies -----------------------------------------------------

    @staticmethod
    def _sort_strategies() -> List[Tuple[str, Callable[[Product], object], bool]]:
        return [
            ("volume_desc",    lambda p: p.volume(),                                 True),
            ("footprint_desc", lambda p: p.dimensions[0] * p.dimensions[1],          True),
            ("height_desc",    lambda p: p.dimensions[2],                            True),
            ("weight_desc",    lambda p: p.weight,                                   True),
            ("fragile_first",  lambda p: (0 if p.fragile else 1, -p.volume()),       False),
            ("heavy_bottom",   lambda p: (-p.weight, -p.volume()),                   False),
            ("tall_then_big",  lambda p: (-p.dimensions[2], -p.volume()),            False),
        ]

    # ----- public API ----------------------------------------------------------

    def optimize_packing(self, products: List[Product], verbose: bool = True) -> PackingConfiguration:
        best_cfg: Optional[PackingConfiguration] = None
        best_score = -1.0
        best_name = ""

        for name, key_fn, rev in self._sort_strategies():
            cfg = self._pack(sorted(products, key=key_fn, reverse=rev))
            score = len(cfg.placed_products) * 10_000 + cfg.get_utilization()
            if score > best_score:
                best_score, best_cfg, best_name = score, cfg, name

        assert best_cfg is not None
        best_cfg.sort_bottom_to_top()

        if verbose:
            print(f"  Strategy: {best_name}")
            print(f"  Placed:   {len(best_cfg.placed_products)}/{len(products)}")
            print(f"  Util:     {best_cfg.get_utilization():.1f}%")
            print(f"  Weight:   {best_cfg.total_weight:.1f}/{self.container.max_weight} kg")

        return best_cfg

    # ----- core loop -----------------------------------------------------------

    def _pack(self, products: List[Product]) -> PackingConfiguration:
        cfg = PackingConfiguration(self.container)
        remaining = list(products)
        progress = True
        while progress and remaining:
            progress = False
            still = []
            for prod in remaining:
                pl = self._find_best(prod, cfg)
                if pl and cfg.add(pl):
                    progress = True
                else:
                    still.append(prod)
            remaining = still
        cfg.unpacked_products = remaining
        return cfg

    # ----- lowest-point search -------------------------------------------------

    def _find_best(self, product: Product, cfg: PackingConfiguration) -> Optional[PlacedProduct]:
        """Placement with the lowest top (z+h); ties broken by score."""
        z_levels = self._z_levels(cfg)
        best: Optional[PlacedProduct] = None
        best_top = float('inf')
        best_score = float('inf')

        for z in z_levels:
            if z >= best_top:
                break  # any deeper z can only make ztop larger

            for orient, dims in self._orientation_variants(product):
                ztop = z + dims[2]
                if ztop > self.container.height + EPS or ztop > best_top + EPS:
                    continue

                # Fragile above floor → must rest on a shelf level
                if product.fragile and z > SHELF_TOL:
                    sn = round(z / self.si)
                    if abs(z - sn * self.si) > SHELF_TOL:
                        continue

                for pos in self._candidates(dims, z, cfg):
                    if not self._valid(pos, dims, cfg, product):
                        continue
                    sc = self._score(pos, dims, cfg)
                    top_r = round(ztop, 2)
                    if top_r < best_top or (top_r == best_top and sc < best_score):
                        best_top, best_score = top_r, sc
                        best = PlacedProduct(product=product, orientation=orient,
                                             position=pos, dimensions=dims)
        return best

    def _z_levels(self, cfg: PackingConfiguration) -> List[float]:
        """Floor, shelves, and the tops of flat-topped placements."""
        levels = {0.0}
        for p in cfg.placed_products:
            if p.has_flat_top:
                levels.add(round(p.z_max, 2))
        for i in range(1, int(self.container.height / self.si) + 1):
            levels.add(i * self.si)
        return sorted(levels)

    # ----- candidate position generator ---------------------------------------

    def _candidates(self, dims, z, cfg) -> List[Tuple[float, float, float]]:
        """Extreme points + container corners + coarse fallback grid."""
        l, w, _ = dims
        cL, cW = self.container.length, self.container.width
        seen, out = set(), []

        def add(x: float, y: float) -> None:
            if x < -EPS or y < -EPS or x + l > cL + EPS or y + w > cW + EPS:
                return
            x = max(0.0, x); y = max(0.0, y)
            k = (round(x, 1), round(y, 1))
            if k in seen:
                return
            seen.add(k)
            out.append((x, y, z))

        # Container corners
        add(0, 0); add(cL - l, 0); add(0, cW - w); add(cL - l, cW - w)

        # Extreme points from placed products
        for p in cfg.placed_products:
            px, py = p.position[0], p.position[1]
            pmx, pmy = p.x_max, p.y_max
            add(pmx, py);    add(px, pmy);    add(pmx, pmy);    add(px, py)
            add(pmx, 0);     add(0, pmy)
            add(pmx, cW - w); add(cL - l, pmy)

        # Coarse fallback grid (5 cm) — catches positions extreme points miss
        for x in range(0, int(cL - l) + 1, 5):
            for y in range(0, int(cW - w) + 1, 5):
                add(float(x), float(y))

        out.sort(key=lambda c: (c[1], c[0]))
        return out

    # ----- scoring (lower is better) ------------------------------------------

    def _score(self, pos, dims, cfg) -> float:
        x, y, z = pos
        l, w, h = dims
        cL, cW = self.container.length, self.container.width

        walls = sum([x < SHELF_TOL,
                     y < SHELF_TOL,
                     abs(x + l - cL) < SHELF_TOL,
                     abs(y + w - cW) < SHELF_TOL])

        contact = 0
        for p in cfg.placed_products:
            px, py, pz = p.position
            pmx, pmy, pmz = p.x_max, p.y_max, p.z_max
            if max(z, pz) >= min(z + h, pmz):
                continue  # no z-overlap
            if abs(x + l - px) < SHELF_TOL or abs(pmx - x) < SHELF_TOL:
                if max(y, py) < min(y + w, pmy):
                    contact += 1
            if abs(y + w - py) < SHELF_TOL or abs(pmy - y) < SHELF_TOL:
                if max(x, px) < min(x + l, pmx):
                    contact += 1

        return y * 2 + x - walls * 60 - contact * 40

    # ----- validation ----------------------------------------------------------

    def _valid(self, pos, dims, cfg, product) -> bool:
        x, y, z = pos
        l, w, h = dims
        if x < -EPS or y < -EPS or z < -EPS:
            return False
        if x + l > self.container.length + EPS: return False
        if y + w > self.container.width + EPS:  return False
        if z + h > self.container.height + EPS: return False

        test = PlacedProduct(product=product, orientation='B', position=pos, dimensions=dims)
        for e in cfg.placed_products:
            if test.overlaps_with(e):
                return False

        if self._spans_occupied_shelf(z, h, cfg):
            return False

        return self._supported(pos, dims, cfg)

    def _spans_occupied_shelf(self, z, h, cfg) -> bool:
        """True if the (z, z+h) range straddles a shelf already in use."""
        z_top = z + h
        for sn in range(1, int(self.container.height / self.si) + 1):
            sz = sn * self.si
            if z + 0.5 < sz < z_top - 0.5:
                for p in cfg.placed_products:
                    if abs(p.position[2] - sz) < 0.5:
                        return True
        return False

    def _supported(self, pos, dims, cfg) -> bool:
        x, y, z = pos
        l, w, _ = dims

        if abs(z) < EPS:
            return True  # floor

        sn = round(z / self.si)
        if sn > 0 and abs(z - sn * self.si) < EPS and self._shelf_clear(sn * self.si, cfg):
            return True  # resting on a shelf

        # Stacking on flat tops
        footprint = l * w
        supported = 0.0
        for p in cfg.placed_products:
            if not p.has_flat_top:
                continue
            if abs(p.z_max - z) > SHELF_TOL:
                continue
            ox = max(0.0, min(x + l, p.x_max) - max(x, p.position[0]))
            oy = max(0.0, min(y + w, p.y_max) - max(y, p.position[1]))
            supported += ox * oy

        return supported >= footprint * SUPPORT_THRESHOLD

    def _shelf_clear(self, sz, cfg) -> bool:
        """True if no placed product straddles this shelf height."""
        for p in cfg.placed_products:
            if p.position[2] < sz - 0.5 < p.z_max:
                return False
        return True


# ---------------------------------------------------------------------------
# Multi-container packing
# ---------------------------------------------------------------------------

class MultiContainerSolution:
    """A packing spread across one or more identical roll containers."""

    def __init__(self):
        self.containers: List[PackingConfiguration] = []
        self.unpacked_products: List[Product] = []

    @property
    def total_placed(self) -> int:
        return sum(len(c.placed_products) for c in self.containers)

    @property
    def total_weight(self) -> float:
        return sum(c.total_weight for c in self.containers)

    @property
    def container_count(self) -> int:
        return len(self.containers)

    def average_utilization(self) -> float:
        if not self.containers:
            return 0.0
        return sum(c.get_utilization() for c in self.containers) / len(self.containers)


class MultiContainerPacker:
    """
    Pack products into a sequence of identical roll containers.
    A new container is opened as soon as the current one rejects all
    remaining items. Stops when everything is placed or the cap is hit.
    """

    def __init__(self, container_factory: Callable[[int], RollContainer],
                 max_containers: int = 20):
        self.container_factory = container_factory
        self.max_containers = max_containers

    def pack(self, products: List[Product], verbose: bool = True) -> MultiContainerSolution:
        solution = MultiContainerSolution()
        remaining = list(products)

        while remaining and len(solution.containers) < self.max_containers:
            idx = len(solution.containers) + 1
            container = self.container_factory(idx)
            if verbose:
                print(f"\n--- Container #{idx} ({len(remaining)} candidate items) ---")

            cfg = ProperPackingAlgorithm(container).optimize_packing(remaining, verbose=verbose)

            if not cfg.placed_products:
                # Nothing fit in a fresh container → items are individually too big
                break

            solution.containers.append(cfg)
            remaining = cfg.unpacked_products

        solution.unpacked_products = remaining
        return solution
