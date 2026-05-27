"""
Sample product dataset based on real customer order data.

Each line item declares its package type via the ``unit`` field
(Karton, Kiste, Fass, Tube, ...). The PACKAGING_RULES table below
maps the German keyword to (orientation policy, shape).
"""

from typing import List, Tuple

from product import create_quader, create_cylinder, Product


# ---------------------------------------------------------------------------
# Packaging rules
# ---------------------------------------------------------------------------

PACKAGING_RULES: dict = {
    # any side down, render as cuboid
    "KARTON":    ("any", "cuboid"),
    "BEUTEL":    ("any", "cuboid"),
    "BLOCK":     ("any", "cuboid"),
    "BROTFORM":  ("any", "cuboid"),
    "PACK":      ("any", "cuboid"),
    "ROLLE":     ("any", "cuboid"),
    "PK":        ("any", "cuboid"),
    "RL":        ("any", "cuboid"),

    # bottom only, cuboid
    "BOX":       ("bottom", "cuboid"),
    "CONTAINER": ("bottom", "cuboid"),
    "KANISTER":  ("bottom", "cuboid"),
    "KISTE":     ("bottom", "cuboid"),
    "TR":        ("bottom", "cuboid"),

    # must lie on its side (no standing), cuboid
    "SACK":      ("horizontal_only", "cuboid"),

    # bottom only, cylinder
    "EIMER":     ("bottom", "cylinder"),
    "FA":        ("bottom", "cylinder"),
    "FASS":      ("bottom", "cylinder"),

    # bottom or lying on side, cylinder
    "BUND":      ("bottom_or_side", "cylinder"),
    "DOSE":      ("bottom_or_side", "cylinder"),
    "FL":        ("bottom_or_side", "cylinder"),
    "FLASCHE":   ("bottom_or_side", "cylinder"),
    "GLASS":     ("bottom_or_side", "cylinder"),
    "SCHLAUCH":  ("bottom_or_side", "cylinder"),
    "SPIESS":    ("bottom_or_side", "cylinder"),
    "TUBE":      ("bottom_or_side", "cylinder"),
}

# Source-data oddities: Greek-encoded "KI" → KISTE, German "FAß" → FASS.
UNIT_ALIASES: dict = {
    "KI":  "KISTE",
    "ΚΙ": "KISTE",   # Greek capital Kappa+Iota
    "FAß": "FASS",
}


# ---------------------------------------------------------------------------
# Real customer order (transcribed from production JSON)
# ---------------------------------------------------------------------------

RAW_ORDER: List[dict] = [
    {"desc": "DPG Red Bull 24 x 0,25 l DS",          "code": "9505", "qty": 1,  "unit": "Karton 24 Stk", "dims": "33, 22.5, 14",     "weight": 7.0,  "color": "lightblue"},
    {"desc": "DPG Uludag 24 x 0,33 Dose",            "code": "8900", "qty": 2,  "unit": "Karton 24 Stk", "dims": "35.5, 23, 15",     "weight": 9.0,  "color": "deepskyblue"},
    {"desc": "DPG Mezzo Mix 24 x 0,33 l DS",         "code": "9504", "qty": 2,  "unit": "Karton 24 Stk", "dims": "36, 24, 15",       "weight": 9.0,  "color": "orange"},
    {"desc": "DPG Fanta Lemon 24 x 0,33 l DS",       "code": "9538", "qty": 1,  "unit": "Karton 24 Stk", "dims": "36, 24, 15",       "weight": 9.0,  "color": "yellow"},
    {"desc": "Mezzo Mix 24 x 0,2 l Kiste",           "code": "9585", "qty": 2,  "unit": "ΚΙ 24","dims": "44, 30.5, 27.5",  "weight": 10.0, "color": "chocolate"},
    {"desc": "Vio Medium Apollinaris 18 x 0,51 DPG", "code": "9559", "qty": 1,  "unit": "Karton 18",     "dims": "39, 20, 22.5",     "weight": 12.0, "color": "skyblue"},
    {"desc": "Vio Spritzig 18 x 0,5 l DPG",          "code": "9569", "qty": 2,  "unit": "Karton 18",     "dims": "39, 20, 22.5",     "weight": 12.0, "color": "paleturquoise"},
    {"desc": "FUZE Pfirsich Hibiskus 12 x 0,41 PET", "code": "8923", "qty": 3,  "unit": "TR 12",         "dims": "25, 19, 20",       "weight": 6.0,  "color": "lightcoral"},
    {"desc": "DPG Fanta Cassis 24 x 0,33 DS",        "code": "9508", "qty": 4,  "unit": "Karton 24 Stk", "dims": "36, 24, 15",       "weight": 9.0,  "color": "purple"},
    {"desc": "Krombacher 30 l Fass",                 "code": "9616", "qty": 1,  "unit": "Fass",          "dims": "37, 40",           "weight": 35.0, "color": "gold"},
    {"desc": "Tomaten Ketchup 800 ml Tube",          "code": "9081", "qty": 2,  "unit": "Tube 1",        "dims": "6.5, 29",          "weight": 1.0,  "color": "red"},
    {"desc": "Romi Xtra Frittieroel 15 l KN",        "code": "9700", "qty": 2,  "unit": "Kanister 15 k", "dims": "24.5, 23.5, 32.5", "weight": 14.0, "color": "olive"},
    {"desc": "Farina Pizzamehl Tipo 00 25 kg",       "code": "9941", "qty": 2,  "unit": "Sack 25 kg",    "dims": "56, 32, 14",       "weight": 25.0, "color": "wheat"},
    {"desc": "FABBRI Gourmet-Sauce Haselnuss 950 g", "code": "9544", "qty": 2,  "unit": "Flasche 1",     "dims": "7.5, 25",          "weight": 1.0,  "color": "chocolate"},
    {"desc": "Mondamin Sossenbinder dunkel 1 KG",    "code": "9324", "qty": 1,  "unit": "Pack 1",        "dims": "13, 11.5, 20.5",   "weight": 1.0,  "color": "brown"},
    {"desc": "Kraftbouillon Gemuese 1 KG",           "code": "9306", "qty": 1,  "unit": "Pack 1",        "dims": "13, 11.5, 15",     "weight": 1.0,  "color": "limegreen"},
    {"desc": "Schnellkochnudeln 500 g Long-Life",    "code": "9868", "qty": 10, "unit": "Pack 1",        "dims": "10, 10, 20",       "weight": 0.5,  "color": "beige"},
    {"desc": "Develey Suess Sauer Sauce 875 ml",     "code": "9822", "qty": 2,  "unit": "Tube 1",        "dims": "9.5, 6, 26.5",     "weight": 1.0,  "color": "darkred"},
    {"desc": "Zwiebeln granuliert Hausmarke",        "code": "9311", "qty": 1,  "unit": "Pack 1",        "dims": "30, 19, 5",        "weight": 1.0,  "color": "tan"},
    {"desc": "Ravens. H-Milchreis Natur 1 l",        "code": "9314", "qty": 4,  "unit": "Pack 1",        "dims": "9.5, 6.5, 17",     "weight": 1.0,  "color": "ivory"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CUBOID_ORIENTATIONS = {
    "any":              ["B", "L", "R", "V", "H", "O"],
    "bottom":           ["B"],
    # Sacks must lie flat. Assuming the data follows natural (l, b, h) ordering
    # where h is the smallest dimension, B and O are the lying-flat orientations.
    "horizontal_only":  ["B", "O"],
    "bottom_or_side":   ["B", "L", "R", "V", "H"],
}

_CYLINDER_ORIENTATIONS = {
    "any":              ["B", "M"],
    "bottom":           ["B"],
    "horizontal_only":  ["M"],
    "bottom_or_side":   ["B", "M"],
}


def _orientations(rule: str, shape: str) -> List[str]:
    table = _CYLINDER_ORIENTATIONS if shape == "cylinder" else _CUBOID_ORIENTATIONS
    if rule not in table:
        raise ValueError(f"Unknown orientation rule {rule!r} for shape {shape!r}")
    return list(table[rule])


def _unit_key(unit: str) -> str:
    """Canonical packaging keyword from a unit string (first token, normalised)."""
    if not unit:
        return "KARTON"
    first = unit.strip().split()[0].upper()
    return UNIT_ALIASES.get(first, first)


def _parse_dims(text: str) -> Tuple[float, ...]:
    return tuple(float(p.strip()) for p in text.split(","))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_sample_products() -> List[Product]:
    """Expand RAW_ORDER into individual Product instances (one per unit)."""
    products: List[Product] = []

    for entry in RAW_ORDER:
        key = _unit_key(entry["unit"])
        rule, shape = PACKAGING_RULES.get(key, ("any", "cuboid"))

        dims = _parse_dims(entry["dims"])
        # When the dimension count contradicts the rule, the data wins:
        #   3 dims → cuboid (Develey 'Tube' is actually rectangular);
        #   2 dims → cylinder (diameter, height).
        if len(dims) == 3 and shape == "cylinder":
            shape = "cuboid"
        if len(dims) == 2 and shape == "cuboid":
            shape = "cylinder"
        if len(dims) not in (2, 3):
            raise ValueError(f"Bad dimension string {entry['dims']!r}")

        orientations = _orientations(rule, shape)
        qty = entry["qty"]

        for n in range(qty):
            pid  = entry["code"] if qty == 1 else f"{entry['code']}-{n+1}"
            name = entry["desc"] if qty == 1 else f"{entry['desc']} ({n+1}/{qty})"

            if shape == "cylinder":
                d, h = dims
                products.append(create_cylinder(
                    id=pid, name=name,
                    diameter=d, height=h,
                    allowed_orientations=orientations,
                    weight=entry["weight"], color=entry["color"],
                ))
            else:
                l, b, h = dims
                products.append(create_quader(
                    id=pid, name=name,
                    length=l, width=b, height=h,
                    allowed_orientations=orientations,
                    weight=entry["weight"], color=entry["color"],
                ))

    return products
