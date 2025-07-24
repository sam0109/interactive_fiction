"""
This module defines the GameState class, which serves as the single source of
truth for all dynamic state in the game.
"""
from typing import Optional
from entities.entity import Entity
from entities.in_memory_entity_db import InMemoryEntityDB

class GameState:
    """
    Manages the dynamic state of the game, including player status and location.
    """
    def __init__(self, entity_db: InMemoryEntityDB):
        self.entity_db = entity_db
        self.player_id: str = "player_01"
        
        # Initialize player location
        self.player_location_id: str = "tavern_main_room_01" # Default starting location

    def get_player_entity(self) -> Optional[Entity]:
        """Retrieves the player's entity object from the database."""
        return self.entity_db.get_entity_by_id(self.player_id)

    def set_player_location(self, new_location_id: str) -> bool:
        """
        Sets the player's location, verifying the location exists.

        Args:
            new_location_id: The unique ID of the new location.

        Returns:
            True if the location was updated successfully, False otherwise.
        """
        if self.entity_db.get_entity_by_id(new_location_id):
            self.player_location_id = new_location_id
            return True
        return False 