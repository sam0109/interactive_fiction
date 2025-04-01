"""
This is the main file for the web application.
It handles the routes for the web application and the LLM API.
"""

import os
from flask import Flask, render_template, request, jsonify, send_from_directory

# Assuming core.game and utils.llm_api are structured correctly
from core.game import Game
from utils.llm_api import generate_response
import config

app = Flask(__name__)

# --- Game Initialization ---
# Initialize the game object once
game = Game()
game.load_characters()

# Store conversation history (in-memory, resets on app restart)
# For persistence, use Flask sessions, a database, or files.
conversation_histories = {}

# --- Routes ---


@app.route("/")
def index():
  """Serves the main chat interface."""
  character_names = [char.name for char in game.characters]
  return render_template("index.html", character_names=character_names)


@app.route("/chat", methods=["POST"])
def chat():
  """Handles incoming chat messages and returns LLM response."""
  data = request.json
  character_name = data.get("character_name")
  user_prompt = data.get("prompt")

  if not character_name or not user_prompt:
    return jsonify({"error": "Missing character name or prompt"}), 400

  selected_char_obj = next(
    (char for char in game.characters if char.name == character_name), None)

  if not selected_char_obj:
    return jsonify({"error": "Character not found"}), 404

  # Get or initialize history for this character
  if character_name not in conversation_histories:
    conversation_histories[character_name] = []

  current_history = conversation_histories[character_name]

  # --- History Preparation (Corrected) ---
  # 1. Prepare the history to send to the LLM (up to this point)
  history_to_send = current_history[-config.MAX_HISTORY:]

  # 2. Add user message to the stored history *after* preparing the list for the
  # LLM
  current_history.append({"role": "Player", "text": user_prompt})
  # --- End History Preparation ---

  # --- Get Other Character Details ---
  other_character_details = [
      {"name": char.name, "description": char.description}
      for char in game.characters
      # Only include if they have a description
      if char.name != selected_char_obj.name and char.description
  ]
  # --- End Get Other Details ---

  # --- Debug History ---
  print("\n" + "-" * 15 + " History being sent to LLM API " + "-" * 15)
  print(history_to_send)
  print("-" * 15 + " End History Sent " + "-" * 15 + "\n")
  # --- End Debug History ---

  # Call the LLM API, passing other character details
  llm_response = generate_response(
      user_prompt,
      selected_char_obj.context,
      history_to_send,  # Pass the history *before* the current prompt
      other_character_details=other_character_details  # Pass details list
  )
  # Add LLM response to the stored history
  current_history.append({"role": "Character", "text": llm_response})

  # Limit the *stored* history size after adding both messages
  conversation_histories[character_name] = current_history[-config.MAX_HISTORY:]

  return jsonify({"response": llm_response})


@app.route("/character_image/<character_name>")
def character_image(character_name):
  """Serves the character"s portrait image."""
  # Generate safe filename (same logic as in GUI/generation)
  safe_name = "".join(c for c in character_name
                      if c.isalnum() or c in (" ", "_")).rstrip()
  safe_name = safe_name.replace(" ", "_").lower()
  image_filename = f"{safe_name}.png"

  image_path = os.path.join(config.IMAGE_SAVE_DIR)

  # Check if file exists before sending
  if os.path.exists(os.path.join(image_path, image_filename)):
    return send_from_directory(image_path, image_filename)
  else:
    # Optionally return a default placeholder image
    # return send_from_directory("static", "placeholder.png")
    return jsonify({"error": "Image not found"}), 404


@app.route("/history/<character_name>")
def get_history(character_name):
  """Returns the conversation history for a given character."""
  if character_name in conversation_histories:
    # Return the history, ensuring it respects MAX_HISTORY if needed
    # Although the main limit is applied on save, we could re-apply here for
    # safety
    history = conversation_histories[character_name]
    return jsonify(history[-config.MAX_HISTORY:])
  else:
    # No history found for this character yet
    return jsonify([])


# --- Run the App ---
if __name__ == "__main__":
  # Ensure template and static folders exist
  if not os.path.exists("templates"):
    os.makedirs("templates")
  if not os.path.exists("static"):
    os.makedirs("static")
  # Debug mode is helpful during development
  app.run(debug=True)
