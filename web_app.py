"""
This is the main file for the web application.
It handles the routes for the web application and the LLM API.
"""

import os
from flask import Flask, render_template, request, jsonify, send_from_directory
import logging
from typing import Tuple, Optional

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# --- Core Game System Imports ---
from core.knowledge import KnowledgeManager
from core.llm_engine import LLMEngine
from core.game_master import GameMaster
from core.game_state import GameState
from entities.in_memory_entity_db import InMemoryEntityDB
from entities.entity import Entity
import config

app = Flask(__name__)

# --- Game Initialization ---
# 1. Load the ground truth entity database
logging.info("Initializing application from default data directories...")
entity_db = InMemoryEntityDB.from_directories(config.ENTITY_DATA_DIRS)

# 2. Initialize the manager for what characters know
knowledge_manager = KnowledgeManager()

# 3. Initialize the Game State
game_state = GameState(entity_db)

# 4. Initialize the engine for LLM interactions
llm_engine = LLMEngine()

# 5. Initialize the Game Master
game_master = GameMaster(llm_engine, knowledge_manager, entity_db)
logging.info("Default application initialization complete.")

# TODO: Seed initial knowledge for the player and other characters
# For now, we assume the game starts with the player knowing nothing.
PLAYER_ID = "player_01" 
PLAYER_LOCATION = "tavern_main_room_01" # Player's current location

# --- Routes ---

@app.route("/")
def index():
    """Serves the main chat interface."""
    # The character list is no longer needed as we have a single player context.
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    """Handles incoming player commands."""
    data = request.json
    prompt = data.get("prompt")
    logging.info(f"Received chat request: prompt='{prompt}', player_location='{game_state.player_location_id}'")
    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    response_text = game_master.process_command(prompt, game_state)
    logging.info(f"Sending response: '{response_text[:100]}...'")
    return jsonify({"response": response_text})

@app.route('/reinitialize_db', methods=['POST'])
def reinitialize_db():
    """A test-only endpoint to re-initialize the entity DB with new data."""
    global entity_db, knowledge_manager, game_state, game_master
    data = request.json
    data_dirs = data.get("data_dirs")
    logging.info(f"Received request to re-initialize DB from: {data_dirs}")
    if not data_dirs:
        logging.error("Re-initialize failed: Missing data_dirs")
        return jsonify({"error": "Missing data_dirs"}), 400
    
    try:
        logging.info(f"Loading entities from {data_dirs}...")
        entity_db = InMemoryEntityDB.from_directories(data_dirs)
        logging.info(f"Loaded {len(entity_db.get_all_entities())} entities.")
        
        # Create and add a default player entity if it doesn't exist
        if not entity_db.get_entity_by_id("player_01"):
            logging.info("Player entity 'player_01' not found. Creating a new one.")
            player_entity = Entity(unique_id="player_01", entity_type="player", data={})
            entity_db._add_entity(player_entity)
        else:
            logging.info("Player entity 'player_01' found in loaded data.")

        knowledge_manager = KnowledgeManager()
        game_state = GameState(entity_db)
        game_master = GameMaster(llm_engine, knowledge_manager, entity_db)
        logging.info(f"DB re-initialized successfully.")
        return jsonify({"message": f"DB re-initialized from {data_dirs}"})
    except Exception as e:
        logging.exception("Failed to re-initialize DB")
        return jsonify({"error": f"Failed to re-initialize DB: {e}"}), 500

@app.route('/set_location', methods=['POST'])
def set_location():
    """A test-only endpoint to set the player's location."""
    data = request.json
    new_location = data.get("location_id")
    logging.info(f"Received request to set location to: {new_location}")
    if not new_location:
        return jsonify({"error": "Missing location_id"}), 400
    
    if not game_state.set_player_location(new_location):
        logging.error(f"Failed to set location: '{new_location}' not found in DB.")
        return jsonify({"error": f"Location '{new_location}' not found."}), 404
        
    logging.info(f"Player location successfully set to: {new_location}")
    return jsonify({"message": f"Player location set to {new_location}"})

# Add error handler for 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


# Add error handler for 500
@app.errorhandler(500)
def internal_server_error(e):
    # Log the error here if needed
    logging.exception("Internal Server Error")
    return render_template("500.html"), 500


# --- Run the App ---
if __name__ == "__main__":
    # Ensure template and static folders exist
    if not os.path.exists("templates"):
        os.makedirs("templates")
    if not os.path.exists("static"):
        os.makedirs("static")
    # Debug mode is helpful during development
    app.run(port=5001, debug=True)
