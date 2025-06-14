"""Configuration settings for the Interactive Fiction game."""

import json
import os

# --- API Key Loading ---
# Load the API key from a private JSON file
GEMINI_API_KEY = None
try:
    with open("keys.json", "r") as f:
        keys = json.load(f)
        GEMINI_API_KEY = keys.get("GEMINI_API_KEY")
except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
    print(f"Warning: Could not load GEMINI_API_KEY from keys.json: {e}")


# LLM Configuration (for utils/llm_api.py)
MODEL_NAME = "gemini-1.5-flash-latest"  # Stable flash model

GENERATION_CONFIG = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 256,
}

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Game Configuration (for core/game.py)
MAX_HISTORY = 1000  # Number of turns (player + character) to keep in history

# List of relative paths from project root to directories containing entity JSON files
ENTITY_DATA_DIRS = ["data"]

# Directory containing the generated character images
IMAGE_SAVE_DIR = "generated_images"

# --- Entity Loading Settings ---
# A set of entity types that are considered 'characters' for certain logic.
CHARACTER_TYPES = {"character"}

# A mapping from entity properties (from JSON) to Entity class attributes.
# This can be useful for more complex data mappings in the future.
# Example: {"hit_points": "hp"}
PROPERTY_MAPPING = {}
