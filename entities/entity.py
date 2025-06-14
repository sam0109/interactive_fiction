"""
This module defines the core Entity class, a fundamental data structure
representing any object, character, or location in the game world.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Set


@dataclass
class Entity:
    """
    Represents a single entity in the game world.

    This class holds the "ground truth" for an entity. All data stored here is
    considered objective reality within the game. What characters *know* about
    this entity is managed separately by the KnowledgeManager.

    Attributes:
        unique_id: A unique identifier for the entity (e.g., "player", "rusty_key_01").
        entity_type: The type of the entity (e.g., "character", "item", "location").
        data: A dictionary containing the objective facts and properties of the entity.
        portrait_image_path: An optional path to a portrait image for the entity.
    """
    unique_id: str
    entity_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    portrait_image_path: Optional[str] = None
