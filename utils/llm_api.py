# Placeholder for interacting with an LLM API

# import requests # Example, if using a REST API
# import openai # Example, if using OpenAI

# Example API Key setup (replace with secure method like environment variables)
# API_KEY = "YOUR_API_KEY_HERE"

import json # Add this import
import os
import textwrap # For formatting markdown output nicely
import google.generativeai as generativeai
import time # Import time for sleep
from google.genai import types

# Import configuration settings
import config

# Get API Key from keys.json
# Expects a keys.json file in the same directory (or project root)
# with the format: {"GEMINI_API_KEY": "YOUR_API_KEY"}
GOOGLE_API_KEY = None # Initialize to None
KEYS_FILE_PATH = 'keys.json' # Define the path to the keys file

try:
    with open(KEYS_FILE_PATH, 'r') as f:
        keys = json.load(f)
        GOOGLE_API_KEY = keys.get('GEMINI_API_KEY') # Use .get for safer access
    if not GOOGLE_API_KEY:
         # Keep this warning in case the key is present but empty
         print(f"Warning: 'GEMINI_API_KEY' key found in {KEYS_FILE_PATH} but its value is empty or missing.")
         GOOGLE_API_KEY = None # Treat empty/missing key
except FileNotFoundError:
    print(f"Error: API key file '{KEYS_FILE_PATH}' not found. Please create it with your API key.")
    # Consider exiting or raising an exception here if the key is critical
except json.JSONDecodeError:
    print(f"Error: Could not decode JSON from '{KEYS_FILE_PATH}'. Make sure it's valid JSON format.")
    # Consider exiting or raising
except Exception as e: # Catch other potential file reading errors
     print(f"An unexpected error occurred loading the API key from {KEYS_FILE_PATH}: {e}")
     GOOGLE_API_KEY = None

# Configure genai only if the key was successfully loaded
if GOOGLE_API_KEY:
    try:
        generativeai.configure(api_key=GOOGLE_API_KEY)
    except Exception as e:
        print(f"Error configuring Google AI SDK with API key: {e}")
        GOOGLE_API_KEY = None
else:
     pass

# Initialize the model using settings from config.py
model = None
if GOOGLE_API_KEY:
    try:
        model = generativeai.GenerativeModel(
            model_name=config.MODEL_NAME,
            generation_config=config.GENERATION_CONFIG,
            safety_settings=config.SAFETY_SETTINGS
        )
    except Exception as e:
         print(f"Error initializing Gemini model: {e}")
         model = None
else:
    print("Warning: Gemini model not initialized because API key was not loaded or configuration failed.")

def generate_image(prompt, character_name):
    """Generates an image using Imagen on Vertex AI if none exists and saves it to be used in the future."""
    if not os.path.exists(config.IMAGE_SAVE_DIR):
        try:
            os.makedirs(config.IMAGE_SAVE_DIR, exist_ok=True)
            print(f"Created directory: {config.IMAGE_SAVE_DIR}")
        except OSError as e:
            print(f"Error creating directory {config.IMAGE_SAVE_DIR}: {e}")
            return None # Cannot proceed without directory

    # Create a simple, safe filename based on character name
    safe_name = "".join(c for c in character_name if c.isalnum() or c in (' ', '_')).rstrip()
    safe_name = safe_name.replace(' ', '_').lower()
    filename = f"{safe_name}.png" # Assume PNG format
    filepath = os.path.join(config.IMAGE_SAVE_DIR, filename)

    client = genai.Client(api_key=GOOGLE_API_KEY)

    response = client.models.generate_images(
        model='imagen-3.0-generate-002',
        prompt=prompt,

    config=types.GenerateImagesConfig(
            number_of_images= 1,
        )
    )

    with open(filepath, "wb") as f:
        f.write(response.generated_images[0].image.image_bytes)

    return filepath

def generate_response(prompt, character_context, history=None, retries=1, delay=2):
    """Generates a response from the Gemini LLM with basic retry logic."""
    if not model:
        print("Error: Gemini model not initialized. Check API Key.")
        return "I seem to be at a loss for words right now. (Model Initialization Error)"

    # Construct the full prompt for the LLM
    history_string = ""
    if history:
        for turn in history:
            # Assuming history is a list of dicts like {'role': 'Player'/'Character', 'text': '...'}
            role = turn.get('role', 'Unknown')
            text = turn.get('text', '')
            if role == 'Player':
                history_string += f"Player: {text}\n"
            elif role == 'Character':
                # Use "You:" to represent the LLM's previous turns
                history_string += f"You: {text}\n"
            else:
                history_string += f"{role}: {text}\n" # Handle unexpected roles
        history_string += "\n" # Add a newline after the history

    # Combine context, history, and the current player prompt
    full_prompt = f"""{character_context}

{history_string}Player: {prompt}

You:""" # Adding "You:" helps guide the model

    attempt = 0
    while attempt <= retries:
        try:
            # Call the Gemini API
            response = model.generate_content(full_prompt)

            # Handle potential safety blocks or empty responses
            if not response.candidates or not response.candidates[0].content.parts:
                if response.prompt_feedback.block_reason:
                    print(f"Warning: Response blocked due to safety reasons: {response.prompt_feedback.block_reason}")
                    # Maybe customize this based on character?
                    return f"(I cannot speak of such things - {response.prompt_feedback.block_reason})"
                else:
                    print("Warning: Received an empty response from the API.")
                    # Slightly more in-character fallback
                    return "(I... hmm. I seem to have lost my train of thought.)"

            # Success! Return the response.
            llm_response = response.text.strip()
            return llm_response

        except Exception as e:
            # Catch potential API errors or other issues
            print(f"An error occurred calling the Gemini API (Attempt {attempt + 1}/{retries + 1}): {e}")
            if attempt < retries:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                attempt += 1
            else:
                print("Max retries reached. Giving up.")
                # Final fallback on error after retries
                return "(My mind feels muddled right now... Try again in a moment.)"

    # Should not be reached if retries are handled correctly, but as a safeguard:
    return "(Something went quite wrong with my thoughts.)"

# --- Remove Placeholder ---
# placeholder_response = f"Well met, traveler. You mentioned '{prompt}'. Tell me more."
# print(f"LLM Placeholder Response: {placeholder_response}")
# return placeholder_response
# --- End Placeholder ---