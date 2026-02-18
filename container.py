"""
Roll-container model for the packing optimization system.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class RollContainer:
    """Represents a roll container with specific dimensions."""
    length: float  # cm (depth)
    width: float   # cm
    height: float  # cm
    max_weight: float = 300.0  # kg (default max capacity)
    name: str = "Roll Container"
    shelf_interval: float = 20.0  # cm - shelves can be placed every 20cm
    
    def volume(self) -> float:
        """Calculate container volume in cubic cm."""
        return self.length * self.width * self.height
    
    def volume_liters(self) -> float:
        """Calculate container volume in liters."""
        return self.volume() / 1000.0
    
    def __repr__(self):
        return (f"{self.name}: {self.length}×{self.width}×{self.height} cm, "
                f"Vol: {self.volume_liters():.1f}L, Max: {self.max_weight}kg")


# Standard roll container: 100cm x 80cm x 170cm with 20cm shelf intervals
STANDARD_ROLL_CONTAINER = RollContainer(
    length=100, width=80, height=170,
    max_weight=300, name="Standard Roll Container"
)
