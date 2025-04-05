"""In-memory implementation of the CharacterDatabase interface."""

import os
import json
import re
from typing import List, Optional, Dict, Set

# Import the interface and data structures
from .character_db import CharacterDatabase, Character
from thefuzz import process


class InMemoryCharacterDB(CharacterDatabase):
    """Stores and retrieves character data entirely in memory."""

    def __init__(self, directory_path: str):
        """Initializes the database by loading character data from JSON files.

        Args:
            directory_path: The path to the directory containing character JSON files.

        Raises:
            FileNotFoundError: If the directory does not exist.
            ValueError: If a file is invalid JSON, missing required fields,
                        or contains invalid character data (stops on first error).
        """
        self._characters: Dict[str, Character] = {}
        print(f"Initializing InMemoryCharacterDB from: {directory_path}")

        if not os.path.isdir(directory_path):
            raise FileNotFoundError(f"Character directory not found: {directory_path}")

        loaded_count = 0
        error_files = []
        for filename in os.listdir(directory_path):
            if filename.endswith(".json"):
                filepath = os.path.join(directory_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Use helper to process and add character
                    self._process_and_add_character_data(data)
                    loaded_count += 1
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    print(f"Error processing file {filename}: {e}")
                    error_files.append(filename)
                    # Decide on error handling: stop or continue?
                    # For constructor, maybe stop on first error?
                    raise ValueError(
                        f"Failed to load character from {filename}: {e}"
                    ) from e
                except Exception as e:
                    print(f"Unexpected error processing file {filename}: {e}")
                    error_files.append(filename)
                    raise RuntimeError(f"Unexpected error processing {filename}") from e

        print(f"Finished initialization. Loaded {loaded_count} characters.")
        if error_files:
            print(f"Errors encountered in files: {error_files}")

    @classmethod
    def from_data(cls, character_data: List[Dict]) -> "InMemoryCharacterDB":
        """Creates a database instance from a list of character data dictionaries."""
        db_instance = cls.__new__(cls)  # Create instance without calling __init__
        db_instance._characters = {}
        print(f"Initializing InMemoryCharacterDB from ({len(character_data)} items)")

        loaded_count = 0
        for i, data in enumerate(character_data):
            try:
                db_instance._process_and_add_character_data(data)
                loaded_count += 1
            except (ValueError, TypeError) as e:
                # Decide on error handling: stop or skip?
                # Let's stop for now.
                raise ValueError(
                    f"Failed to process character data at index {i}: {e}"
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"Unexpected error processing character data at index {i}"
                ) from e

        print(f"Finished initialization from data. Loaded {loaded_count} characters.")
        return db_instance

    # --- Helper Method ---
    def _process_and_add_character_data(self, data: Dict):
        """Parses a character data dictionary and adds the Character to the DB."""
        # --- Pre-process data for Character initialization ---
        raw_inventory_list = data.get("inventory", [])
        private_facts = data.get("private_facts", {})
        unique_id = data.get("unique_id", "")  # Get ID for validation/adding

        # Build initial inventory dict
        initial_inventory = {"money": 0, "items": {}}
        wealth_str = private_facts.get("wealth", "0")
        match = re.search(r"\d+", wealth_str)
        if match:
            initial_inventory["money"] = int(match.group(0))
        else:
            pass

        # Parse items
        temp_items = {}
        if raw_inventory_list:
            for item_str in raw_inventory_list:
                count_match = re.search(r"\(x(\d+)\)$", item_str)
                if count_match:
                    item_name = item_str[: count_match.start()].strip()
                    count = int(count_match.group(1))
                else:
                    item_name = item_str.strip()
                    count = 1
                if item_name:
                    temp_items[item_name] = temp_items.get(item_name, 0) + count
        initial_inventory["items"] = temp_items
        # --- End Pre-processing ---

        # Ensure names are converted to a set
        names_list = data.get("names", [])
        if not isinstance(names_list, list):
            # Use actual filename if available, otherwise indicate data error
            source = data.get("_source_file", "input data")
            raise TypeError(f"Source '{source}': 'names' field must be a list.")

        # Create Character object, passing the pre-built inventory
        # This will perform internal validation via __post_init__
        char = Character(
            unique_id=unique_id,
            names=set(names_list),
            public_facts=data.get("public_facts", {}),
            private_facts=private_facts,  # Pass the loaded private facts
            inventory=initial_inventory,  # Pass the constructed inventory
        )

        # Add character to DB (no name mapping here anymore)
        self._add_character(char)

    # --- Core Data Storage and Access ---
    def _add_character(self, char: Character):
        """Internal helper to add a character to the internal dictionary."""
        if char.unique_id in self._characters:
            raise ValueError(f"Duplicate character ID attempted: {char.unique_id}")
        self._characters[char.unique_id] = char

    def get_character_by_name(self, name: str) -> Optional[Character]:
        """Looks up a character by name using fuzzy matching (builds map on the fly)."""
        if not self._characters:  # No characters loaded
            return None

        # --- Build name map on the fly ---
        name_to_id_map: Dict[str, str] = {}
        ambiguous_names: Set[str] = set()
        for char in self._characters.values():
            for char_name in char.names:
                lower_name = char_name.lower()
                if (
                    lower_name in name_to_id_map
                    and name_to_id_map[lower_name] != char.unique_id
                ):
                    ambiguous_names.add(lower_name)
                name_to_id_map[lower_name] = char.unique_id
        # --- End build name map ---

        lookup_name = name.lower()

        # Check for exact match first (respecting ambiguity)
        if lookup_name in name_to_id_map and lookup_name not in ambiguous_names:
            exact_match_id = name_to_id_map[lookup_name]
            return self._characters.get(exact_match_id)

        # If exact match fails or is ambiguous, proceed to fuzzy matching
        all_known_names = list(name_to_id_map.keys())
        if not all_known_names:
            return None  # No names found to match against

        # Find the best fuzzy match above a certain threshold
        best_match, score = process.extractOne(lookup_name, all_known_names)

        match_threshold = 75

        if score >= match_threshold:
            char_id = name_to_id_map.get(best_match)
            if char_id:
                if best_match in ambiguous_names:
                    print(
                        f"Warning: Fuzzy match '{best_match}' for '{name}' is ambiguous. Returning one possibility."
                    )
                return self._characters.get(char_id)

        return None  # No good match found

    def get_character_by_id(self, character_id: str) -> Optional[Character]:
        """Retrieves a character by their unique ID."""
        return self._characters.get(character_id)

    def get_all_characters(self) -> List[Character]:
        """Returns a list of all loaded characters."""
        # Return a list of copies if Character objects were mutable complex types
        # Since they are dataclasses with simple types, returning list of references is
        # ok.
        return list(self._characters.values())
