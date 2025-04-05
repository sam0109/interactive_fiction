"""In-memory implementation of the ItemDatabase interface."""

import os
import json
from typing import List, Optional, Dict, Set
import logging

# Import the interface and data structures
from .item_db import ItemDatabase, Item
from thefuzz import process


class InMemoryItemDB(ItemDatabase):
    """Stores and retrieves item data entirely in memory, loaded on initialization."""

    def __init__(self, json_file_path: str):
        """Initializes the database by loading item data from a single JSON file.

        Args:
            json_file_path: The path to the JSON file containing a list of item
                dictionaries.

        Raises:
            FileNotFoundError: If the JSON file does not exist.
            ValueError: If the file is invalid JSON, or contains invalid item data.
        """
        self._items: Dict[str, Item] = {}
        logging.info("Initializing InMemoryItemDB from: %s", json_file_path)

        if not os.path.isfile(json_file_path):
            raise FileNotFoundError(f"Item data file not found: {json_file_path}")

        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                item_data_list = json.load(f)

            if not isinstance(item_data_list, list):
                raise ValueError("Item data file must contain a JSON list.")

            loaded_count = 0
            for i, data in enumerate(item_data_list):
                data["_source_file"] = json_file_path  # Add source for error reporting
                self._process_and_add_item_data(data)
                loaded_count += 1

            logging.info(
                "Finished initialization. Loaded %d items from %s.",
                loaded_count,
                json_file_path,
            )

        except json.JSONDecodeError as e:
            logging.error("Invalid JSON in file %s: %s", json_file_path, e)
            raise ValueError(f"Invalid JSON in {json_file_path}") from e
        except (ValueError, TypeError) as e:
            # Error during item processing/validation
            logging.error("Invalid item data in %s: %s", json_file_path, e)
            raise  # Re-raise the specific error (ValueError/TypeError)
        except Exception as e:
            logging.exception(
                "Unexpected error loading items from %s: %s", json_file_path, e
            )
            raise RuntimeError(
                f"Unexpected error loading items from {json_file_path}"
            ) from e

    @classmethod
    def get_from_data(cls, item_data: List[Dict]) -> "InMemoryItemDB":
        """Creates a database instance from a list of item data dictionaries."""
        db_instance = cls.__new__(cls)  # Create instance without calling __init__
        db_instance._items = {}
        logging.info(
            "Initializing InMemoryItemDB from data list (%d items)", len(item_data)
        )

        loaded_count = 0
        for i, data in enumerate(item_data):
            try:
                db_instance._process_and_add_item_data(data)
                loaded_count += 1
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Failed to process item data at index {i}: {e}"
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"Unexpected error processing item data at index {i}"
                ) from e

        logging.info(
            "Finished initialization from data. Loaded %d items.", loaded_count
        )
        return db_instance

    # --- Helper Method ---
    def _process_and_add_item_data(self, data: Dict):
        """Parses an item data dictionary and adds the Item to the DB."""

        unique_id = data.get("unique_id", "")  # Get ID for validation/adding

        # Ensure names are converted to a set
        names_list = data.get("names", [])
        source = data.get("_source_file", "input data")
        if not isinstance(names_list, list):
            raise TypeError(
                f"Source '{source}', Item '{unique_id}': 'names' field must be a list."
            )

        # Create Item object (performs validation)
        item = Item(
            unique_id=unique_id,
            names=set(names_list),
            description=data.get(
                "description", ""
            ),  # Pass empty string to trigger validation if missing
            properties=data.get("properties", {}),  # Optional
        )

        # Add item to DB
        self._add_item(item)

    # --- Core Data Storage and Access ---
    def _add_item(self, item: Item):
        """Internal helper to add an item."""
        if item.unique_id in self._items:
            raise ValueError(f"Duplicate item ID attempted: {item.unique_id}")
        self._items[item.unique_id] = item

    def get_item_by_name(self, name: str) -> Optional[Item]:
        """Looks up an item by name using fuzzy matching (thefuzz library)."""
        if not self._items:
            return None

        # Build name map on the fly
        name_to_id_map: Dict[str, str] = {}
        ambiguous_names: Set[str] = set()
        for item in self._items.values():
            for item_name in item.names:
                lower_name = item_name.lower()
                if (
                    lower_name in name_to_id_map
                    and name_to_id_map[lower_name] != item.unique_id
                ):
                    ambiguous_names.add(lower_name)
                name_to_id_map[lower_name] = item.unique_id

        if not name_to_id_map:
            return None  # No names registered

        lookup_name = name.lower()

        # Check for exact match first (respecting ambiguity)
        if lookup_name in name_to_id_map and lookup_name not in ambiguous_names:
            exact_match_id = name_to_id_map[lookup_name]
            return self._items.get(exact_match_id)

        # If exact match fails or is ambiguous, proceed to fuzzy matching
        all_known_names = list(name_to_id_map.keys())
        best_match, score = process.extractOne(lookup_name, all_known_names)

        match_threshold = 75  # Adjust as needed

        if score >= match_threshold:
            item_id = name_to_id_map.get(best_match)
            if item_id:
                if best_match in ambiguous_names:
                    logging.warning(
                        "Fuzzy match '%s' for item '%s' is ambiguous. "
                        "Returning one possibility.",
                        best_match,
                        name,
                    )
                return self._items.get(item_id)

        return None  # No good match found

    def get_item_by_id(self, item_id: str) -> Optional[Item]:
        """Retrieves an item by its unique ID."""
        return self._items.get(item_id)

    def get_all_items(self) -> List[Item]:
        """Returns a list of all loaded items."""
        return list(self._items.values())
