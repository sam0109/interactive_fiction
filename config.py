"""Configuration settings for the Interactive Fiction game."""

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
CHARACTER_DIR = "characters"  # Directory containing character definition files
# Directory to save generated character images
IMAGE_SAVE_DIR = "generated_images"
