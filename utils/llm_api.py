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


def generate_image(prompt, character_name):
  """Generates an image using and saves it to be used in the future."""
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

  # Create a simple, safe filename based on character name
  safe_name = "".join(
      c for c in character_name if c.isalnum() or c in (" ", "_")
  ).rstrip()
  safe_name = safe_name.replace(" ", "_").lower()
  filename = f"{safe_name}.png"  # Assume PNG format
  filepath = os.path.join(config.IMAGE_SAVE_DIR, filename)

  try:
    # Generate the image using the client
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp-image-generation",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["Text", "Image"]
        )
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
        print(f"Successfully generated and saved image: {filepath}")
        return filepath

    print("Warning: No image data found in response")
    return None
  except Exception as e:
    print(f"Error generating image: {e}")
    return None


def generate_response(
        prompt, character_context, history=None, other_character_details=None):
  """Generates a response from the Gemini LLM using the client."""
  if not client:
    print("Error: Gemini client not initialized. Check API Key.")
    return (
        "I seem to be at a loss for words right now."
        "(Client Initialization Error)"
    )

  # Construct the history part of the prompt
  history_string = ""
  if history:
    for turn in history:
      role = turn.get("role", "Unknown")
      text = turn.get("text", "")
      if role == "Player":
        history_string += f"Player: {text}\n"
      elif role == "Character":
        history_string += f"You: {text}\n"
      else:
        history_string += f"{role}: {text}\n"
    history_string += "\n"

  # Construct the scene context (who else is present and brief description)
  scene_context = ""
  if other_character_details:
    scene_context += ("Scene context: Besides you, the following are also in "
                      "the tavern:\n")
    for char_detail in other_character_details:
      # Extract a brief part of the description (e.g., first sentence or key
      # phrase) This is a simple example; more sophisticated extraction could
      # be used.
      brief_desc = char_detail.get("description", "").split(".")[0]
      scene_context += f"- {char_detail.get('name', 'Someone')}: {brief_desc}\n"
    scene_context += "\n"  # Add a newline after scene context

  # Combine character context, scene context, history, and the current player
  # prompt
  full_prompt = f"""{character_context}

{scene_context}{history_string}Player: {prompt}

You:"""

  # --- Debug Print ---
  print("\n" + "-" * 20 + " Sending Prompt to LLM " + "-" * 20)
  print(full_prompt)
  print("-" * 20 + " End Prompt " + "-" * 20 + "\n")
  # --- End Debug Print ---

  try:
    # Call the Gemini API using the client
    response = client.models.generate_content(
        model=config.MODEL_NAME,  # Use the model from config
        contents=full_prompt,
        config=types.GenerateContentConfig(
            safety_settings=config.SAFETY_SETTINGS,
            **config.GENERATION_CONFIG  # Unpack the dictionary here
        )
    )

    # Handle potential safety blocks or empty responses
    if not response.candidates or not response.candidates[0].content.parts:
      if response.prompt_feedback.block_reason:
        print(
            "Warning: Response blocked due to safety reasons:"
            f" {response.prompt_feedback.block_reason}"
        )
        return ("(I cannot speak of such things -"
                f" {response.prompt_feedback.block_reason})")
      else:
        print("Warning: Received an empty response from the API.")
        return "(I... hmm. I seem to have lost my train of thought.)"

    # Success! Return the response.
    llm_response = response.text.strip()
    return llm_response

  except Exception as e:
    # General error handling (consider adding more specific exceptions)
    print(f"An error occurred calling the Gemini API: {e}")
    return "(My mind feels muddled right now... Try again in a moment.)"
