"""
Product models for roll-container packing optimization.

Supports two product types:
- Quader (cuboid): B (Boden/bottom), L (links/left), R (rechts/right), 
                   V (vorne/front), H (hinten/back), O (oben/top)
- Cylinder: B (Boden/bottom), M (Mantel/side), O (oben/top)
"""

from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum
import math


class ProductType(Enum):
    QUADER = "Quader"
    CYLINDER = "Cylinder"


class QuaderOrientation(Enum):
    B = "Boden"      # Bottom
    L = "Links"      # Left
    R = "Rechts"     # Right
    V = "Vorne"      # Front
    H = "Hinten"     # Back
    O = "Oben"       # Top


class CylinderOrientation(Enum):
    B = "Boden"      # Bottom
    M = "Mantel"     # Side/Mantel
    O = "Oben"       # Top


@dataclass
class Product:
    """Base product class with dimensions and orientation constraints."""
    id: str
    name: str
    product_type: ProductType
    dimensions: Tuple[float, float, float]  # (length, width, height) in cm
    allowed_orientations: List[str]  # List of allowed orientation codes
    weight: float = 0.0  # kg
    color: str = None  # For visualization
    fragile: bool = False  # If True, nothing should be stacked on top
    
    def get_oriented_dimensions(self, orientation: str) -> Tuple[float, float, float]:
        """
        Returns (length, width, height) based on orientation.
        
        For Quader (cuboid):
        - Original dimensions are (L, W, H)
        - Different orientations rotate the box
        
        For Cylinder:
        - Original dimensions are (diameter, diameter, height)
        - B/O: standing upright (diameter, diameter, height)
        - M: lying on side (height, diameter, diameter)
        """
        l, w, h = self.dimensions
        
        if self.product_type == ProductType.QUADER:
            # Define rotations for each orientation
            rotations = {
                'B': (l, w, h),      # Bottom down (normal)
                'O': (l, w, h),      # Top down (flipped, same dimensions)
                'L': (h, w, l),      # Left side down
                'R': (h, w, l),      # Right side down
                'V': (l, h, w),      # Front side down
                'H': (l, h, w),      # Back side down
            }
            return rotations.get(orientation, (l, w, h))
        
        elif self.product_type == ProductType.CYLINDER:
            # Cylinder rotations
            if orientation in ['B', 'O']:
                return (l, w, h)  # Standing (diameter, diameter, height)
            elif orientation == 'M':
                return (h, l, w)  # Lying on side (height, diameter, diameter)
        
        return (l, w, h)  # Default
    
    def volume(self) -> float:
        """Calculate product volume in cubic cm."""
        l, w, h = self.dimensions
        if self.product_type == ProductType.CYLINDER:
            radius = l / 2
            return math.pi * radius * radius * h
        return l * w * h
    
    def __repr__(self):
        return f"{self.name} ({self.id}): {self.dimensions} cm, {self.allowed_orientations}"


def create_quader(id: str, name: str, length: float, width: float, height: float, 
                  allowed_orientations: List[str], weight: float = 0.0, 
                  color: str = None, fragile: bool = False) -> Product:
    """Helper function to create a Quader (cuboid) product."""
    return Product(
        id=id,
        name=name,
        product_type=ProductType.QUADER,
        dimensions=(length, width, height),
        allowed_orientations=allowed_orientations,
        weight=weight,
        color=color,
        fragile=fragile
    )


def create_cylinder(id: str, name: str, diameter: float, height: float,
                   allowed_orientations: List[str], weight: float = 0.0,
                   color: str = None, fragile: bool = False) -> Product:
    """Helper function to create a Cylinder product."""
    return Product(
        id=id,
        name=name,
        product_type=ProductType.CYLINDER,
        dimensions=(diameter, diameter, height),
        allowed_orientations=allowed_orientations,
        weight=weight,
        color=color,
        fragile=fragile
    )
