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
    # Use entity_db
    if game.entity_db:  # Check if DB loaded successfully
        # Get character entities
        all_char_entities = game.entity_db.get_entities_by_type("character")
        # Get the first name from the names set for display
        character_names = [
            list(entity.names)[0] if entity.names else "Unknown"  # Use entity.names
            for entity in all_char_entities  # Iterate over entities
        ]
    else:
        # Handle case where DB failed to load
        print("Warning: Entity DB not loaded, cannot populate character list.")

    return render_template("index.html", character_names=character_names)


@app.route("/chat", methods=["POST"])
def chat():
    """Handles incoming chat messages and returns LLM response."""
    # Use entity_db
    if not game.entity_db:
        return (
            jsonify({"error": "Entity database not available"}),
            503,
        )  # Service Unavailable

    data = request.json
    character_name = data.get("character_name")
    user_prompt = data.get("prompt")

    if not character_name or not user_prompt:
        return jsonify({"error": "Missing character name or prompt"}), 400

    # Find character entity using the game method (which uses entity_db)
    selected_char_entity = game.get_character_by_name(character_name)

    if not selected_char_entity:
        logging.warning(
            "Chat request failed: Character '%s' not found.", character_name
        )
        return jsonify({"error": "Character not found"}), 404

    # Use character entity's unique_id for history key
    char_id = selected_char_entity.unique_id
    if char_id not in conversation_histories:
        conversation_histories[char_id] = []
        logging.info("Initialized history for %s", char_id)

    current_history = conversation_histories[char_id]

    # --- History Preparation (Corrected) ---
    # 1. Prepare the history to send to the LLM (up to this point)
    history_to_send = current_history[-config.MAX_HISTORY :]

    # 2. Add user message to the stored history *after* preparing the list for the LLM
    current_history.append({"role": "Player", "text": user_prompt})
    # --- End History Preparation ---

    # --- Get Other Character Details ---
    # Get character entities
    all_char_entities = game.entity_db.get_entities_by_type("character")
    other_character_details = [
        {
            # Get first name from set for display, or use ID as fallback
            "name": list(entity.names)[0] if entity.names else entity.unique_id,
            # Get description from entity.data dict
            "description": entity.data.get("public_facts", {}).get(
                "description", "An unknown figure."
            ),
        }
        # Filter out self using unique_id
        for entity in all_char_entities  # Iterate over entities
        if entity.unique_id != selected_char_entity.unique_id
        # Ensure description exists in entity.data
        and entity.data.get("public_facts", {}).get("description")
    ]
    # --- End Get Other Details ---

    try:
        # Initialize response_payload
        response_payload = None

        # Call the LLM API, passing other character details and current inventory
        # Access context and inventory via entity.data
        llm_context = selected_char_entity.data.get("private_facts", {}).get(
            "internal_description", ""
        )
        character_inventory = selected_char_entity.data.get("inventory", {})
        response_data = generate_response(
            user_prompt,
            llm_context,
            history_to_send,
            other_character_details=other_character_details,
            character_inventory=character_inventory,
        )

        # --- Add Logging to inspect response_data ---
        logging.info("--- LLM Response Data ---")
        logging.info(response_data)
        logging.info("-------------------------")
        # --- End Logging ---

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
            # Extract the dialogue part preceding the function call
            # Assuming the raw LLM response is available (need to check generate_response)
            # For now, let's assume `response_data["content"]` holds the full original text
            # If not, `generate_response` needs adjustment or we parse `response_data` differently.
            # Let's assume `response_data["text_content"]` holds the dialogue part.

            # Placeholder: Extract text before the function call marker if possible
            # This depends heavily on how `generate_response` structures its output
            dialogue_part = response_data.get(
                "text_content", ""
            )  # Prefer a dedicated text field
            if (
                not dialogue_part and "content" in response_data
            ):  # Fallback to parsing content
                content_str = response_data["content"]
                if isinstance(content_str, str) and "[ACTION:" in content_str:
                    dialogue_part = content_str.split("[ACTION:", 1)[0].strip()
                elif isinstance(
                    content_str, str
                ):  # No action marker, but maybe function call was separate?
                    dialogue_part = content_str.strip()

            func_name = response_data.get("name")
            func_args = response_data.get("args", {})
            print(f"---> Received function call: {func_name} with args: {func_args}")

            # --- Execute Function Call using Game methods ---
            action_result = "(Error executing action)"  # Default error message
            sender_id = selected_char_entity.unique_id  # Use unique_id
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
                item_id = func_args.get("item_id")
                if item_id:
                    print(
                        f"---> Attempting to call game.transfer_item for {func_name} with ID: {item_id}"
                    )
                    action_result = game.transfer_item(
                        sender_id, recipient_name, item_id
                    )
                else:
                    action_result = "(Error: Missing item_id for give_item)"
            else:
                action_result = f"(Attempted unknown action: {func_name})"
            # --- End Execute Function Call ---

            # Combine dialogue and action result for the final text
            # final_response_text = dialogue_part
            # if action_result: # Add action result if it exists
            #     # Add a space or newline for separation?
            #     final_response_text += f"\n{action_result}"

            # --- Determine if player inventory might have changed ---
            player_affected = False  # Reset flag
            if (
                recipient_name is not None  # Ensure recipient was parsed
                and recipient_name.lower() == "player"
                and not action_result.startswith("(Error")
                and not action_result.startswith("(Cannot")
            ):
                player_affected = True
            # --- End Determine Player Affected ---

            # Add dialogue and action result to history separately? Or combined?
            # For now, add combined for LLM context, but send separately to UI.
            history_entry_text = dialogue_part
            if action_result:
                history_entry_text += f"\n{action_result}"
            current_history.append({"role": "Character", "text": history_entry_text})

            # Prepare response payload with separate fields
            response_payload = {
                "response": dialogue_part,  # The character dialogue
                "action_result": action_result,  # The system action text
            }
            if player_affected:
                response_payload["player_inventory_updated"] = True

        elif response_type == "error":
            final_response_text = response_data.get("content", "(Unknown LLM error)")
            print(f"LLM API Error: {final_response_text}")
            # Add error message to history
            current_history.append({"role": "Character", "text": final_response_text})
            response_payload = {"response": final_response_text}
            player_affected = False

        else:  # Should be response_type == "text"
            final_response_text = response_data.get("content", "(Empty text response)")
            # Add the final text (LLM response or action result) to history
            current_history.append({"role": "Character", "text": final_response_text})
            response_payload = {"response": final_response_text}
            player_affected = False

        # Limit the *stored* history size after adding message
        conversation_histories[char_id] = current_history[-config.MAX_HISTORY :]

        return jsonify(response_payload)

    except Exception as e:
        print(f"Error processing LLM response or function call: {e}")
        # Log the exception traceback for more detail if needed
        # import traceback
        # traceback.print_exc()
        return jsonify({"error": "Internal server error processing response."}), 500


@app.route("/character_image/<character_name>")
def character_image(character_name):
    """Serves the character's portrait image."""
    # Use entity_db
    if not game.entity_db:
        return jsonify({"error": "Entity database not available"}), 503

    # Use game method to find character entity
    character_entity = game.get_character_by_name(character_name)

    # Check entity and its portrait path
    if character_entity and character_entity.portrait_image_path:
        # Use the pre-calculated path stored on the entity object
        try:
            logging.info(
                "Serving portrait for '%s' from stored path: %s",
                character_name,
                character_entity.portrait_image_path,
            )
            # send_from_directory needs directory and filename separately
            directory = os.path.dirname(character_entity.portrait_image_path)
            filename = os.path.basename(character_entity.portrait_image_path)
            return send_from_directory(directory, filename)
        except Exception as e:
            logging.error(
                "Error sending file from path %s: %s",
                character_entity.portrait_image_path,
                e,
            )
            return jsonify({"error": "Error serving image file"}), 500
    elif character_entity:
        # Character entity exists but has no portrait path - return 404
        logging.warning("Portrait path not found for character: %s", character_name)
        return jsonify({"error": "Image not found for this character"}), 404
    else:
        # Character entity not found in DB
        logging.warning(
            "Character '%s' not found for portrait request.", character_name
        )
        return jsonify({"error": "Character not found"}), 404


@app.route("/history/<character_name>")
def get_history(character_name):
    """Returns the conversation history for a given character."""
    # Use entity_db
    if not game.entity_db:
        return jsonify([])  # Return empty if DB not available
    # Find character entity by name to get their ID for history lookup
    character_entity = game.get_character_by_name(character_name)
    # Use entity unique_id
    if character_entity and character_entity.unique_id in conversation_histories:
        history = conversation_histories[character_entity.unique_id]
        return jsonify(history[-config.MAX_HISTORY :])  # Apply limit again for safety
    else:
        # No history found for this character entity yet or character not found
        return jsonify([])


@app.route("/inventory/<character_name>")
def get_inventory(character_name):
    """Returns the inventory for a given character."""
    # Use entity_db
    if not game.entity_db:
        return jsonify({"error": "Entity database not available"}), 503

    # Find character entity
    character_entity = game.get_character_by_name(character_name)
    if character_entity:
        # Access inventory via entity.data, provide default
        inventory = character_entity.data.get("inventory", {"money": 0, "items": {}})
        return jsonify(inventory)
    else:
        return jsonify({"error": "Character not found"}), 404


@app.route("/player_inventory")
def get_player_inventory():
    """Returns the player's current inventory."""
    if not game.entity_db:
        return jsonify({"error": "Entity database not available"}), 503

    player_entity = game.entity_db.get_entity_by_id("player_01")
    if player_entity:
        inventory = player_entity.data.get("inventory", {"money": 0, "items": {}})
        return jsonify(inventory)
    else:
        logging.error("Could not find player entity 'player_01' for inventory request.")
        return jsonify({"error": "Player entity not found"}), 404


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
    app.run(debug=True)
