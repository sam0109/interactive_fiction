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

  try:
    # Call the LLM API, passing other character details and current inventory
    response_data = generate_response(
        user_prompt,
        selected_char_obj.context,
        history_to_send,
        other_character_details=other_character_details,
        character_inventory=selected_char_obj.inventory  # Pass current inventory
    )

    final_response_text = ""
    player_affected = False  # Initialize default value
    # Default to error if type missing
    response_type = response_data.get("type", "error")

    if response_type == "text":
      final_response_text = response_data.get(
          "content", "(Error processing response)")
      # player_affected remains False for text responses
    elif response_type == "function_call":
      func_name = response_data.get("name")
      func_args = response_data.get("args", {})
      print(f"---> Received function call: {func_name} with args: {func_args}")

      # --- Execute Function Call ---
      action_result = "(Error executing action)"  # Default error message
      sender_name = selected_char_obj.name  # The character speaking is the sender
      recipient_name = func_args.get("recipient_name")

      if not recipient_name:
        action_result = "(Error: Tool call missing recipient_name)"
      elif func_name == "give_money":
        amount = func_args.get("amount")
        if isinstance(amount, int):
          print(f"---> Attempting to call game.transfer_money for {func_name}")
          action_result = game.transfer_money(
              sender_name, recipient_name, amount)
        else:
          action_result = "(Error: Invalid or missing amount for give_money)"
      elif func_name == "give_item":
        item_name = func_args.get("item_name")
        if item_name:
          print(f"---> Attempting to call game.transfer_item for {func_name}")
          action_result = game.transfer_item(
              sender_name, recipient_name, item_name)
        else:
          action_result = "(Error: Missing item_name for give_item)"
      else:
        action_result = f"(Attempted unknown action: {func_name})"

      # Use the result of the action as the response text
      final_response_text = action_result
      # --- End Execute Function Call ---

      # --- Determine if player inventory might have changed ---
      if recipient_name.lower() == "player" and not action_result.startswith(
              "(Error") and not action_result.startswith("(Cannot"):
        # If recipient is player and the action didn't obviously fail
        player_affected = True
      # --- End Determine Player Affected ---

    elif response_type == "error":
      final_response_text = response_data.get(
          "content", "(Unknown LLM error)")
      print(f"LLM API Error: {final_response_text}")
      player_affected = False  # Error means no change
    else:
      final_response_text = "(Received unexpected response type)"
      print(f"Unknown response type: {response_type}")
      player_affected = False  # Unexpected type means no change

    # Add the final text (LLM response or action result) to history
    current_history.append({"role": "Character", "text": final_response_text})

    # Limit the *stored* history size after adding both messages
    conversation_histories[character_name] = current_history[-config.MAX_HISTORY:]
    # Include the flag in the response if player was affected
    response_payload = {'response': final_response_text}
    if response_type == "function_call" and player_affected:
      response_payload['player_inventory_updated'] = True

    return jsonify(response_payload)

  except Exception as e:
    print(f"Error processing LLM response or function call: {e}")
    # Log the exception traceback for more detail if needed
    # import traceback
    # traceback.print_exc()
    return jsonify({"error": "Internal server error processing response."}), 500


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


@app.route("/inventory/<character_name>")
def get_inventory(character_name):
  """Returns the inventory for a given character."""
  character = game.get_character_by_name(character_name)
  if character:
      # Ensure structure, although load_characters should handle this
    inventory = character.inventory
    if "money" not in inventory:
      inventory["money"] = 0
    if "items" not in inventory:
      inventory["items"] = {}
    return jsonify(inventory)
  else:
    # Handle case where character might not be found (though unlikely if name comes from dropdown)
    return jsonify({"error": "Character not found"}), 404


@app.route("/player_inventory")
def get_player_inventory():
  """Returns the player's current inventory."""
  inventory = game.player_inventory
  # Ensure structure (optional, but safe)
  if "money" not in inventory:
    inventory["money"] = 0
  if "items" not in inventory:
    inventory["items"] = {}
  print(f"---> [API] Serving Player Inventory: {inventory}")  # Debug print
  return jsonify(inventory)


# --- Run the App ---
if __name__ == "__main__":
  # Ensure template and static folders exist
  if not os.path.exists("templates"):
    os.makedirs("templates")
  if not os.path.exists("static"):
    os.makedirs("static")
  # Debug mode is helpful during development
  app.run(debug=True)
