"""Defines the Character database interface and data structures."""

from abc import ABC, abstractmethod
from typing import List, Set, Optional, Dict, Union
from dataclasses import dataclass, field

# Type alias for possessions: Simple strings for now, but could become IDs
PossessionType = str  # Union[str, int] # Example if we used item IDs later

# Type alias for inventory structure
InventoryType = Dict[str, Union[int, Dict[str, int]]]


@dataclass
class Character:
    """Data structure representing a character in the game."""

    unique_id: str  # Internal, unique identifier (e.g., "guard_01")
    # Set of names the character might be known by (e.g., {"Gareth", "Guard"})
    names: Set[str]
    # Static data loaded from file
    # Facts known publicly (e.g., description)
    public_facts: Dict[str, str] = field(default_factory=dict)
    private_facts: Dict[str, str] = field(
        default_factory=dict
    )  # Facts known only to the character

    # Dynamic state - single source of truth for possessions
    # Initialized by the loading process before being passed to __init__
    inventory: InventoryType = field(default_factory=lambda: {"money": 0, "items": {}})

    # Optional path to the character's portrait image
    portrait_image_path: Optional[str] = field(init=False, default=None)

    def __post_init__(self):
        """Validate required fields after initialization."""
        # Inventory initialization is now handled *before* calling __init__
        if not self.unique_id:
            raise ValueError("Character unique_id cannot be empty.")
        if not self.names:
            raise ValueError("Character names cannot be empty.")
        if (
            "description" not in self.public_facts
            or not self.public_facts["description"]
        ):
            raise ValueError(
                "Character must have a non-empty 'description' in public_facts."
            )
        if (
            "internal_description" not in self.private_facts
            or not self.private_facts["internal_description"]
        ):
            raise ValueError(
                "Character must have a non-empty 'internal_description' in "
                "private_facts."
            )


class CharacterDatabase(ABC):
    """Abstract base class defining the interface for a character database.

    Responsibilities:
    - Loading initial character definitions.
    - Storing and retrieving Character objects.
    """

    @classmethod
    @abstractmethod
    def from_data(cls, character_data: List[Dict]) -> "CharacterDatabase":
        """Creates a database instance from a list of character data dictionaries.

        Args:
            character_data: A list where each element is a dictionary conforming
                            to the expected character JSON structure.

        Returns:
            An instance of the CharacterDatabase populated with the provided data.

        Raises:
            ValueError: If any dictionary in the list is invalid.
        """
        pass

    @abstractmethod
    def get_character_by_name(self, name: str) -> Optional[Character]:
        """Finds a character using a potentially fuzzy name lookup.

        Args:
            name: The name (or partial name/alias) to search for.

        Returns:
            The matching Character object, or None if no suitable match is found.
        """
        pass

    @abstractmethod
    def get_character_by_id(self, character_id: str) -> Optional[Character]:
        """Retrieves a character directly by their unique ID.

        Args:
            character_id: The unique identifier of the character.

        Returns:
            The Character object, or None if the ID is not found.
        """
        pass

    @abstractmethod
    def get_all_characters(self) -> List[Character]:
        """Returns a list of all characters currently loaded in the database."""
        pass


# Interface simplified: Removed get_character_possessions, get_character_public_facts,
# get_character_private_facts, get_character_inventory, update_character_inventory
