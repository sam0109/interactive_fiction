# Import the LLM interaction function
from utils.llm_api import generate_response
import logging

# Import configuration
import config

# Import necessary modules for file loading
import os

# Import the new Character Database and Character class
from characters.character_db import Character
from characters.in_memory_character_db import InMemoryCharacterDB
from typing import Optional, Dict, List


class Game:
    def __init__(self):
        # Initialize the character database
        try:
            # Use CHARACTER_CAST_DIR if defined in config, otherwise CHARACTER_DIR
            char_dir = getattr(config, "CHARACTER_CAST_DIR", config.CHARACTER_DIR)
            logging.info(f"Attempting to load characters from: {char_dir}")
            self.character_db = InMemoryCharacterDB(char_dir)
        except FileNotFoundError:
            logging.error(f"FATAL: Character directory '{char_dir}' not found.")
            self.character_db = None
        except Exception as e:
            logging.exception(f"FATAL: Failed to initialize CharacterDatabase: {e}")
            # Depending on desired behavior, could exit or run with no characters
            self.character_db = None  # Or raise the exception

        # Store the currently selected character object
        self.current_character: Optional[Character] = None
        # Simple representation for Player inventory (can be expanded)
        self.player_inventory = {"money": 10, "items": {"Rusty Dagger": 1}}
        # Manage conversation history externally, keyed by character unique_id
        self.conversation_histories: Dict[str, List[Dict[str, str]]] = {}

        logging.info("Game initialized.")
        if self.character_db:
            logging.info(
                f"Loaded {len(self.character_db.get_all_characters())} characters."
            )
        else:
            logging.warning("Character database failed to load or is empty.")

    def _get_display_name(self, character: Optional[Character]) -> str:
        """Helper to get a display name (first name in the set)."""
        # Added check for character being None
        if character and character.names:
            # Convert set to list and get first element safely
            name_list = list(character.names)
            if name_list:
                return name_list[0]
        return "Unknown Character"

    # Replace old character lookup
    def get_character_by_name(self, name: str) -> Optional[Character]:
        """Finds and returns a character object by name using the database."""
        if not self.character_db:
            return None
        return self.character_db.get_character_by_name(name)

    def transfer_money(self, sender_id: str, recipient_name: str, amount: int) -> str:
        """Transfers money between characters or player, using IDs."""
        if not self.character_db:
            return "(Error: Character database not available)"
        if amount <= 0:
            return f"(Cannot transfer zero or negative amount)"
        logging.info(f"Transferring {amount} gold from {sender_id} to {recipient_name}")

        # --- Find Sender ---
        # Assume sender_id is the unique_id of the current character speaking
        sender = self.character_db.get_character_by_id(sender_id)
        if not sender:
            logging.error(f"Transfer Money: Sender ID {sender_id} not found in DB.")
            return f"(Error: Sender {sender_id} not found)"
        sender_display_name = self._get_display_name(sender)

        # --- Find Recipient ---
        recipient_inventory = None
        recipient_display_name = "Unknown"
        recipient_is_player = False

        if recipient_name.lower() == "player":
            recipient_inventory = self.player_inventory
            recipient_display_name = "Player"
            recipient_is_player = True
        else:
            recipient = self.get_character_by_name(recipient_name)  # Use DB lookup
            if not recipient:
                logging.warning(
                    f"Transfer Money: Recipient '{recipient_name}' not found."
                )
                return f"(Cannot give money: Recipient {recipient_name} not found)"
            recipient_inventory = recipient.inventory  # Access inventory directly
            recipient_display_name = self._get_display_name(recipient)

        # --- Check Sender Funds ---
        if sender.inventory["money"] < amount:
            logging.info(
                f"Transfer Money: Sender {sender_display_name} has insufficient funds ({sender.inventory['money']} < {amount})"
            )
            return f"({sender_display_name} tries to give {amount} gold but doesn't have enough)"

        # --- Perform Transfer ---
        sender.inventory["money"] -= amount
        recipient_inventory["money"] += amount  # Modify the retrieved inventory dict

        logging.info(
            f"---> [Inventory Update] Sender ({sender_display_name}): {sender.inventory}"
        )
        if recipient_is_player:
            logging.info(f"---> [Inventory Update] Player: {self.player_inventory}")
        else:
            # recipient object's inventory was already updated
            logging.info(
                f"---> [Inventory Update] Recipient ({recipient_display_name}): {recipient_inventory}"
            )

        logging.info(
            f"[Action] {sender_display_name} gave {amount} gold to {recipient_display_name}"
        )
        return (
            f"({sender_display_name} gives {amount} gold to {recipient_display_name})"
        )

    def transfer_item(self, sender_id: str, recipient_name: str, item_name: str) -> str:
        """Transfers an item between characters or player, using IDs."""
        if not self.character_db:
            return "(Error: Character database not available)"
        logging.info(f"Transferring '{item_name}' from {sender_id} to {recipient_name}")

        # --- Find Sender ---
        sender = self.character_db.get_character_by_id(sender_id)
        if not sender:
            logging.error(f"Transfer Item: Sender ID {sender_id} not found in DB.")
            return f"(Error: Sender {sender_id} not found)"
        sender_display_name = self._get_display_name(sender)
        sender_items = sender.inventory["items"]  # Access items directly

        # --- Find Recipient ---
        recipient_items_inventory = None
        recipient_display_name = "Unknown"
        recipient_is_player = False

        if recipient_name.lower() == "player":
            recipient_items_inventory = self.player_inventory["items"]
            recipient_display_name = "Player"
            recipient_is_player = True
        else:
            recipient = self.get_character_by_name(recipient_name)  # Use DB lookup
            if not recipient:
                logging.warning(
                    f"Transfer Item: Recipient '{recipient_name}' not found."
                )
                return f"(Cannot give item: Recipient {recipient_name} not found)"
            # Ensure recipient inventory structure exists if adding first item
            if "items" not in recipient.inventory:
                recipient.inventory["items"] = {}
            recipient_items_inventory = recipient.inventory[
                "items"
            ]  # Access items directly
            recipient_display_name = self._get_display_name(recipient)

        # --- Check Sender Inventory ---
        if item_name not in sender_items or sender_items[item_name] <= 0:
            logging.info(
                f"Transfer Item: Sender {sender_display_name} doesn't have '{item_name}'. Inventory: {sender_items}"
            )
            return (
                f"({sender_display_name} tries to give {item_name} but doesn't have it)"
            )

        # --- Perform Transfer ---
        # Decrement sender (remove if count reaches 0)
        sender_items[item_name] -= 1
        if sender_items[item_name] == 0:
            del sender_items[item_name]

        # Increment recipient
        recipient_items_inventory[item_name] = (
            recipient_items_inventory.get(item_name, 0) + 1
        )

        logging.info(
            f"[Action] {sender_display_name} gave {item_name} to {recipient_display_name}"
        )
        logging.info(
            f"---> [Inventory Update] Sender ({sender_display_name}): {sender.inventory}"
        )
        if recipient_is_player:
            logging.info(f"---> [Inventory Update] Player: {self.player_inventory}")
        else:
            # recipient object's inventory was already updated
            logging.info(
                f"---> [Inventory Update] Recipient ({recipient_display_name}): {recipient.inventory}"
            )  # Use recipient obj here

        return f"({sender_display_name} gives {item_name} to {recipient_display_name})"

    def list_characters(self) -> List[Character]:
        """Lists characters available in the database and returns the list."""
        print("Characters in the room:")
        if not self.character_db:
            logging.warning("Character DB not available for listing.")
            print("(Cannot list characters - database error)")
            return []  # Return empty list

        all_chars = self.character_db.get_all_characters()
        if not all_chars:
            print("(It's empty.)")
            return []

        for i, char in enumerate(all_chars):
            # Use helper to get a display name
            print(f"{i + 1}. {self._get_display_name(char)}")
        return all_chars  # Return the list for selection logic

    def select_character(self) -> bool:
        """Allows player to select a character to interact with."""
        available_characters = self.list_characters()
        if not available_characters:
            # list_characters already printed "(It's empty.)"
            return False

        while True:
            try:
                choice = input(
                    f"Who do you want to talk to? (Enter number, or 'quit'): "
                )
                if choice.lower() == "quit":
                    self.current_character = None  # Ensure current character is cleared
                    return False
                char_index = int(choice) - 1
                if 0 <= char_index < len(available_characters):
                    # Store the selected Character object
                    self.current_character = available_characters[char_index]
                    display_name = self._get_display_name(self.current_character)
                    print(f"You approach {display_name}.")

                    # Check if a pre-generated image exists (using public description)
                    description = self.current_character.public_facts.get("description")
                    if description:
                        # Simplified image logic for now
                        print("------------------------------------------------------")
                        print(f"[Description: {description}]")
                        # Image display is better handled by the UI layer (web_app, GUI)
                        # Based on character ID or name. We just provide the data here.
                        print("[Image display logic would ideally be in UI]")
                        print("------------------------------------------------------")

                    # Initialize history for this character if it doesn't exist
                    if (
                        self.current_character.unique_id
                        not in self.conversation_histories
                    ):
                        self.conversation_histories[
                            self.current_character.unique_id
                        ] = []
                        logging.info(
                            f"Initialized history for {self.current_character.unique_id}"
                        )

                    return True  # Character successfully selected
                else:
                    print("Invalid choice. Please enter a valid number.")
            except ValueError:
                print("Invalid input. Please enter a number or 'quit'.")
            except (
                IndexError
            ):  # Catch potential index error if list is modified unexpectedly
                print("Error selecting character. Please try again.")
                return False

    def start(self):
        """Starts the main game loop for the text-based interface."""
        # Initialization now happens in __init__
        logging.info("Welcome to the adventure!")
        if not self.character_db:
            print("Game cannot start: Character Database failed to load.")
            return

        while True:
            # Reset current character before selection
            self.current_character = None
            if not self.select_character():  # Select returns false if user quits
                print("Leaving the tavern. Goodbye!")
                break  # Exit the main game loop

            # Ensure a character was actually selected (should be guaranteed by select_character if it returns True)
            if not self.current_character:
                logging.error(
                    "select_character returned True but current_character is not set."
                )
                break  # Should not happen

            current_char_name = self._get_display_name(self.current_character)
            current_char_id = self.current_character.unique_id
            logging.info(
                f"Starting interaction with {current_char_name} ({current_char_id})"
            )

            print(
                f"What do you say to {current_char_name}? (Type 'back' to talk to someone else, 'quit' to exit)"
            )

            # Get history for the current character
            # Use .setdefault to ensure the key exists and get the list
            current_history = self.conversation_histories.setdefault(
                current_char_id, []
            )

            while True:  # Inner loop for conversation with the selected character
                player_input = input("Player: ")
                if player_input.lower() == "quit":
                    print("Leaving the tavern. Goodbye!")
                    return  # Exit game completely
                if player_input.lower() == "back":
                    print(f"You step back from {current_char_name}.")
                    break  # Exit inner loop, go back to character selection

                if not player_input:
                    print("(You remain silent.)")
                    continue

                # Prepare data for LLM
                llm_context = self.current_character.private_facts.get(
                    "internal_description", "I have no specific thoughts."
                )
                llm_inventory = (
                    self.current_character.inventory
                )  # Pass current inventory
                all_chars = self.character_db.get_all_characters()
                other_character_details = [
                    {
                        # Use helper for consistent naming
                        "name": self._get_display_name(char),
                        "description": char.public_facts.get(
                            "description", "An unknown figure."
                        ),
                    }
                    # Filter out self, ensure description exists
                    for char in all_chars
                    if char.unique_id != current_char_id
                    and char.public_facts.get("description")
                ]

                # Add player input to history BEFORE calling LLM
                current_history.append({"role": "Player", "text": player_input})

                # Ensure history doesn't exceed max length for the API call
                # Slice creates a copy, original history grows until trimmed later
                history_for_llm = (
                    current_history[-(config.MAX_HISTORY - 1) :]
                    if config.MAX_HISTORY > 1
                    else []
                )

                logging.info(
                    f"Calling LLM for {current_char_name} ({current_char_id}). History length: {len(history_for_llm)}"
                )
                response_data = generate_response(
                    prompt=player_input,
                    character_context=llm_context,
                    history=history_for_llm,
                    other_character_details=other_character_details,
                    character_inventory=llm_inventory,
                )

                final_response = "(Error processing response)"  # Default
                response_type = response_data.get("type", "error")

                if response_type == "text":
                    final_response = response_data.get(
                        "content", "(Error in text response)"
                    )
                elif response_type == "function_call":
                    func_name = response_data.get("name")
                    func_args = response_data.get("args", {})
                    # Sender is always the current character
                    sender_id = current_char_id
                    recipient_name = func_args.get("recipient_name")
                    logging.info(
                        f"--> Function Call: {func_name}({func_args}) by {sender_id}"
                    )

                    if not recipient_name:
                        final_response = "(Error: Tool call missing recipient_name)"
                        logging.warning("LLM function call missing recipient_name.")
                    elif func_name == "give_money":
                        amount = func_args.get("amount")
                        if isinstance(amount, int):
                            # Use updated transfer method
                            final_response = self.transfer_money(
                                sender_id, recipient_name, amount
                            )
                        else:
                            final_response = "(Error: Invalid amount for give_money)"
                            logging.warning(
                                f"Invalid amount '{amount}' for give_money."
                            )
                    elif func_name == "give_item":
                        item_name = func_args.get("item_name")
                        if item_name and isinstance(item_name, str):
                            # Use updated transfer method
                            final_response = self.transfer_item(
                                sender_id, recipient_name, item_name
                            )
                        else:
                            final_response = (
                                "(Error: Missing or invalid item_name for give_item)"
                            )
                            logging.warning(
                                f"Invalid item_name '{item_name}' for give_item."
                            )
                    else:
                        # Should match function names defined in llm_api
                        logging.warning(f"LLM attempted unknown action: {func_name}")
                        final_response = (
                            f"(Tried to perform an unknown action: {func_name})"
                        )
                elif response_type == "error":
                    final_response = response_data.get("content", "(Unknown LLM error)")
                    logging.error(f"LLM API Error: {final_response}")
                else:
                    # Handle unexpected response types
                    logging.error(
                        f"Unexpected response type from LLM API: {response_type}"
                    )
                    final_response = "(Received an unexpected response type)"

                # Add character response/action result to history
                current_history.append({"role": "Character", "text": final_response})

                # Update the stored history for this character ID, trimming it
                self.conversation_histories[current_char_id] = current_history[
                    -config.MAX_HISTORY :
                ]
                logging.debug(
                    f"History updated for {current_char_id}. New length: {len(self.conversation_histories[current_char_id])}"
                )

                # Print the character's response or action result
                print(f"{current_char_name}: {final_response}")


# Minimal setup for running if needed
if __name__ == "__main__":
    # Basic logging setup
    # Consider moving logging config to a central place or config file
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Ensure necessary directories exist if config relies on them (e.g., image save dir)
    # Check if IMAGE_SAVE_DIR exists in config before using it
    if hasattr(config, "IMAGE_SAVE_DIR") and not os.path.exists(config.IMAGE_SAVE_DIR):
        try:
            os.makedirs(config.IMAGE_SAVE_DIR, exist_ok=True)
            logging.info(f"Created directory: {config.IMAGE_SAVE_DIR}")
        except OSError as e:
            logging.error(f"Could not create directory {config.IMAGE_SAVE_DIR}: {e}")

    game_instance = Game()
    if game_instance.character_db:  # Only start if DB loaded successfully
        game_instance.start()
    else:
        # Error message already logged in __init__
        print("Game cannot start due to character loading issues. Check logs.")
