import os
import json
import sys

# Add the project root to the Python path to allow importing modules like config and utils
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import necessary modules from the project
import config
from utils.llm_api import generate_image # Assuming generate_image is ready in llm_api

def generate_missing_character_images():
    """
    Scans the character directory, finds characters without images,
    and generates images for them using their description.
    """
    print(f"Checking for missing character images in '{config.IMAGE_SAVE_DIR}'...")
    if not os.path.exists(config.CHARACTER_DIR):
        print(f"Error: Character directory '{config.CHARACTER_DIR}' not found.")
        return

    generated_count = 0
    skipped_count = 0
    no_description_count = 0
    error_count = 0

    # Ensure the image save directory exists
    if not os.path.exists(config.IMAGE_SAVE_DIR):
        try:
            os.makedirs(config.IMAGE_SAVE_DIR, exist_ok=True)
            print(f"Created image directory: {config.IMAGE_SAVE_DIR}")
        except OSError as e:
            print(f"Error creating image directory {config.IMAGE_SAVE_DIR}: {e}")
            return # Cannot proceed without the directory

    for filename in os.listdir(config.CHARACTER_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(config.CHARACTER_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    char_data = json.load(f)
                    char_name = char_data.get('name')
                    char_description = char_data.get('description')

                    if not char_name:
                        print(f"Warning: Skipping {filename}, missing 'name'.")
                        error_count += 1
                        continue

                    if not char_description:
                        print(f"Skipping image generation for '{char_name}': No 'description' found.")
                        no_description_count += 1
                        continue

                    # Determine expected image path
                    safe_name = "".join(c for c in char_name if c.isalnum() or c in (' ', '_')).rstrip()
                    safe_name = safe_name.replace(' ', '_').lower()
                    image_filename = f"{safe_name}.png"
                    image_filepath = os.path.join(config.IMAGE_SAVE_DIR, image_filename)

                    if os.path.exists(image_filepath):
                        print(f"Image for '{char_name}' already exists at '{image_filepath}'. Skipping.")
                        skipped_count += 1
                    else:
                        print(f"Generating image for '{char_name}'...")
                        # Use the description as the prompt
                        try:
                            # generate_image requires description and name
                            generate_image(char_description, char_name)
                            print(f"Successfully generated image for '{char_name}'.")
                            generated_count += 1
                        except Exception as e:
                            print(f"Error generating image for '{char_name}': {e}")
                            error_count += 1

            except json.JSONDecodeError:
                print(f"Warning: Skipping file {filename}. Invalid JSON format.")
                error_count += 1
            except Exception as e:
                print(f"Warning: Skipping file {filename}. Error loading: {e}")
                error_count += 1

    print("--- Image Generation Summary ---")
    print(f"Generated: {generated_count}")
    print(f"Skipped (already exists): {skipped_count}")
    print(f"Skipped (no description): {no_description_count}")
    print(f"Errors: {error_count}")
    print("------------------------------")

if __name__ == "__main__":
    print("Starting character image generation utility...")
    # Note: This requires Google Cloud authentication (gcloud auth login)
    # and project configuration (gcloud config set project YOUR_PROJECT_ID)
    # if using the Vertex AI image generation.
    generate_missing_character_images()
    print("Image generation process finished.") 