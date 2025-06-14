"""
This is the main file for the web application.
It handles the routes for the web application and the LLM API.
"""

import os
from flask import Flask, render_template, request, jsonify, send_from_directory
import logging
from typing import Tuple, Optional

# --- Core Game System Imports ---
from core.knowledge import KnowledgeManager
from core.llm_engine import LLMEngine
from core.game_master import GameMaster
from entities.in_memory_entity_db import InMemoryEntityDB
from entities.entity import Entity
import config

app = Flask(__name__)

# --- Game Initialization ---
# 1. Load the ground truth entity database
entity_db = InMemoryEntityDB.from_directories(config.ENTITY_DATA_DIRS)

# 2. Initialize the manager for what characters know
knowledge_manager = KnowledgeManager()

# 3. Initialize the engine for LLM interactions
llm_engine = LLMEngine()

# 4. Initialize the Game Master
game_master = GameMaster(llm_engine, knowledge_manager, entity_db)

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
    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    response_text = game_master.process_command(prompt, PLAYER_LOCATION)
    return jsonify({"response": response_text})

@app.route('/set_location', methods=['POST'])
def set_location():
    """A test-only endpoint to set the player's location."""
    global PLAYER_LOCATION
    data = request.json
    new_location = data.get("location_id")
    if not new_location:
        return jsonify({"error": "Missing location_id"}), 400
    
    if not entity_db.get_entity_by_id(new_location):
        return jsonify({"error": f"Location '{new_location}' not found."}), 404
        
    PLAYER_LOCATION = new_location
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
