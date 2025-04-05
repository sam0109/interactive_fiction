"""Defines the generic Entity data structure."""

from dataclasses import dataclass, field
from typing import Set, Dict, Any, Optional


@dataclass
class Entity:
    """Generic data structure for any entity in the game world."""

    unique_id: str
    entity_type: str  # e.g., "character", "item", "location"
    names: Set[str]
    # Dictionary to hold all other type-specific data
    data: Dict[str, Any] = field(default_factory=dict)
    # Optional field for image path, managed by the loading process
    portrait_image_path: Optional[str] = field(init=False, default=None)

    def __post_init__(self):
        """Basic validation for core fields."""
        if not self.unique_id:
            raise ValueError("Entity unique_id cannot be empty.")
        if not self.entity_type:
            raise ValueError("Entity entity_type cannot be empty.")
        if not self.names:
            # Enforce that names set cannot be empty upon creation
            raise ValueError("Entity names cannot be empty.")
        # Basic type checks
        if not isinstance(self.unique_id, str):
            raise TypeError("Entity unique_id must be a string.")
        if not isinstance(self.entity_type, str):
            raise TypeError("Entity entity_type must be a string.")
        if not isinstance(self.names, set):
            raise TypeError("Entity names must be a set.")
        if not isinstance(self.data, dict):
            raise TypeError("Entity data must be a dictionary.")
