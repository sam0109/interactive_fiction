# Import the LLM interaction function
from utils.llm_api import generate_response, generate_image
# Import configuration
import config
# Import necessary modules for file loading
import os
import json

# Define a simple Character class


class Character:
  def __init__(self, name, context, description=None, inventory=None):
    self.name = name
    self.context = context
    self.description = description
    self.history = []
    self.inventory = inventory if inventory is not None else {
        "money": 0, "items": {}}


class Game:
  def __init__(self):
    self.characters = []
    self.current_character = None
    # Simple representation for Player inventory (can be expanded)
    self.player_inventory = {"money": 10, "items": {"Rusty Dagger": 1}}
    print("Game initialized.")

  def get_character_by_name(self, name):
    """Finds and returns a character object by name."""
    for char in self.characters:
      if char.name == name:
        return char
    return None

  def transfer_money(self, sender_name, recipient_name, amount):
    """Transfers money between characters or player."""
    if amount <= 0:
      return f"(Cannot transfer zero or negative amount)"
    print(f"Transferring {amount} gold from {sender_name} to {recipient_name}")

    # --- Find Sender ---
    sender = self.get_character_by_name(sender_name)
    if not sender:
      return f"(Error: Sender {sender_name} not found)"

    # --- Find Recipient ---
    recipient = None
    recipient_is_player = False
    if recipient_name.lower() == "player":
      recipient = self.player_inventory
      recipient_is_player = True
      recipient_display_name = "Player"
    else:
      recipient = self.get_character_by_name(recipient_name)
      if not recipient:
        return f"(Cannot give money: Recipient {recipient_name} not found)"
      recipient_display_name = recipient.name

    # --- Check Sender Funds ---
    if sender.inventory["money"] < amount:
      return f"({sender.name} tries to give {amount} gold but doesn't have enough)"

    # --- Perform Transfer ---
    sender.inventory["money"] -= amount
    recipient["money"] += amount
    print(f"---> [Inventory Update] Sender ({sender_name}): {sender.inventory}")
    if recipient_is_player:
      print(f"---> [Inventory Update] Player: {self.player_inventory}")
    else:
      print(
        f"---> [Inventory Update] Recipient ({recipient_display_name}): {recipient.inventory}")

    print(
      f"[Action] {sender.name} gave {amount} gold to {recipient_display_name}")
    return f"({sender.name} gives {amount} gold to {recipient_display_name})"

  def transfer_item(self, sender_name, recipient_name, item_name):
    """Transfers an item between characters or player."""
    # --- Find Sender ---
    sender = self.get_character_by_name(sender_name)
    if not sender:
      return f"(Error: Sender {sender_name} not found)"

    # --- Find Recipient ---
    recipient_inventory = None
    recipient_is_player = False
    if recipient_name.lower() == "player":
      recipient_inventory = self.player_inventory["items"]
      recipient_is_player = True
      recipient_display_name = "Player"
    else:
      recipient = self.get_character_by_name(recipient_name)
      if not recipient:
        return f"(Cannot give item: Recipient {recipient_name} not found)"
      recipient_inventory = recipient.inventory["items"]
      recipient_display_name = recipient.name

    # --- Check Sender Inventory ---
    sender_items = sender.inventory["items"]
    if item_name not in sender_items or sender_items[item_name] <= 0:
      return f"({sender.name} tries to give {item_name} but doesn't have it)"

    # --- Perform Transfer ---
    # Decrement sender (remove if count reaches 0)
    sender_items[item_name] -= 1
    if sender_items[item_name] == 0:
      del sender_items[item_name]

    # Increment recipient
    recipient_inventory[item_name] = recipient_inventory.get(item_name, 0) + 1

    print(
      f"[Action] {sender.name} gave {item_name} to {recipient_display_name}")
    return f"({sender.name} gives {item_name} to {recipient_display_name})"

  def load_characters(self):
    print(f"Loading characters from '{config.CHARACTER_DIR}' directory...")
    if not os.path.exists(config.CHARACTER_DIR):
      print(
        f"Warning: Character directory '{config.CHARACTER_DIR}' not found. Creating it.")
      os.makedirs(config.CHARACTER_DIR, exist_ok=True)
      # Optionally, create a default character file here if needed

    for filename in os.listdir(config.CHARACTER_DIR):
      if filename.endswith(".json"):
        filepath = os.path.join(config.CHARACTER_DIR, filename)
        try:
          with open(filepath, 'r', encoding='utf-8') as f:  # Added encoding
            char_data = json.load(f)
            if 'name' in char_data and 'context' in char_data:
              # Get description and ascii_art safely
              desc = char_data.get('description')
              # art = char_data.get('ascii_art') # Removed ascii_art loading
              # Load inventory, defaulting if not present or invalid
              inventory_data = char_data.get('inventory')
              if not isinstance(inventory_data, dict):
                print(
                  f"Warning: Invalid or missing inventory for {char_data['name']}. Defaulting.")
                inventory_data = {"money": 0, "items": {}}
              else:
                # Ensure basic structure
                if "money" not in inventory_data:
                  inventory_data["money"] = 0
                if "items" not in inventory_data:
                  inventory_data["items"] = {}

              self.characters.append(Character(
                  char_data['name'],
                  char_data['context'],
                  desc,
                  inventory_data  # Pass loaded/defaulted inventory
              ))
              print(f" - Loaded character: {char_data['name']}")
            else:
              print(
                f"Warning: Skipping file {filename}. Missing 'name' or 'context' field.")
        except json.JSONDecodeError:
          print(f"Warning: Skipping file {filename}. Invalid JSON format.")
        except Exception as e:
          print(f"Warning: Skipping file {filename}. Error loading: {e}")

    if not self.characters:
      print("Warning: No valid character files found in the directory.")
    else:
      print(f"Loaded {len(self.characters)} character(s) successfully.")

  def list_characters(self):
    print("\nCharacters in the room:")
    if not self.characters:
      print("(It's empty.)")
      return
    for i, char in enumerate(self.characters):
      print(f"{i + 1}. {char.name}")

  def select_character(self):
    self.list_characters()
    if not self.characters:
      return False

    while True:
      try:
        choice = input(
          f"Who do you want to talk to? (Enter number, or 'quit'): ")
        if choice.lower() == 'quit':
          return False
        char_index = int(choice) - 1
        if 0 <= char_index < len(self.characters):
          self.current_character = self.characters[char_index]
          print(f"\nYou approach {self.current_character.name}.")

          # Check if a pre-generated image exists
          if self.current_character.description:
            print("\n------------------------------------------------------")
            # Construct the expected image path
            safe_name = "".join(
                c for c in self.current_character.name
                if c.isalnum() or c in (' ', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_').lower()
            image_filename = f"{safe_name}.png"
            image_path = os.path.join(config.IMAGE_SAVE_DIR, image_filename)

            if os.path.exists(image_path):
              print(
                f"[Image found for {self.current_character.name}: {image_path}]")
              # TODO: Add code here to actually display the image if possible
              #       (e.g., open with default viewer, or integrate with a GUI)
            else:
              print(
                f"[Image for {self.current_character.name} not found at '{image_path}'.]")
              print(
                "[Run 'python utils/generate_character_images.py' to generate missing images.]")
            print("------------------------------------------------------\n")

          return True
        else:
          print("Invalid choice. Please enter a valid number.")
      except ValueError:
        print("Invalid input. Please enter a number or 'quit'.")

  def start(self):
    print("\nWelcome to the adventure!")
    self.load_characters()

    while True:
      if not self.select_character():
        print("\nLeaving the tavern. Goodbye!")
        break

      print(
        f"What do you say to {self.current_character.name}? (Type 'back' to talk to someone else, 'quit' to exit)")
      while True:
        player_input = input("Player: ")
        if player_input.lower() == 'quit':
          print("\nLeaving the tavern. Goodbye!")
          return
        if player_input.lower() == 'back':
          print(f"\nYou step back from {self.current_character.name}.")
          self.current_character = None
          break

        if not player_input:
          print("(You remain silent.)")
          continue

        # Get the LLM response (which might be text or function call)
        response_data = generate_response(
            player_input,
            self.current_character.context,
            self.current_character.history,
            # Pass other character details for context
            other_character_details=[
                {"name": char.name, "description": char.description}
                for char in self.characters
                if char.name != self.current_character.name and char.description
            ],
            # Pass current character inventory for context
            character_inventory=self.current_character.inventory
        )

        final_response = "(Error processing response)"  # Default
        response_type = response_data.get("type", "error")

        if response_type == "text":
          final_response = response_data.get(
            "content", "(Error in text response)")
        elif response_type == "function_call":
          func_name = response_data.get("name")
          func_args = response_data.get("args", {})
          sender_name = self.current_character.name
          recipient_name = func_args.get("recipient_name")
          print(f"--> Function Call: {func_name}({func_args})")  # Debug

          if not recipient_name:
            final_response = "(Error: Tool call missing recipient_name)"
          elif func_name == "give_money":
            amount = func_args.get("amount")
            if isinstance(amount, int):
              final_response = self.transfer_money(
                sender_name, recipient_name, amount)
            else:
              final_response = "(Error: Invalid amount for give_money)"
          elif func_name == "give_item":
            item_name = func_args.get("item_name")
            if item_name:
              final_response = self.transfer_item(
                sender_name, recipient_name, item_name)
            else:
              final_response = "(Error: Missing item_name for give_item)"
          else:
            final_response = f"(Attempted unknown action: {func_name})"
        elif response_type == "error":
          final_response = response_data.get("content", "(Unknown LLM error)")

        # Update history with the final response (text or action result)
        self.current_character.history.append(
            {'role': 'Player', 'text': player_input})
        self.current_character.history.append(
            {'role': 'Character', 'text': final_response})
        # Limit history size using config
        if len(self.current_character.history) > config.MAX_HISTORY:
          self.current_character.history = self.current_character.history[-config.MAX_HISTORY:]

        # Print the character's response or action result
        print(f"\n{self.current_character.name}: {final_response}")

# Removed runnable block
