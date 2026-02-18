"""Sample product dataset for the tetris packing demo."""

from product import create_quader, create_cylinder, Product
from typing import List


def create_sample_products() -> List[Product]:
    """
    Create a sample product dataset for testing.
    
    Includes mix of:
    - Heavy base items (stackable)
    - Fragile items (flat, bottom-only orientation)
    - Medium items (flexible orientations)
    - Small items (gap fillers)
    """
    
    products = [
        # Beverage crates (Quader - boxes)
        create_quader(
            id="BEV001",
            name="Water Crate 6x1.5L",
            length=40, width=30, height=25,
            allowed_orientations=['B', 'O'],  # Only bottom or top down
            weight=10.5,
            color='lightblue'
        ),
        
        create_quader(
            id="BEV002",
            name="Juice Box 12x1L",
            length=35, width=25, height=30,
            allowed_orientations=['B', 'O'],
            weight=13.2,
            color='orange'
        ),
        
        create_quader(
            id="BEV003",
            name="Soda Crate 24x0.5L",
            length=38, width=28, height=22,
            allowed_orientations=['B', 'O'],
            weight=13.0,
            color='deepskyblue'
        ),
        
        # Bread crates (FRAGILE - nothing should be stacked on top)
        create_quader(
            id="BREAD001",
            name="Bread Crate Large",
            length=60, width=40, height=15,
            allowed_orientations=['B'],  # Only bottom down (fragile)
            weight=5.0,
            color='wheat',
            fragile=True
        ),
        
        create_quader(
            id="BREAD002",
            name="Bread Crate Small",
            length=40, width=30, height=15,
            allowed_orientations=['B'],
            weight=3.5,
            color='tan',
            fragile=True
        ),
        
        create_quader(
            id="BREAD003",
            name="Baguette Tray",
            length=65, width=35, height=12,
            allowed_orientations=['B'],
            weight=4.0,
            color='burlywood',
            fragile=True
        ),
        
        # Vegetable crates (FRAGILE - tomatoes are delicate)
        create_quader(
            id="VEG001",
            name="Tomato Crate",
            length=50, width=30, height=20,
            allowed_orientations=['B'],  # Only bottom (fragile)
            weight=8.0,
            color='red',
            fragile=True
        ),
        
        create_quader(
            id="VEG002",
            name="Potato Bag Box",
            length=40, width=30, height=30,
            allowed_orientations=['B', 'L', 'R', 'V', 'H'],  # Multiple orientations OK
            weight=12.0,
            color='brown'
        ),
        
        create_quader(
            id="VEG003",
            name="Lettuce Crate",
            length=45, width=35, height=18,
            allowed_orientations=['B'],
            weight=6.5,
            color='limegreen',
            fragile=True
        ),
        
        # Dairy products
        create_quader(
            id="DAIRY001",
            name="Milk Crate 4x2L",
            length=30, width=25, height=28,
            allowed_orientations=['B', 'O'],
            weight=9.0,
            color='white'
        ),
        
        create_quader(
            id="DAIRY002",
            name="Yogurt Box 24x150g",
            length=35, width=28, height=20,
            allowed_orientations=['B'],
            weight=4.5,
            color='lavender',
            fragile=True  # Yogurt cups are fragile
        ),
        
        # Cylindrical products - Liquids
        create_cylinder(
            id="CYL001",
            name="Oil Drum 5L",
            diameter=20, height=35,
            allowed_orientations=['B', 'O'],  # Standing only
            weight=4.5,
            color='yellow'
        ),
        
        create_cylinder(
            id="CYL002",
            name="Sauce Container 10L",
            diameter=25, height=40,
            allowed_orientations=['B', 'O', 'M'],  # Can lie on side
            weight=11.0,
            color='darkred'
        ),
        
        create_cylinder(
            id="CYL003",
            name="Vinegar Barrel 8L",
            diameter=22, height=38,
            allowed_orientations=['B', 'O'],
            weight=8.5,
            color='olive'
        ),
        
        create_cylinder(
            id="CYL004",
            name="Syrup Keg 15L",
            diameter=28, height=45,
            allowed_orientations=['B', 'O', 'M'],
            weight=16.0,
            color='chocolate'
        ),
        
        create_cylinder(
            id="CYL005",
            name="Wine Cask 5L",
            diameter=18, height=30,
            allowed_orientations=['B', 'O'],
            weight=5.5,
            color='maroon'
        ),
        
        # Small items
        create_quader(
            id="SMALL001",
            name="Spice Box",
            length=20, width=15, height=10,
            allowed_orientations=['B', 'L', 'R', 'V', 'H', 'O'],  # Any orientation
            weight=2.0,
            color='green'
        ),
        
        create_quader(
            id="SMALL002",
            name="Herb Pack",
            length=25, width=20, height=8,
            allowed_orientations=['B'],  # Only bottom
            weight=1.5,
            color='lightgreen'
        ),
        
        create_quader(
            id="SMALL003",
            name="Condiment Box",
            length=22, width=18, height=12,
            allowed_orientations=['B', 'O'],
            weight=2.5,
            color='darkgreen'
        ),
        
        # Large boxes
        create_quader(
            id="LARGE001",
            name="Cereal Master Case",
            length=50, width=35, height=40,
            allowed_orientations=['B', 'L', 'R'],
            weight=8.5,
            color='gold'
        ),
        
        create_quader(
            id="LARGE002",
            name="Pasta Case",
            length=45, width=30, height=25,
            allowed_orientations=['B', 'L', 'R', 'V', 'H'],
            weight=6.0,
            color='beige'
        ),
        
        create_quader(
            id="LARGE003",
            name="Rice Bag Box",
            length=48, width=32, height=28,
            allowed_orientations=['B', 'L', 'R'],
            weight=10.0,
            color='ivory'
        ),
        
        # Frozen goods
        create_quader(
            id="FROZEN001",
            name="Ice Cream Box",
            length=42, width=32, height=24,
            allowed_orientations=['B'],
            weight=7.5,
            color='lightcyan'
        ),
        
        create_quader(
            id="FROZEN002",
            name="Frozen Veg Case",
            length=38, width=28, height=20,
            allowed_orientations=['B', 'O'],
            weight=9.5,
            color='paleturquoise'
        ),
    ]
    
    return products
