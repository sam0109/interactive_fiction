"""Defines the Item database interface and data structures."""

from abc import ABC, abstractmethod
from typing import List, Set, Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class Item:
    """Data structure representing an item in the game."""

    unique_id: str  # Internal, unique identifier (e.g., "rusty_dagger_01")
    names: Set[
        str
    ]  # Set of names the item might be known by (e.g., {"Rusty Dagger", "Dagger"})
    description: str  # Text description shown to the player.
    properties: Dict[str, Any] = field(
        default_factory=dict
    )  # Arbitrary properties (weight, type, tags etc.)

    def __post_init__(self):
        """Validate required fields after initialization."""
        if not self.unique_id:
            raise ValueError("Item unique_id cannot be empty.")
        if not self.names:
            raise ValueError("Item names cannot be empty.")
        if not self.description:
            raise ValueError("Item description cannot be empty.")


class ItemDatabase(ABC):
    """Abstract base class defining the interface for an item database.

    Responsibilities:
    - Loading initial item definitions.
    - Storing and retrieving Item objects.
    """

    @classmethod
    @abstractmethod
    def get_from_data(cls, item_data: List[Dict]) -> "ItemDatabase":
        """Creates a database instance from a list of item data dictionaries.

        Args:
            item_data: A list where each element is a dictionary conforming
                       to the expected item JSON structure.

        Returns:
            An instance of the ItemDatabase populated with the provided data.

        Raises:
            ValueError: If any dictionary in the list is invalid.
        """
        pass

    @abstractmethod
    def get_item_by_name(self, name: str) -> Optional[Item]:
        """Finds an item using a potentially fuzzy name lookup.

        Args:
            name: The name (or partial name/alias) to search for.

        Returns:
            The matching Item object, or None if no suitable match is found.
        """
        pass

    @abstractmethod
    def get_item_by_id(self, item_id: str) -> Optional[Item]:
        """Retrieves an item directly by its unique ID.

        Args:
            item_id: The unique identifier of the item.

        Returns:
            The Item object, or None if the ID is not found.
        """
        pass

    @abstractmethod
    def get_all_items(self) -> List[Item]:
        """Returns a list of all items currently loaded in the database."""
        pass
