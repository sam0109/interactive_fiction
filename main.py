import sys
import os

# Ensure the 'core' and 'utils' directories can be found
# This adds the project root directory to the Python path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Game class from the core module
from core.game import Game

def main():
    """Initializes and starts the game."""
    print("Launching Interactive Fiction Game...")
    # Initialize the game object
    game_instance = Game()
    # Start the game loop
    game_instance.start()

if __name__ == "__main__":
    main() 