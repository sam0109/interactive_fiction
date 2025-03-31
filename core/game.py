# Import the LLM interaction function
from utils.llm_api import generate_response, generate_image
# Import configuration
import config
# Import necessary modules for file loading
import os
import json

# Define a simple Character class
class Character:
    def __init__(self, name, context, description=None, ascii_art=None):
        self.name = name
        self.context = context
        self.description = description # Store description for image gen
        self.history = []
        # self.ascii_art = ascii_art # Removed ascii_art storage

class Game:
    def __init__(self):
        self.characters = []
        self.current_character = None
        print("Game initialized.")

    def load_characters(self):
        print(f"Loading characters from '{config.CHARACTER_DIR}' directory...")
        if not os.path.exists(config.CHARACTER_DIR):
            print(f"Warning: Character directory '{config.CHARACTER_DIR}' not found. Creating it.")
            os.makedirs(config.CHARACTER_DIR, exist_ok=True)
            # Optionally, create a default character file here if needed

        for filename in os.listdir(config.CHARACTER_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(config.CHARACTER_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        char_data = json.load(f)
                        if 'name' in char_data and 'context' in char_data:
                            # Get description and ascii_art safely
                            desc = char_data.get('description')
                            # art = char_data.get('ascii_art') # Removed ascii_art loading
                            self.characters.append(Character(char_data['name'], char_data['context'], desc))
                            print(f" - Loaded character: {char_data['name']}")
                        else:
                            print(f"Warning: Skipping file {filename}. Missing 'name' or 'context' field.")
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
                choice = input(f"Who do you want to talk to? (Enter number, or 'quit'): ")
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
                        safe_name = "".join(c for c in self.current_character.name if c.isalnum() or c in (' ', '_')).rstrip()
                        safe_name = safe_name.replace(' ', '_').lower()
                        image_filename = f"{safe_name}.png"
                        image_path = os.path.join(config.IMAGE_SAVE_DIR, image_filename)

                        if os.path.exists(image_path):
                            print(f"[Image found for {self.current_character.name}: {image_path}]")
                            # TODO: Add code here to actually display the image if possible
                            #       (e.g., open with default viewer, or integrate with a GUI)
                        else:
                            print(f"[Image for {self.current_character.name} not found at '{image_path}'.]")
                            print("[Run 'python utils/generate_character_images.py' to generate missing images.]")
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

            print(f"What do you say to {self.current_character.name}? (Type 'back' to talk to someone else, 'quit' to exit)")
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

                # Get the LLM response, passing the history
                # print("\n(Thinking...)") # Removed thinking indicator
                response = generate_response(player_input, self.current_character.context, self.current_character.history)

                # Update history
                self.current_character.history.append({'role': 'Player', 'text': player_input})
                self.current_character.history.append({'role': 'Character', 'text': response})
                # Limit history size using config
                if len(self.current_character.history) > config.MAX_HISTORY:
                    self.current_character.history = self.current_character.history[-config.MAX_HISTORY:]

                # Print the character's response
                print(f"\n{self.current_character.name}: {response}")

# Removed runnable block 