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

from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from product import Product, ProductType, base_code
from container import RollContainer


EPS = 0.01
SHELF_TOL = 0.1

# Same-code adjacency bonus per touching face — large enough to dominate
# the wall/contact terms when breaking ties between equal-top positions.
SAME_CODE_FACE_BONUS = 1000.0


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
        """
        Make the step sequence reflect how a worker would actually load the
        container:

          - Same-code units stay contiguous (worker processes one article at
            a time — already true from ``_pack``).
          - Within a code, units are emitted bottom-up by z.
          - **Across codes, the algorithm's placement order is preserved.**
            That order is dependency-respecting by construction (each unit
            was validly supported by something already placed when it was
            added), so every visualisation step is physically possible.

        Sorting codes by min-z across the sequence is tempting but unsafe: if
        code A was placed second and a unit of A stacks on a unit of code B
        placed first, swapping A before B (because A has a floor unit) would
        make that high A unit float in the step view until B catches up.
        """
        seen: "OrderedDict[str, None]" = OrderedDict()
        for p in self.placed_products:
            seen.setdefault(base_code(p.product.id), None)

        buckets: "defaultdict[str, list[PlacedProduct]]" = defaultdict(list)
        for p in self.placed_products:
            buckets[base_code(p.product.id)].append(p)

        for code in buckets:
            buckets[code].sort(key=lambda p: (
                round(p.position[2], 2),
                round(p.position[1], 2),
                round(p.position[0], 2),
            ))

        self.placed_products = [p for code in seen for p in buckets[code]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_isolated_units(cfg: "PackingConfiguration") -> int:
    """
    Count units that should cluster with same-code siblings but don't share
    any face with one. Used as a strategy tiebreaker — lower is better.
    Singletons (group size 1) are ignored.
    """
    groups: "defaultdict[str, list[PlacedProduct]]" = defaultdict(list)
    for p in cfg.placed_products:
        groups[base_code(p.product.id)].append(p)

    isolated = 0
    for items in groups.values():
        if len(items) < 2:
            continue
        for i, p in enumerate(items):
            x, y, z = p.position
            x2, y2, z2 = p.x_max, p.y_max, p.z_max
            touches = False
            for j, q in enumerate(items):
                if i == j:
                    continue
                qx, qy, qz = q.position
                qmx, qmy, qmz = q.x_max, q.y_max, q.z_max
                x_face = abs(x2 - qx) < SHELF_TOL or abs(qmx - x) < SHELF_TOL
                y_face = abs(y2 - qy) < SHELF_TOL or abs(qmy - y) < SHELF_TOL
                z_face = abs(z2 - qz) < SHELF_TOL or abs(qmz - z) < SHELF_TOL
                if x_face and max(y, qy) < min(y2, qmy) and max(z, qz) < min(z2, qmz):
                    touches = True; break
                if y_face and max(x, qx) < min(x2, qmx) and max(z, qz) < min(z2, qmz):
                    touches = True; break
                if z_face and max(x, qx) < min(x2, qmx) and max(y, qy) < min(y2, qmy):
                    touches = True; break
            if not touches:
                isolated += 1
    return isolated


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
    def _all_variants(product: Product) -> List[Tuple[str, Tuple[float, float, float]]]:
        """Every unique (orientation_code, dims) including 90° rotation about z."""
        seen, out = set(), []
        for o in product.allowed_orientations:
            l, w, h = product.get_oriented_dimensions(o)
            for d in ((l, w, h), (w, l, h)):
                key = (round(d[0], 2), round(d[1], 2), round(d[2], 2))
                if key not in seen:
                    seen.add(key)
                    out.append((o, d))
        return out

    def _orientation_variants(self, product: Product,
                              cfg: Optional["PackingConfiguration"] = None,
                              prefer_code: Optional[str] = None
                              ) -> List[Tuple[str, Tuple[float, float, float]]]:
        """
        Variants to try for this product. If we already have same-code units
        placed, restrict to the *exact* dims those siblings are using — same
        article ⇒ same shape, so faces line up cleanly when clustering.
        """
        all_vars = self._all_variants(product)
        if cfg is None or not prefer_code:
            return all_vars
        used_dims = {
            tuple(round(v, 2) for v in p.dimensions)
            for p in cfg.placed_products
            if base_code(p.product.id) == prefer_code
        }
        if not used_dims:
            return all_vars
        restricted = [(o, d) for o, d in all_vars
                      if tuple(round(v, 2) for v in d) in used_dims]
        return restricted or all_vars  # fall back if nothing matches

    # ----- sort strategies -----------------------------------------------------

    @staticmethod
    def _sort_strategies(counts: dict) -> List[Tuple[str, Callable[[Product], object], bool]]:
        """
        Strategies sort *individual products*; since same-code units share
        every per-product attribute, this is equivalent to sorting code groups.
        ``counts`` maps base code → number of units, enabling group-aware
        strategies that put the biggest groups first.
        """
        def gc(p):  # group count for this product's code
            return counts[base_code(p.id)]
        return [
            ("total_volume_desc", lambda p: gc(p) * p.volume(),                        True),
            ("group_count_desc",  lambda p: (gc(p), p.volume()),                       True),
            ("volume_desc",       lambda p: p.volume(),                                True),
            ("footprint_desc",    lambda p: p.dimensions[0] * p.dimensions[1],         True),
            ("height_desc",       lambda p: p.dimensions[2],                           True),
            ("heavy_bottom",      lambda p: (-p.weight, -p.volume()),                  False),
            ("fragile_first",     lambda p: (0 if p.fragile else 1, -p.volume()),      False),
        ]

    # ----- public API ----------------------------------------------------------

    def optimize_packing(self, products: List[Product], verbose: bool = True) -> PackingConfiguration:
        best_cfg: Optional[PackingConfiguration] = None
        best_score = (-1, -1, -1.0)  # (placed, -isolated, util)
        best_name = ""

        counts: dict = defaultdict(int)
        for p in products:
            counts[base_code(p.id)] += 1

        for name, key_fn, rev in self._sort_strategies(counts):
            cfg = self._pack(sorted(products, key=key_fn, reverse=rev))
            isolated = _count_isolated_units(cfg)
            score = (len(cfg.placed_products), -isolated, cfg.get_utilization())
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
        """
        Pack products into the container, processing one *code group* at a time.

        All units of the same base code are placed back-to-back; within a group
        each unit prefers a position adjacent to its already-placed siblings.
        The order of code groups is determined by the order of the input list
        (which the caller has sorted by some strategy).
        """
        cfg = PackingConfiguration(self.container)

        # Group products by base code, preserving first-occurrence order.
        groups: "OrderedDict[str, List[Product]]" = OrderedDict()
        for p in products:
            groups.setdefault(base_code(p.id), []).append(p)

        queue = [(code, list(units)) for code, units in groups.items()]
        while True:
            any_progress = False
            next_queue = []
            for code, units in queue:
                # First choice: place the entire code as one dense block.
                # Real packers stack identical boxes in a regular grid.
                if len(units) >= 2 and self._try_block_placement(units, cfg):
                    any_progress = True
                    continue
                # Fallback: place each unit individually (strict-touch search).
                still_units = []
                for unit in units:
                    pl = self._find_best(unit, cfg, prefer_code=code)
                    if pl and cfg.add(pl):
                        any_progress = True
                    else:
                        still_units.append(unit)
                if still_units:
                    next_queue.append((code, still_units))
            queue = next_queue
            if not any_progress:
                break

        cfg.unpacked_products = [u for _, units in queue for u in units]
        return cfg

    # ----- block placement -----------------------------------------------------

    @staticmethod
    def _decompositions(n: int) -> List[Tuple[int, int, int]]:
        """All (cols, rows, layers) with cols*rows*layers == n."""
        out = []
        for layers in range(1, n + 1):
            if n % layers != 0:
                continue
            per_layer = n // layers
            for cols in range(1, per_layer + 1):
                if per_layer % cols == 0:
                    rows = per_layer // cols
                    out.append((cols, rows, layers))
        return out

    def _try_block_placement(self, units: List[Product], cfg: PackingConfiguration) -> bool:
        """
        Try to place every unit as a single dense block (cols × rows × layers
        grid of identical units, all in the same orientation). Returns True
        iff all units were placed.
        """
        n = len(units)
        product = units[0]
        cL, cW, cH = self.container.length, self.container.width, self.container.height
        decomps = self._decompositions(n)
        fragile = product.fragile

        best_key = None
        best_layout = None

        # Common z-level menu (block-friendly): floor, clear shelves, flat tops.
        z_menu = [0.0]
        for k in range(1, int(cH / self.si) + 1):
            sz = k * self.si
            if sz + min(p.dimensions[2] for p in [product]) > cH + EPS:
                # We don't yet know which orientation; just include and prune later.
                pass
            if any(p.position[2] < sz - 0.5 < p.z_max for p in cfg.placed_products):
                continue
            z_menu.append(sz)
        for p in cfg.placed_products:
            if p.has_flat_top:
                z_menu.append(round(p.z_max, 2))
        z_menu = sorted(set(z_menu))

        for orient, (ul, uw, uh) in self._all_variants(product):
            # Multi-layer blocks need each unit's top to support the one above.
            # Cylinders in 'M' orientation and fragile units have no flat top.
            orient_has_flat_top = not fragile and not (
                product.product_type == ProductType.CYLINDER and orient == 'M'
            )
            for cols, rows, layers in decomps:
                if layers > 1 and not orient_has_flat_top:
                    continue
                bL, bW, bH = cols * ul, rows * uw, layers * uh
                if bL > cL + EPS or bW > cW + EPS or bH > cH + EPS:
                    continue

                # Lower z always yields a lower top for this layout, so as soon
                # as we find ANY valid placement at some z we don't search z
                # values above it for the same (orient, decomp).
                found_for_layout = False
                for bz in z_menu:
                    if bz + bH > cH + EPS:
                        break
                    # Early prune: if we already have a global best whose top
                    # is < bz + bH, this layout/z combo can't improve it.
                    if best_key is not None and round(bz + bH, 2) > best_key[0]:
                        break
                    if fragile and bz > SHELF_TOL:
                        sn = round(bz / self.si)
                        if abs(bz - sn * self.si) > SHELF_TOL:
                            continue
                    for bx, by in self._block_candidates(bL, bW, cfg):
                        if not self._block_fits(bx, by, bz, bL, bW, bH, cfg):
                            continue
                        if not self._block_supported(bx, by, bz, bL, bW, cfg):
                            continue
                        top = bz + bH
                        score = self._block_score(bx, by, bL, bW, cfg)
                        key = (round(top, 2), score, abs(cols - rows) + abs(rows - layers))
                        if best_key is None or key < best_key:
                            best_key = key
                            best_layout = (orient, ul, uw, uh, cols, rows, layers, bx, by, bz)
                            found_for_layout = True
                    if found_for_layout:
                        break  # higher z only makes top larger for same layout

        if best_layout is None:
            return False

        orient, ul, uw, uh, cols, rows, layers, bx, by, bz = best_layout
        # Place units bottom-up, row-by-row, col-by-col so step order is buildable.
        idx = 0
        for layer in range(layers):
            for row in range(rows):
                for col in range(cols):
                    if idx >= n:
                        return True
                    pos = (bx + col * ul, by + row * uw, bz + layer * uh)
                    pl = PlacedProduct(product=units[idx], orientation=orient,
                                       position=pos, dimensions=(ul, uw, uh))
                    if not cfg.add(pl):
                        # Validations passed, this should never fail — but bail
                        # out cleanly rather than corrupt state.
                        return False
                    idx += 1
        return True

    def _block_candidates(self, bL: float, bW: float, cfg: PackingConfiguration
                          ) -> List[Tuple[float, float]]:
        cL, cW = self.container.length, self.container.width
        seen, out = set(), []

        def add(x: float, y: float) -> None:
            if x < -EPS or y < -EPS or x + bL > cL + EPS or y + bW > cW + EPS:
                return
            x = max(0.0, x); y = max(0.0, y)
            k = (round(x, 1), round(y, 1))
            if k in seen:
                return
            seen.add(k)
            out.append((x, y))

        add(0, 0); add(cL - bL, 0); add(0, cW - bW); add(cL - bL, cW - bW)
        for p in cfg.placed_products:
            px, py = p.position[0], p.position[1]
            pmx, pmy = p.x_max, p.y_max
            # Touch any face of an existing product, against any wall, or against
            # another product's corner. No coarse grid — for a packer block these
            # touching/wall-aligned positions are the natural anchor points.
            add(pmx, py);          add(px, pmy);    add(pmx, pmy);   add(px, py)
            add(px - bL, py);      add(px - bL, pmy)
            add(px, py - bW);      add(pmx, py - bW)
            add(pmx, 0);           add(0, pmy)
            add(px - bL, 0);       add(0, py - bW)
            add(pmx, cW - bW);     add(cL - bL, pmy)
        return out

    def _block_fits(self, bx, by, bz, bL, bW, bH, cfg) -> bool:
        x_max, y_max, z_max = bx + bL, by + bW, bz + bH
        if x_max > self.container.length + EPS or y_max > self.container.width + EPS \
           or z_max > self.container.height + EPS:
            return False
        for p in cfg.placed_products:
            if (bx < p.x_max - EPS and x_max > p.position[0] + EPS and
                by < p.y_max - EPS and y_max > p.position[1] + EPS and
                bz < p.z_max - EPS and z_max > p.position[2] + EPS):
                return False
        # No spanning an installed shelf
        for k in range(1, int(self.container.height / self.si) + 1):
            sz = k * self.si
            if bz + 0.5 < sz < z_max - 0.5:
                for p in cfg.placed_products:
                    if abs(p.position[2] - sz) < 0.5:
                        return False
        return True

    def _block_supported(self, bx, by, bz, bL, bW, cfg) -> bool:
        if abs(bz) < EPS:
            return True
        sn = round(bz / self.si)
        if sn > 0 and abs(bz - sn * self.si) < EPS:
            sz = sn * self.si
            if not any(p.position[2] < sz - 0.5 < p.z_max for p in cfg.placed_products):
                return True
        supports = [(p.position[0], p.position[1], p.x_max, p.y_max)
                    for p in cfg.placed_products
                    if p.has_flat_top and abs(p.z_max - bz) < SHELF_TOL]
        if not supports:
            return False
        return self._rect_fully_covered(bx, by, bx + bL, by + bW, supports)

    def _block_score(self, bx, by, bL, bW, cfg) -> float:
        cL, cW = self.container.length, self.container.width
        walls = sum([bx < SHELF_TOL, by < SHELF_TOL,
                     abs(bx + bL - cL) < SHELF_TOL,
                     abs(by + bW - cW) < SHELF_TOL])
        contact = 0
        for p in cfg.placed_products:
            if abs(bx + bL - p.position[0]) < SHELF_TOL or abs(p.x_max - bx) < SHELF_TOL:
                contact += 1
            if abs(by + bW - p.position[1]) < SHELF_TOL or abs(p.y_max - by) < SHELF_TOL:
                contact += 1
        return by * 2 + bx - walls * 100 - contact * 40

    # ----- lowest-point search -------------------------------------------------

    def _find_best(self, product: Product, cfg: PackingConfiguration,
                   prefer_code: Optional[str] = None) -> Optional[PlacedProduct]:
        """
        Find the best placement for ``product``.

        If ``prefer_code`` is given AND at least one same-code product is
        already placed, a strict-touch pass runs first — the new unit must
        share a face with an existing same-code sibling. Only if no valid
        touching position exists do we fall back to an unconstrained search.
        """
        has_siblings = bool(prefer_code) and any(
            base_code(p.product.id) == prefer_code for p in cfg.placed_products
        )
        if has_siblings:
            touching = self._search(product, cfg, prefer_code, require_touch=True)
            if touching is not None:
                return touching
        return self._search(product, cfg, prefer_code, require_touch=False)

    def _search(self, product: Product, cfg: PackingConfiguration,
                prefer_code: Optional[str], require_touch: bool) -> Optional[PlacedProduct]:
        z_levels = self._z_levels(cfg)
        best: Optional[PlacedProduct] = None
        best_top = float('inf')
        best_score = float('inf')

        for z in z_levels:
            if z >= best_top:
                break  # any deeper z can only make ztop larger

            for orient, dims in self._orientation_variants(product, cfg, prefer_code):
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
                    if require_touch and not self._touches_same_code(pos, dims, cfg, prefer_code):
                        continue
                    sc = self._score(pos, dims, cfg, prefer_code=prefer_code)
                    top_r = round(ztop, 2)
                    if top_r < best_top or (top_r == best_top and sc < best_score):
                        best_top, best_score = top_r, sc
                        best = PlacedProduct(product=product, orientation=orient,
                                             position=pos, dimensions=dims)
        return best

    def _touches_same_code(self, pos, dims, cfg, prefer_code: Optional[str]) -> bool:
        """True if a placement at ``pos`` would share a face with any same-code product."""
        if not prefer_code:
            return False
        x, y, z = pos
        l, w, h = dims
        x_max, y_max, z_max = x + l, y + w, z + h
        for p in cfg.placed_products:
            if base_code(p.product.id) != prefer_code:
                continue
            px, py, pz = p.position
            pmx, pmy, pmz = p.x_max, p.y_max, p.z_max
            # X face (need overlap in y and z, touch on x)
            if abs(x_max - px) < SHELF_TOL or abs(pmx - x) < SHELF_TOL:
                if max(y, py) < min(y_max, pmy) and max(z, pz) < min(z_max, pmz):
                    return True
            # Y face
            if abs(y_max - py) < SHELF_TOL or abs(pmy - y) < SHELF_TOL:
                if max(x, px) < min(x_max, pmx) and max(z, pz) < min(z_max, pmz):
                    return True
            # Z face (stacking)
            if abs(z_max - pz) < SHELF_TOL or abs(pmz - z) < SHELF_TOL:
                if max(x, px) < min(x_max, pmx) and max(y, py) < min(y_max, pmy):
                    return True
        return False

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

        # Extreme points from placed products — touching positions on all
        # four horizontal faces of every placed item (right, left, front, back)
        # plus combinations against walls and other items' corners.
        for p in cfg.placed_products:
            px, py = p.position[0], p.position[1]
            pmx, pmy = p.x_max, p.y_max
            # Touch p's right / front / corner / origin
            add(pmx, py);          add(px, pmy);    add(pmx, pmy);   add(px, py)
            # Touch p's left face (new's right edge meets p's left)
            add(px - l, py);       add(px - l, pmy);  add(px - l, py - w)
            # Touch p's back face (new's top edge meets p's bottom)
            add(px, py - w);       add(pmx, py - w)
            # Wall-aligned variants
            add(pmx, 0);           add(0, pmy)
            add(pmx, cW - w);      add(cL - l, pmy)
            add(px - l, 0);        add(0, py - w)
            add(px - l, cW - w);   add(cL - l, py - w)

        # Coarse fallback grid (5 cm) — catches positions extreme points miss
        for x in range(0, int(cL - l) + 1, 5):
            for y in range(0, int(cW - w) + 1, 5):
                add(float(x), float(y))

        out.sort(key=lambda c: (c[1], c[0]))
        return out

    # ----- scoring (lower is better) ------------------------------------------

    def _score(self, pos, dims, cfg, prefer_code: Optional[str] = None) -> float:
        x, y, z = pos
        l, w, h = dims
        cL, cW = self.container.length, self.container.width

        walls = sum([x < SHELF_TOL,
                     y < SHELF_TOL,
                     abs(x + l - cL) < SHELF_TOL,
                     abs(y + w - cW) < SHELF_TOL])

        contact = 0
        same_faces = 0
        same_dist_sum = 0.0
        same_count = 0

        for p in cfg.placed_products:
            px, py, pz = p.position
            pmx, pmy, pmz = p.x_max, p.y_max, p.z_max
            is_same = bool(prefer_code) and base_code(p.product.id) == prefer_code

            # Side-face adjacency (overlapping in z)
            if max(z, pz) < min(z + h, pmz):
                x_adj = abs(x + l - px) < SHELF_TOL or abs(pmx - x) < SHELF_TOL
                y_adj = abs(y + w - py) < SHELF_TOL or abs(pmy - y) < SHELF_TOL
                if x_adj and max(y, py) < min(y + w, pmy):
                    contact += 1
                    if is_same:
                        same_faces += 1
                if y_adj and max(x, px) < min(x + l, pmx):
                    contact += 1
                    if is_same:
                        same_faces += 1

            # Top-/bottom-face adjacency for same-code (stacked clones)
            if is_same and (abs(z - pmz) < SHELF_TOL or abs(pz - (z + h)) < SHELF_TOL):
                ox = max(0.0, min(x + l, pmx) - max(x, px))
                oy = max(0.0, min(y + w, pmy) - max(y, py))
                if ox > EPS and oy > EPS:
                    same_faces += 1

            # Manhattan distance between centres of mass (for proximity tiebreak)
            if is_same:
                same_count += 1
                cx_p, cy_p, cz_p = x + l / 2, y + w / 2, z + h / 2
                ocx = px + p.dimensions[0] / 2
                ocy = py + p.dimensions[1] / 2
                ocz = pz + p.dimensions[2] / 2
                same_dist_sum += abs(cx_p - ocx) + abs(cy_p - ocy) + abs(cz_p - ocz)

        avg_same_dist = (same_dist_sum / same_count) if same_count else 0.0

        return (y * 2 + x
                - walls * 60
                - contact * 40
                - same_faces * SAME_CODE_FACE_BONUS
                + avg_same_dist * 2.0)

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

        # Stacking on flat tops — FULL FOOTPRINT COVERAGE.
        # The product's entire bottom face must lie over the union of flat
        # tops at this z. No overhang past any support edge is permitted.
        # Supports may abut so a long product is allowed to bridge several
        # smaller items as long as they form a contiguous covering surface.
        supports = []
        for p in cfg.placed_products:
            if not p.has_flat_top:
                continue
            if abs(p.z_max - z) > SHELF_TOL:
                continue
            supports.append((p.position[0], p.position[1], p.x_max, p.y_max))
        if not supports:
            return False
        return self._rect_fully_covered(x, y, x + l, y + w, supports)

    @staticmethod
    def _rect_fully_covered(x1, y1, x2, y2, supports) -> bool:
        """
        True iff the axis-aligned rectangle (x1,y1)-(x2,y2) is fully covered
        by the union of ``supports`` (each ``(sx1, sy1, sx2, sy2)``).
        Uses coordinate compression — every cell of the induced grid inside
        the target rect must lie in at least one support.
        """
        xs_set = {x1, x2}
        ys_set = {y1, y2}
        for sx1, sy1, sx2, sy2 in supports:
            if sx1 < x2 - EPS and sx2 > x1 + EPS:
                xs_set.add(max(x1, sx1))
                xs_set.add(min(x2, sx2))
            if sy1 < y2 - EPS and sy2 > y1 + EPS:
                ys_set.add(max(y1, sy1))
                ys_set.add(min(y2, sy2))
        xs = sorted(xs_set)
        ys = sorted(ys_set)
        for i in range(len(xs) - 1):
            if xs[i + 1] - xs[i] < EPS:
                continue
            cx = (xs[i] + xs[i + 1]) / 2
            for j in range(len(ys) - 1):
                if ys[j + 1] - ys[j] < EPS:
                    continue
                cy = (ys[j] + ys[j + 1]) / 2
                covered = False
                for sx1, sy1, sx2, sy2 in supports:
                    if (sx1 - EPS <= cx <= sx2 + EPS and
                        sy1 - EPS <= cy <= sy2 + EPS):
                        covered = True
                        break
                if not covered:
                    return False
        return True

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
