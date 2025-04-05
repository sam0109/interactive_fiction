"""LLM API for accessing models."""

import json
import os
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# Import configuration settings
import config

# Get API Key from keys.json
# Expects a keys.json file in the same directory (or project root)
# with the format: {"GEMINI_API_KEY": "YOUR_API_KEY"}
GOOGLE_API_KEY = None  # Initialize to None
KEYS_FILE_PATH = "keys.json"  # Define the path to the keys file


with open(KEYS_FILE_PATH, "r", encoding="utf-8") as file:
    keys = json.load(file)
    GOOGLE_API_KEY = keys.get("GEMINI_API_KEY")  # Use .get for safer access
if not GOOGLE_API_KEY:
    # Keep this warning in case the key is present but empty
    raise ValueError(
        f"Warning: 'GEMINI_API_KEY' key found in {KEYS_FILE_PATH} but its"
        "value is empty or missing."
    )

# Initialize the client using settings from config.py
client = None
if GOOGLE_API_KEY:
    client = genai.Client(api_key=GOOGLE_API_KEY)
else:
    print(
        "Warning: Gemini client not initialized because API key was not loaded"
        "or configuration failed."
    )

# --- Define Tool Functions (Stubs) ---


def give_money(recipient_name: str, amount: int) -> str:
    """Give a specified amount of money to another character or the player.

    Args:
        recipient_name: Name of the character or 'Player' receiving the money.
        amount: The amount of money to give.
    """
    # This is just a stub for the API definition.
    # The actual logic will be handled in web_app.py based on the function call.
    print(f"[Stub] Called give_money: recipient={recipient_name}, amount={amount}")
    return f"(Action: Gave {amount} gold to {recipient_name})"


def give_item(recipient_name: str, item_name: str) -> str:
    """Give a specific item from your inventory to another character or the player.

    Args:
        recipient_name: Name of the character or 'Player' receiving the item.
        item_name: The name of the item to give.
    """
    # This is just a stub for the API definition.
    print(f"[Stub] Called give_item: recipient={recipient_name}, item={item_name}")
    return f"(Action: Gave {item_name} to {recipient_name})"


# List of function stubs for the API
api_tools = [give_money, give_item]


def generate_image(prompt: str, character_name: str, unique_id: str):
    """Generates an image using the prompt and saves it using the unique_id."""
    if not client:
        print("Error: Client not initialized. Check API Key.")
        return None

    if not os.path.exists(config.IMAGE_SAVE_DIR):
        try:
            os.makedirs(config.IMAGE_SAVE_DIR, exist_ok=True)
            print(f"Created directory: {config.IMAGE_SAVE_DIR}")
        except OSError as e:
            print(f"Error creating directory {config.IMAGE_SAVE_DIR}: {e}")
            return None  # Cannot proceed without directory

    # Use unique_id for the filename
    filename = f"{unique_id}.png"  # Assume PNG format
    filepath = os.path.join(config.IMAGE_SAVE_DIR, filename)

    try:
        # Add style modifiers to the prompt
        style_prefix = "Fantasy cartoon style, digital art illustration. "
        full_image_prompt = style_prefix + prompt

        # Generate the image using the client
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=full_image_prompt,  # Use the modified prompt
            config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
        )

        # Check if we got a valid response
        if not response.candidates or not response.candidates[0].content.parts:
            print("Warning: No response data")
            return None

        # Find the image part in the response
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                # Save the generated image
                image = Image.open(BytesIO(part.inline_data.data))
                image.save(filepath)
                print(
                    f"Successfully generated and saved image for '{character_name}' ({unique_id}): {filepath}"
                )
                return filepath

        print(
            f"Warning: No image data found in response for {character_name} ({unique_id})"
        )
        return None
    except Exception as e:
        print(f"Error generating image: {e}")
        return None


def generate_response(
    prompt,
    character_context,
    history=None,
    other_character_details=None,
    character_inventory=None,
):
    """Generates a response or function call from the Gemini LLM."""
    if not client:
        print("Error: Gemini client not initialized. Check API Key.")
        return {"type": "error", "content": "Client Initialization Error"}

    # Construct the history part (for contents argument)
    content_list = []
    if history:
        for turn in history:
            role = turn.get("role")
            text = turn.get("text")
            # Map roles to API roles ('user'/'model')
            api_role = (
                "user" if role == "Player" else "model" if role == "Character" else None
            )
            if api_role:
                content_list.append(
                    types.Content(role=api_role, parts=[types.Part(text=text)])
                )
            else:
                print(f"Warning: Skipping history turn with unknown role: {role}")
    # Add the current user prompt to contents
    content_list.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

    # Construct the SYSTEM INSTRUCTION
    # Character Context
    system_instruction_text = f"{character_context}\n"
    # Scene Context
    if other_character_details:
        system_instruction_text += (
            "\nScene context: Besides you, the following are also in the tavern:\n"
        )
        for char_detail in other_character_details:
            brief_desc = char_detail.get("description", "").split(".")[0]
            system_instruction_text += (
                f"- {char_detail.get('name', 'Someone')}: {brief_desc}\n"
            )
    # Inventory Context
    if character_inventory:
        system_instruction_text += "\nYour current inventory:\n"
        system_instruction_text += (
            f"- Money: {character_inventory.get('money', 0)} gold\n"
        )
        items = character_inventory.get("items", {})
        if items:
            system_instruction_text += "- Items:\n"
            for item, count in items.items():
                system_instruction_text += f"  - {item} (x{count})\n"
        else:
            system_instruction_text += "- Items: (None)\n"

    # --- Debug Print ---
    print("\n" + "-" * 20 + " System Instruction " + "-" * 20)
    print(system_instruction_text)
    print("-" * 20 + " End System Instruction " + "-" * 20 + "\n")
    print("\n" + "-" * 20 + " Sending Contents to LLM " + "-" * 20)
    print(content_list)
    print("-" * 20 + " End Contents " + "-" * 20 + "\n")
    # --- End Debug Print ---

    try:
        # Call the Gemini API using system_instruction and contents
        response = client.models.generate_content(
            model=config.MODEL_NAME,
            contents=content_list,  # Pass formatted history + current prompt
            config=types.GenerateContentConfig(
                system_instruction=system_instruction_text,  # Pass system prompt here
                tools=api_tools,
                # Explicitly disable auto execution
                automatic_function_calling={"disable": True},
                safety_settings=config.SAFETY_SETTINGS,
                **config.GENERATION_CONFIG,
            ),
        )

        # --- Debug Print Relevant Response Parts ---
        print("\n" + "-" * 20 + " Relevant LLM Response Parts " + "-" * 20)
        try:
            if response.candidates:
                first_candidate = response.candidates[0]
                print(f"Finish Reason: {first_candidate.finish_reason}")
                print("Content Parts:")
                for part in first_candidate.content.parts:
                    if part.text:
                        print(f"  - Text: {part.text.strip()}")
                    # Check for function call within the *main* content parts
                    if part.function_call:
                        print(
                            f"  - Function Call: {part.function_call.name}({dict(part.function_call.args)})"
                        )
                print("Safety Ratings:")
                for rating in first_candidate.safety_ratings:
                    print(f"  - {rating.category.name}: {rating.probability.name}")
                # Removed check for automatic_function_calling_history as it's disabled
                # if response.automatic_function_calling_history:
                #     print("Function Call History:")
                #     for call in response.automatic_function_calling_history:
                #         for part in call.parts:
                #             if part.function_call:
                #                 print(
                #                   f"  - Function Call: {part.function_call.name}({dict(part.function_call.args)})")
            else:
                print("No candidates found in response.")
            if response.prompt_feedback:
                print(f"Prompt Feedback: {response.prompt_feedback}")
        except Exception as e:
            print(f"Error extracting debug info: {e}")
            # Fallback to raw if extraction fails
            print("Raw response was:", response)
        print("-" * 20 + " End Relevant Response Parts " + "-" * 20 + "\n")
        # --- End Debug Print ---

        # --- Check Response Type --- (Revised to handle multiple parts)
        if not response.candidates:
            # Handle cases with no candidates (e.g., blocked prompt)
            if response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason
                print(
                    f"Warning: Response blocked due to safety reasons: {block_reason}"
                )
                return {
                    "type": "text",
                    "content": f"(I cannot speak of such things - {block_reason})",
                }
            else:
                print(
                    "Warning: Received an empty response (no candidates) from the API."
                )
                return {
                    "type": "text",
                    "content": "(I... hmm. I seem to have lost my train of thought.)",
                }

        first_candidate = response.candidates[0]
        # Iterate through all parts to find a function call first
        found_function_call = None
        for part in first_candidate.content.parts:
            if part.function_call:
                found_function_call = part.function_call
                break  # Found it, no need to check further parts

        if found_function_call:
            print(f"LLM requested function call: {found_function_call.name}")
            # --- Debug Print Raw Function Call ---
            print(f"--> Raw Function Call Object: {found_function_call}")
            # --- End Debug Print ---
            return {
                "type": "function_call",
                "name": found_function_call.name,
                "args": dict(found_function_call.args),
            }
        else:
            # If no function call found, look for the first text part
            first_text_part = ""
            for part in first_candidate.content.parts:
                if part.text:
                    first_text_part = part.text.strip()
                    break  # Found the first text part

            if first_text_part:
                return {"type": "text", "content": first_text_part}
            else:
                # Handle cases where there's no function call AND no text (unlikely but possible)
                print(
                    "Warning: Received candidate parts with no function call or text:",
                    first_candidate.content.parts,
                )
                return {
                    "type": "text",
                    "content": "(I seem to be having trouble formulating a response...)",
                }

    except Exception as e:
        # General error handling (consider adding more specific exceptions)
        print(f"An error occurred calling the Gemini API: {e}")
        return {
            "type": "error",
            "content": "(My mind feels muddled right now... Try again in a moment.)",
        }
