# Import the LLM interaction function
from utils.llm_api import generate_response
import logging

# Import configuration
import config

# Import necessary modules for file loading
import os

# Import the new Entity Database and Entity class
from entities.entity import Entity
from entities.in_memory_entity_db import InMemoryEntityDB
from typing import Optional, Dict, List, Any

# Add import for json if needed later for prompt generation
import json


class Game:
    def __init__(self):
        # Initialize the unified entity database
        self.entity_db: Optional[InMemoryEntityDB] = None
        try:
            # Use ENTITY_DATA_DIRS from config
            if not hasattr(config, "ENTITY_DATA_DIRS") or not config.ENTITY_DATA_DIRS:
                raise ValueError(
                    "Config error: ENTITY_DATA_DIRS is not defined or empty."
                )

            # Resolve relative paths in ENTITY_DATA_DIRS to absolute paths
            script_dir = os.path.dirname(__file__)  # core/
            base_dir = os.path.dirname(script_dir)  # project root
            entity_abs_dirs = [
                os.path.abspath(os.path.join(base_dir, rel_path))
                for rel_path in config.ENTITY_DATA_DIRS
            ]

            logging.info("Attempting to load entities from: %s", entity_abs_dirs)
            # Instantiate the new DB using the absolute paths
            self.entity_db = InMemoryEntityDB.from_directories(entity_abs_dirs)
        except FileNotFoundError as e:
            # Error message will now use the list of resolved paths
            logging.error(
                "FATAL: Could not find required directories/files listed in ENTITY_DATA_DIRS (%s): %s",
                entity_abs_dirs,
                e,
            )
            self.entity_db = None
        except Exception as e:
            logging.exception("FATAL: Failed to initialize EntityDatabase: %s", e)
            self.entity_db = None

        # --- Create Player Entity ---
        player_id = "player_01"
        initial_player_inventory = {"money": 10, "items": {"rusty_dagger_01": 1}}
        player_entity = Entity(
            unique_id=player_id,
            entity_type="player",  # Distinct type for the player
            names={"Player"},  # Name(s) for lookup
            data={"inventory": initial_player_inventory},  # Store inventory in data
        )
        # Add player directly to the entity db if it loaded successfully
        if self.entity_db:
            # Use internal _add_entity or handle potential ID conflict if loaded from file?
            # Assuming player isn't loaded from file, add directly.
            if player_id not in self.entity_db._entities:
                self.entity_db._entities[player_id] = player_entity
                logging.info("Created and added player entity: %s", player_id)
            else:
                # This case might occur if a player.json was loaded, merge/warn?
                logging.warning(
                    "Player entity %s already exists in DB (loaded from file?). Using loaded version.",
                    player_id,
                )
                # Ensure the loaded player entity has an inventory structure
                if "inventory" not in self.entity_db._entities[player_id].data:
                    self.entity_db._entities[player_id].data[
                        "inventory"
                    ] = initial_player_inventory

        # Store the currently selected character *entity*
        self.current_character_entity: Optional[Entity] = None
        # Manage conversation history externally, keyed by character entity unique_id
        self.conversation_histories: Dict[str, List[Dict[str, str]]] = {}

        logging.info("Game initialized.")
        if self.entity_db:
            logging.info(
                # Update log message
                "Loaded %d total entities.",
                len(self.entity_db.get_all_entities()),
            )
            # Log character count specifically
            char_count = len(self.entity_db.get_entities_by_type("character"))
            item_count = len(self.entity_db.get_entities_by_type("item"))
            logging.info(
                "---> Found %d characters and %d items.", char_count, item_count
            )
        else:
            logging.warning("Entity database failed to load or is empty.")

    def _get_display_name(self, entity: Optional[Entity]) -> str:
        """Helper to get a display name (first name in the set)."""
        # Added check for entity being None
        if entity and entity.names:
            # Convert set to list and get first element safely
            name_list = list(entity.names)
            if name_list:
                return name_list[0]
        # Use entity_type if available and names are missing
        if entity:
            return f"Unnamed {entity.entity_type.capitalize()}"
        return "Unknown Entity"

    # Replace old character lookup, ensure it returns only characters
    def get_character_by_name(self, name: str) -> Optional[Entity]:
        """Finds and returns a *character* entity by name using the database."""
        if not self.entity_db:
            return None
        entity = self.entity_db.get_entity_by_name(name)
        # Ensure the found entity is actually a character
        if entity and entity.entity_type.lower() == "character":
            return entity
        return None  # Return None if not found or not a character

    def get_item_by_name(self, name: str) -> Optional[Entity]:
        """Finds and returns an *item* entity by name using the database."""
        if not self.entity_db:
            return None
        entity = self.entity_db.get_entity_by_name(name)
        # Ensure the found entity is actually an item
        if entity and entity.entity_type.lower() == "item":
            return entity
        return None  # Return None if not found or not an item

    def transfer_money(self, sender_id: str, recipient_name: str, amount: int) -> str:
        """Transfers money between characters or player, using IDs."""
        if not self.entity_db:
            return "(Error: Entity database not available)"
        if amount <= 0:
            return f"(Cannot transfer zero or negative amount)"
        logging.info(
            "Transferring %d gold from %s to %s", amount, sender_id, recipient_name
        )

        # --- Find Sender ---
        sender = self.entity_db.get_entity_by_id(sender_id)
        if not sender or sender.entity_type.lower() != "character":  # Validate sender
            logging.error(
                "Transfer Money: Sender entity %s not found or not a character.",
                sender_id,
            )
            return f"(Error: Sender {sender_id} not found or is not a character)"
        sender_display_name = self._get_display_name(sender)

        # --- Find Recipient ---
        recipient_inventory = None
        recipient_display_name = "Unknown"
        recipient_is_player = False
        recipient_entity: Optional[Entity] = None  # Track recipient entity

        if recipient_name.lower() == "player":
            # Get player entity from DB
            recipient_entity = self.entity_db.get_entity_by_id("player_01")
            if not recipient_entity:
                logging.error(
                    "Transfer Money Error: Player entity 'player_01' not found in DB!"
                )
                return "(Error: Player entity not found)"
            # Ensure player entity has inventory structure
            if "inventory" not in recipient_entity.data or not isinstance(
                recipient_entity.data.get("inventory"), dict
            ):
                recipient_entity.data["inventory"] = {
                    "money": 0,
                    "items": {},
                }  # Initialize if missing
            recipient_inventory = recipient_entity.data["inventory"]
            recipient_display_name = "Player"
            recipient_is_player = True
        else:
            # Use updated method to find character entity
            recipient_entity = self.get_character_by_name(recipient_name)
            if not recipient_entity:  # Already checks type
                logging.warning(
                    "Transfer Money: Recipient character '%s' not found.",
                    recipient_name,
                )
                return f"(Cannot give money: Recipient {recipient_name} not found)"
            # Access inventory via data dict
            if "inventory" not in recipient_entity.data or not isinstance(
                recipient_entity.data.get("inventory"), dict
            ):
                logging.error(
                    "Recipient %s has missing or invalid inventory structure.",
                    recipient_name,
                )
                return f"(Error: Recipient {recipient_name} cannot receive money - invalid data)"
            recipient_inventory = recipient_entity.data["inventory"]
            recipient_display_name = self._get_display_name(recipient_entity)

        # --- Check Sender Funds --- Access inventory via data dict
        if "inventory" not in sender.data or not isinstance(
            sender.data.get("inventory"), dict
        ):
            logging.error(
                "Sender %s has missing or invalid inventory structure.", sender_id
            )
            return f"(Error: Sender {sender_display_name} cannot send money - invalid data)"

        if sender.data["inventory"].get("money", 0) < amount:
            logging.info(
                "Transfer Money: Sender %s has insufficient funds (%d < %d)",
                sender_display_name,
                sender.data["inventory"].get("money", 0),
                amount,
            )
            return f"({sender_display_name} tries to give {amount} gold but doesn't have enough)"

        # --- Perform Transfer --- Modify data dict inventories
        sender.data["inventory"]["money"] = (
            sender.data["inventory"].get("money", 0) - amount
        )
        # Ensure recipient inventory has money key
        if "money" not in recipient_inventory:
            recipient_inventory["money"] = 0
        recipient_inventory["money"] += amount

        logging.info(
            "---> [Inventory Update] Sender (%s): %s",
            sender_display_name,
            sender.data["inventory"],
        )
        if recipient_is_player:
            # Log player inventory via entity data
            player_entity = self.entity_db.get_entity_by_id("player_01")
            if player_entity:
                logging.info(
                    "---> [Inventory Update] Player: %s",
                    player_entity.data.get("inventory", {}),
                )
            else:  # Should not happen if transfer worked
                logging.error(
                    "Player entity 'player_01' missing after successful transfer!"
                )
        else:
            # recipient_entity object's inventory was already updated
            logging.info(
                "---> [Inventory Update] Recipient (%s): %s",
                recipient_display_name,
                recipient_inventory,
            )

        logging.info(
            "[Action] %s gave %d gold to %s",
            sender_display_name,
            amount,
            recipient_display_name,
        )
        return (
            f"({sender_display_name} gives {amount} gold to {recipient_display_name})"
        )

    # Refactor transfer_item to use item_id
    def transfer_item(self, sender_id: str, recipient_name: str, item_id: str) -> str:
        """Transfers an item between characters or player, using item unique ID."""
        if not self.entity_db:
            return "(Error: Entity database not available)"
        logging.info(
            "Transferring item ID '%s' from %s to %s",
            item_id,
            sender_id,
            recipient_name,
        )

        # --- Validate Item ID --- (Optional but recommended)
        item_entity = self.entity_db.get_entity_by_id(item_id)
        if not item_entity or item_entity.entity_type.lower() != "item":
            logging.warning(
                "Transfer Item: Invalid or non-item ID '%s' requested.", item_id
            )
            # Try looking up by name as a fallback? Or just fail?
            # For now, fail if ID is not a valid item ID.
            return f"(Cannot transfer: '{item_id}' is not a valid item ID)"
        # Use the first name found for display purposes if available
        item_display_name = list(item_entity.names)[0] if item_entity.names else item_id

        # --- Find Sender ---
        sender = self.entity_db.get_entity_by_id(sender_id)
        if not sender or sender.entity_type.lower() != "character":
            logging.error(
                "Transfer Item: Sender entity %s not found or not a character.",
                sender_id,
            )
            return f"(Error: Sender {sender_id} not found or is not a character)"
        sender_display_name = self._get_display_name(sender)
        # Access sender items via data dict, ensure structure
        if (
            "inventory" not in sender.data
            or "items" not in sender.data["inventory"]
            or not isinstance(sender.data["inventory"].get("items"), dict)
        ):
            logging.error(
                "Sender %s has missing or invalid item inventory structure.", sender_id
            )
            return f"(Error: Sender {sender_display_name} cannot send items - invalid data)"
        sender_items = sender.data["inventory"]["items"]

        # --- Find Recipient ---
        recipient_items_inventory = None
        recipient_display_name = "Unknown"
        recipient_is_player = False
        recipient_entity: Optional[Entity] = None

        if recipient_name.lower() == "player":
            # Get player entity from DB
            recipient_entity = self.entity_db.get_entity_by_id("player_01")
            if not recipient_entity:
                logging.error(
                    "Transfer Item Error: Player entity 'player_01' not found in DB!"
                )
                return "(Error: Player entity not found)"
            # Ensure player inventory structure exists
            if "inventory" not in recipient_entity.data or not isinstance(
                recipient_entity.data.get("inventory"), dict
            ):
                recipient_entity.data["inventory"] = {"money": 0, "items": {}}
            if "items" not in recipient_entity.data["inventory"] or not isinstance(
                recipient_entity.data["inventory"].get("items"), dict
            ):
                recipient_entity.data["inventory"]["items"] = {}
            recipient_items_inventory = recipient_entity.data["inventory"]["items"]
            recipient_display_name = "Player"
            recipient_is_player = True
        else:
            recipient_entity = self.get_character_by_name(recipient_name)
            if not recipient_entity:
                logging.warning(
                    "Transfer Item: Recipient character '%s' not found.", recipient_name
                )
                return f"(Cannot give item: Recipient {recipient_name} not found)"
            # Access recipient items via data dict, ensure structure
            if "inventory" not in recipient_entity.data or not isinstance(
                recipient_entity.data.get("inventory"), dict
            ):
                recipient_entity.data["inventory"] = {
                    "money": recipient_entity.data.get("inventory", {}).get("money", 0),
                    "items": {},
                }  # Preserve money if exists
            elif "items" not in recipient_entity.data["inventory"] or not isinstance(
                recipient_entity.data["inventory"].get("items"), dict
            ):
                recipient_entity.data["inventory"]["items"] = {}
            recipient_items_inventory = recipient_entity.data["inventory"]["items"]
            recipient_display_name = self._get_display_name(recipient_entity)

        # --- Check Sender Inventory (Using item_id) ---
        if item_id not in sender_items or sender_items[item_id] <= 0:
            logging.info(
                "Transfer Item: Sender %s doesn't have item ID '%s' (%s). Inventory: %s",
                sender_display_name,
                item_id,
                item_display_name,
                sender_items,
            )
            return f"({sender_display_name} tries to give {item_display_name} but doesn't have it)"

        # --- Perform Transfer --- (Using item_id)
        # Decrement sender (remove if count reaches 0)
        sender_items[item_id] -= 1
        if sender_items[item_id] == 0:
            del sender_items[item_id]

        # Increment recipient
        recipient_items_inventory[item_id] = (
            recipient_items_inventory.get(item_id, 0) + 1
        )

        logging.info(
            "[Action] %s gave %s (ID: %s) to %s",
            sender_display_name,
            item_display_name,
            item_id,
            recipient_display_name,
        )
        logging.info(
            "---> [Inventory Update] Sender (%s): %s",
            sender_display_name,
            sender.data["inventory"],
        )
        if recipient_is_player:
            # Log player inventory via entity data
            player_entity = self.entity_db.get_entity_by_id("player_01")
            if player_entity:
                logging.info(
                    "---> [Inventory Update] Player: %s",
                    player_entity.data.get("inventory", {}),
                )
            else:  # Should not happen if transfer worked
                logging.error(
                    "Player entity 'player_01' missing after successful transfer!"
                )
        else:
            logging.info(
                "---> [Inventory Update] Recipient (%s): %s",
                recipient_display_name,
                recipient_entity.data["inventory"],
            )

        # Use display name in the summary message
        return f"({sender_display_name} gives {item_display_name} to {recipient_display_name})"

    def list_characters(self) -> List[Entity]:
        """Lists character entities available in the database and returns the list."""
        print("Characters in the room:")
        if not self.entity_db:
            logging.warning("Entity DB not available for listing characters.")
            print("(Cannot list characters - database error)")
            return []

        # Use new method to get only characters
        all_char_entities = self.entity_db.get_entities_by_type("character")
        if not all_char_entities:
            print("(No characters here.)")
            return []

        for i, char_entity in enumerate(all_char_entities):
            print(f"{i + 1}. {self._get_display_name(char_entity)}")
        return all_char_entities

    def select_character(self) -> bool:
        """Allows player to select a character entity to interact with."""
        available_character_entities = self.list_characters()
        if not available_character_entities:
            return False

        while True:
            try:
                choice = input(
                    f"Who do you want to talk to? (Enter number, or 'quit'): "
                )
                if choice.lower() == "quit":
                    self.current_character_entity = None
                    return False
                char_index = int(choice) - 1
                if 0 <= char_index < len(available_character_entities):
                    # Store the selected Entity object
                    self.current_character_entity = available_character_entities[
                        char_index
                    ]
                    display_name = self._get_display_name(self.current_character_entity)
                    print(f"You approach {display_name}.")

                    # Check for portrait path on the entity
                    if self.current_character_entity.portrait_image_path:
                        print(
                            f"[Portrait available at: {self.current_character_entity.portrait_image_path}]"
                        )  # Simple print for now
                        # UI layer should handle actual display

                    # Access description via data dict
                    description = self.current_character_entity.data.get(
                        "public_facts", {}
                    ).get("description")
                    if description:
                        print("------------------------------------------------------")
                        print(f"[Description: {description}]")
                    else:
                        print("[No description available.]")

                    # Initialize conversation history if needed
                    char_id = self.current_character_entity.unique_id
                    if char_id not in self.conversation_histories:
                        self.conversation_histories[char_id] = []

                    return True
                else:
                    print("Invalid choice.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    def run(self):
        """Main game loop."""
        if not self.entity_db:
            print("ERROR: Entity Database failed to load. Cannot start game.")
            return

        print("Welcome to the Interactive Fiction Engine!")

        while True:
            if not self.current_character_entity:
                print("\nYou look around the room.")
                if not self.select_character():
                    print("Quitting game.")
                    break  # Exit main loop if player quits selection

            # Ensure a character is selected before proceeding
            if not self.current_character_entity:
                logging.error(
                    "Game loop entered invalid state: No character selected after select_character returned True."
                )
                print("An unexpected error occurred. Please restart.")
                break

            # --- Prepare for LLM Interaction ---
            selected_char = self.current_character_entity
            char_id = selected_char.unique_id
            char_display_name = self._get_display_name(selected_char)

            # Retrieve conversation history for this character
            history = self.conversation_histories.get(char_id, [])

            # --- Construct Prompt ---
            # Combine system prompt, character data, history, and player input
            system_prompt = config.SYSTEM_PROMPT

            # Create a simplified view of character data for the prompt
            # Avoid overwhelming the LLM
            prompt_char_data = {
                "name": char_display_name,
                "names_aliases": list(selected_char.names),
                "description": selected_char.data.get("public_facts", {}).get(
                    "description", "N/A"
                ),
                # Only include essential public facts?
                "public_facts": selected_char.data.get("public_facts", {}),
                # Maybe include only *keys* of private facts as hints?
                "private_knowledge_topics": list(
                    selected_char.data.get("private_facts", {}).keys()
                ),
                "inventory": selected_char.data.get(
                    "inventory", {"money": 0, "items": {}}
                ),
                # TODO: Add relationships, status effects etc. selectively
            }
            # Convert to JSON string for the prompt
            prompt_char_json = json.dumps(prompt_char_data, indent=2)

            # Player info (very basic for now)
            player_entity = (
                self.entity_db.get_entity_by_id("player_01") if self.entity_db else None
            )
            player_inv = (
                player_entity.data.get("inventory", {}) if player_entity else {}
            )
            prompt_player_info = {"inventory": player_inv}
            prompt_player_json = json.dumps(prompt_player_info, indent=2)

            # Assemble the context part of the prompt
            context = f"\n--- Character Profile ({char_display_name}) ---\n{prompt_char_json}\n"
            context += f"\n--- Player Information ---\n{prompt_player_json}\n"
            # Optional: Add context about other entities nearby?

            print(
                f"\n--- Talking to {char_display_name} --- (Type 'quit' to exit conversation)"
            )

            player_input = input("You say: ")
            if player_input.lower() == "quit":
                self.current_character_entity = None
                print(f"You stop talking to {char_display_name}.")
                continue  # Go back to character selection

            # --- Call LLM ---
            try:
                # Pass context, history, and latest input
                full_response = generate_response(
                    system_prompt, context, history, player_input
                )
                if not full_response:
                    raise ValueError("LLM returned empty response.")

                # --- Process LLM Response ---
                # Simple split for now, assuming response is first, action is second
                # TODO: Implement more robust parsing (e.g., JSON parsing if LLM outputs structured data)
                response_text = full_response
                action_text = ""
                action_result = ""

                # Basic action parsing example (can be greatly expanded)
                if "[ACTION:" in full_response:
                    parts = full_response.split("[ACTION:", 1)
                    response_text = parts[0].strip()
                    action_part = parts[1].split("]", 1)[0].strip()
                    action_text = (
                        f"[ACTION: {action_part}]"  # Preserve action marker for history
                    )

                    # Parse the specific action
                    action_parts = action_part.split()
                    command = action_parts[0].lower() if action_parts else ""

                    if command == "transfer_money" and len(action_parts) >= 3:
                        try:
                            recipient = action_parts[1]
                            amount = int(action_parts[2])
                            # Use current character entity ID as sender
                            action_result = self.transfer_money(
                                char_id, recipient, amount
                            )
                        except (ValueError, IndexError):
                            action_result = "(Invalid transfer_money action format)"
                    elif command == "transfer_item" and len(action_parts) >= 3:
                        recipient = action_parts[1]
                        item_id = action_parts[2]
                        # Use current character entity ID as sender
                        action_result = self.transfer_item(char_id, recipient, item_id)
                    else:
                        action_result = f"(Unknown or invalid action: {action_part})"

                # --- Output and History ---
                print(f"\n{char_display_name} says: {response_text}")
                if action_result:
                    print(
                        action_result
                    )  # Print result of action (e.g., "(Gareth gives 10 gold to Player)")

                # Add player input and LLM response (including action marker if any) to history
                history.append({"role": "user", "content": player_input})
                # Store the full response including action tag for context
                history.append({"role": "assistant", "content": full_response})
                # Update the main history dictionary
                self.conversation_histories[char_id] = history

            except Exception as e:
                logging.exception("Error during LLM interaction or processing.")
                print(f"\n[System Error: {e}] An error occurred. Please try again.")


if __name__ == "__main__":
    # This allows running the core game logic directly for simple testing
    # For web app, web_app.py should import and use the Game class
    game = Game()
    # Basic check if DB loaded
    if game.entity_db is not None:
        game.run()
    else:
        print("Could not start game due to database loading errors.")
