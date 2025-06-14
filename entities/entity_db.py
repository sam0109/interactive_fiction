"""Defines the abstract interface for an Entity database."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

# Import the core Entity structure
from entities.entity import Entity


class EntityDatabase(ABC):
    """Abstract base class for storing and retrieving game Entities."""

    @classmethod
    @abstractmethod
    def from_data(cls, entity_data: List[Dict[str, Any]]) -> "EntityDatabase":
        """Creates a database instance from a list of entity data dictionaries."""
        pass

    @classmethod
    @abstractmethod
    def from_directories(cls, directory_paths: List[str]) -> "EntityDatabase":
        """Creates a database instance by loading from JSON files in specified directories."""
        pass

    @abstractmethod
    def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """Retrieves an entity by its unique ID."""
        pass

    @abstractmethod
    def get_all_entities(self) -> List[Entity]:
        """Returns a list of all entities."""
        pass

    @abstractmethod
    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """Returns all entities of a specific type."""
        pass
