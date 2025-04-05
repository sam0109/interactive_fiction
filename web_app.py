"""
This is the main file for the web application.
It handles the routes for the web application and the LLM API.
"""

import os
from flask import Flask, render_template, request, jsonify, send_from_directory
import logging

# Assuming core.game and utils.llm_api are structured correctly
from core.game import Game
from utils.llm_api import generate_response
import config

app = Flask(__name__)

# --- Game Initialization ---
# Initialize the game object once
game = Game()

# Store conversation history (in-memory, resets on app restart)
# For persistence, use Flask sessions, a database, or files.
conversation_histories = {}

# --- Routes ---


@app.route("/")
def index():
    """Serves the main chat interface."""
    character_names = []
    if game.character_db:  # Check if DB loaded successfully
        all_chars = game.character_db.get_all_characters()
        # Get the first name from the names set for display
        character_names = [
            list(char.names)[0] if char.names else "Unknown" for char in all_chars
        ]
    else:
        # Handle case where DB failed to load
        print("Warning: Character DB not loaded, cannot populate character list.")

    return render_template("index.html", character_names=character_names)


@app.route("/chat", methods=["POST"])
def chat():
    """Handles incoming chat messages and returns LLM response."""
    if not game.character_db:
        return (
            jsonify({"error": "Character database not available"}),
            503,
        )  # Service Unavailable

    data = request.json
    character_name = data.get("character_name")
    user_prompt = data.get("prompt")

    if not character_name or not user_prompt:
        return jsonify({"error": "Missing character name or prompt"}), 400

    # Find character using the database
    selected_char_obj = game.character_db.get_character_by_name(character_name)

    if not selected_char_obj:
        logging.warning(
            f"Chat request failed: Character '{character_name}' not found in DB."
        )
        return jsonify({"error": "Character not found"}), 404

    # Use character's unique_id for history key
    char_id = selected_char_obj.unique_id
    if char_id not in conversation_histories:
        conversation_histories[char_id] = []
        logging.info(f"Initialized history for {char_id}")

    current_history = conversation_histories[char_id]

    # --- History Preparation (Corrected) ---
    # 1. Prepare the history to send to the LLM (up to this point)
    history_to_send = current_history[-config.MAX_HISTORY :]

    # 2. Add user message to the stored history *after* preparing the list for the
    # LLM
    current_history.append({"role": "Player", "text": user_prompt})
    # --- End History Preparation ---

    # --- Get Other Character Details ---
    all_chars = game.character_db.get_all_characters()
    other_character_details = [
        {
            # Get first name from set for display, or use ID as fallback
            "name": list(char.names)[0] if char.names else char.unique_id,
            # Get description from public_facts dict
            "description": char.public_facts.get("description", "An unknown figure."),
        }
        # Filter out self using unique_id, ensure description exists
        for char in all_chars
        if char.unique_id != selected_char_obj.unique_id
        and char.public_facts.get("description")
    ]
    # --- End Get Other Details ---

    try:
        # Call the LLM API, passing other character details and current inventory
        # Also need to update the context passed to the LLM
        llm_context = selected_char_obj.private_facts.get("internal_description", "")
        response_data = generate_response(
            user_prompt,
            llm_context,
            history_to_send,
            other_character_details=other_character_details,
            character_inventory=selected_char_obj.inventory,
        )

        final_response_text = ""
        player_affected = False  # Initialize default value
        # Default to error if type missing
        response_type = response_data.get("type", "error")

        if response_type == "text":
            final_response_text = response_data.get(
                "content", "(Error processing response)"
            )
            # player_affected remains False for text responses
        elif response_type == "function_call":
            func_name = response_data.get("name")
            func_args = response_data.get("args", {})
            print(f"---> Received function call: {func_name} with args: {func_args}")

            # --- Execute Function Call using Game methods ---
            action_result = "(Error executing action)"  # Default error message
            sender_id = selected_char_obj.unique_id  # Use unique_id
            recipient_name = func_args.get("recipient_name")

            if not recipient_name:
                action_result = "(Error: Tool call missing recipient_name)"
            elif func_name == "give_money":
                amount = func_args.get("amount")
                if isinstance(amount, int):
                    print(
                        f"---> Attempting to call game.transfer_money for {func_name}"
                    )
                    action_result = game.transfer_money(
                        sender_id, recipient_name, amount
                    )
                else:
                    action_result = "(Error: Invalid or missing amount for give_money)"
            elif func_name == "give_item":
                item_name = func_args.get("item_name")
                if item_name:
                    print(f"---> Attempting to call game.transfer_item for {func_name}")
                    action_result = game.transfer_item(
                        sender_id, recipient_name, item_name
                    )
                else:
                    action_result = "(Error: Missing item_name for give_item)"
            else:
                action_result = f"(Attempted unknown action: {func_name})"

            # Use the result of the action as the response text
            final_response_text = action_result
            # --- End Execute Function Call ---

            # --- Determine if player inventory might have changed ---
            if (
                recipient_name.lower() == "player"
                and not action_result.startswith("(Error")
                and not action_result.startswith("(Cannot")
            ):
                # If recipient is player and the action didn't obviously fail
                player_affected = True
            # --- End Determine Player Affected ---

        elif response_type == "error":
            final_response_text = response_data.get("content", "(Unknown LLM error)")
            print(f"LLM API Error: {final_response_text}")
            player_affected = False  # Error means no change
        else:
            final_response_text = "(Received unexpected response type)"
            print(f"Unknown response type: {response_type}")
            player_affected = False  # Unexpected type means no change

        # Add the final text (LLM response or action result) to history
        current_history.append({"role": "Character", "text": final_response_text})

        # Limit the *stored* history size after adding both messages
        conversation_histories[char_id] = current_history[-config.MAX_HISTORY :]
        # Include the flag in the response if player was affected
        response_payload = {"response": final_response_text}
        if response_type == "function_call" and player_affected:
            response_payload["player_inventory_updated"] = True

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
    if not game.character_db:
        return jsonify({"error": "Character database not available"}), 503

    character = game.character_db.get_character_by_name(character_name)

    if character and character.portrait_image_path:
        # Use the pre-calculated path stored on the character object
        try:
            logging.info(
                f"Serving portrait for '{character_name}' from stored path: {character.portrait_image_path}"
            )
            # send_from_directory needs directory and filename separately
            directory = os.path.dirname(character.portrait_image_path)
            filename = os.path.basename(character.portrait_image_path)
            return send_from_directory(directory, filename)
        except Exception as e:
            logging.error(
                f"Error sending file from path {character.portrait_image_path}: {e}"
            )
            return jsonify({"error": "Error serving image file"}), 500
    elif character:
        # Character exists but has no portrait path - return 404
        logging.warning(f"Portrait path not found for character: {character_name}")
        return jsonify({"error": "Image not found for this character"}), 404
    else:
        # Character not found in DB
        logging.warning(f"Character '{character_name}' not found for portrait request.")
        return jsonify({"error": "Character not found"}), 404


@app.route("/history/<character_name>")
def get_history(character_name):
    """Returns the conversation history for a given character."""
    if not game.character_db:
        return jsonify([])  # Return empty if DB not available
    # Find character by name to get their ID for history lookup
    character = game.character_db.get_character_by_name(character_name)
    if character and character.unique_id in conversation_histories:
        history = conversation_histories[character.unique_id]
        return jsonify(history[-config.MAX_HISTORY :])  # Apply limit again for safety
    else:
        # No history found for this character yet or character not found
        return jsonify([])


@app.route("/inventory/<character_name>")
def get_inventory(character_name):
    """Returns the inventory for a given character."""
    if not game.character_db:
        return jsonify({"error": "Character database not available"}), 503

    character = game.character_db.get_character_by_name(character_name)
    if character:
        # The inventory is directly on the character object now
        inventory = character.inventory
        # Ensure structure (optional, but safe)
        if "money" not in inventory:
            inventory["money"] = 0
        if "items" not in inventory:
            inventory["items"] = {}
        return jsonify(inventory)
    else:
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
