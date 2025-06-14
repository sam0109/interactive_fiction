"""In-memory implementation of the EntityDatabase interface."""

import os
import json
import logging
from typing import List, Optional, Dict, Set, Any

# Import configuration settings
import config

# Import the interface and data structures
from entities.entity_db import EntityDatabase
from entities.entity import Entity


class InMemoryEntityDB(EntityDatabase):
    """Stores and retrieves entity data entirely in memory."""

    def __init__(self):
        """Initializes an empty entity database."""
        # Use dict[str, Entity] when type hint support is robust
        self._entities: Dict[str, Entity] = {}
        logging.info("Initialized empty InMemoryEntityDB.")

    @classmethod
    def from_directories(cls, directory_paths: List[str]) -> "InMemoryEntityDB":
        """Creates a database instance by loading from JSON files in specified directories."""
        db_instance = cls()  # Initializes with an empty _entities dict
        # Use % formatting for logging
        logging.info(
            "Initializing InMemoryEntityDB from directories: %s", directory_paths
        )

        loaded_count = 0
        error_files = []
        processed_ids = set()

        for directory_path in directory_paths:
            if not os.path.isdir(directory_path):
                logging.warning("Directory not found, skipping: %s", directory_path)
                continue

            logging.info("Processing directory: %s", directory_path)
            for filename in os.listdir(directory_path):
                # Expect all .json files to contain a LIST of entities
                if filename.endswith(".json"):
                    filepath = os.path.join(directory_path, filename)
                    try:
                        logging.info("Processing entity list file: %s", filepath)
                        with open(filepath, "r", encoding="utf-8") as f:
                            entity_data_list = json.load(f)

                        if not isinstance(entity_data_list, list):
                            raise ValueError(
                                f"File {filepath} must contain a JSON list of entities."
                            )

                        # Process each entity dictionary in the list
                        for entity_data in entity_data_list:
                            # Ensure it's a dict before parsing
                            if not isinstance(entity_data, dict):
                                logging.warning(
                                    "Skipping non-dictionary item in list within %s",
                                    filepath,
                                )
                                continue

                            # Add source file for better error messages
                            entity_data["_source_file"] = filepath
                            entity = db_instance._parse_entity_data(entity_data)

                            if entity.unique_id in processed_ids:
                                raise ValueError(
                                    f"Duplicate unique_id found: {entity.unique_id} from file {filepath}"
                                )
                            processed_ids.add(entity.unique_id)
                            db_instance._add_entity(entity)
                            loaded_count += 1  # Increment for each entity in the list

                    except (json.JSONDecodeError, ValueError, TypeError) as e:
                        logging.error(
                            "Failed to load entities from %s: %s", filepath, e
                        )
                        error_files.append(filepath)
                        # Continue loading other files
                    except Exception as e:
                        logging.exception(
                            "Unexpected error processing file %s: %s", filepath, e
                        )
                        error_files.append(filepath)
                        # Optionally re-raise for critical errors

        logging.info("Finished initialization. Loaded %d entities.", loaded_count)
        if error_files:
            logging.error("Errors encountered loading files: %s", error_files)
            # Optionally raise an error if any file failed to load
            # raise ValueError(f"Failed to load one or more entity files: {error_files}")

        return db_instance

    @classmethod
    def from_data(cls, entity_data: List[Dict[str, Any]]) -> "InMemoryEntityDB":
        """Creates a database instance from a list of entity data dictionaries."""
        db_instance = cls()
        logging.info(
            "Initializing InMemoryEntityDB from data list (%d items)", len(entity_data)
        )
        loaded_count = 0
        processed_ids = set()

        for i, data in enumerate(entity_data):
            try:
                entity = db_instance._parse_entity_data(data)
                if entity.unique_id in processed_ids:
                    raise ValueError(
                        f"Duplicate unique_id found at index {i}: {entity.unique_id}"
                    )
                processed_ids.add(entity.unique_id)
                db_instance._add_entity(entity)
                loaded_count += 1
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Failed to process entity data at index {i}: {e}"
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"Unexpected error processing entity data at index {i}"
                ) from e

        logging.info(
            f"Finished initialization from data. Loaded {loaded_count} entities."
        )
        return db_instance

    # --- Helper Methods ---

    def _parse_entity_data(self, data: Dict[str, Any]) -> Entity:
        """Parses a dictionary and creates an Entity object, handling common fields."""
        unique_id = data.pop("unique_id", "")
        entity_type = data.pop("entity_type", "")
        
        # The 'facts' dictionary is now the main payload.
        # We expect it to be present and will pass it directly.
        facts = data.pop("facts", {})
        source = data.get("_source_file", "input data")

        if not unique_id or not entity_type:
            raise ValueError(f"Source '{source}': 'unique_id' and 'entity_type' are required.")

        if not isinstance(facts, dict):
            raise TypeError(
                f"Source '{source}', Entity '{unique_id}': 'facts' field must be a dictionary."
            )

        # The 'facts' dictionary from JSON is now the primary data payload for the entity.
        # Any other top-level keys in the JSON that are not 'unique_id' or 'entity_type'
        # will also be passed in the 'data' dictionary.
        entity = Entity(
            unique_id=unique_id,
            entity_type=entity_type,
            data={**data, **facts},  # Merge facts and any other remaining data
        )

        # --- Set Portrait Path (Example for characters) ---
        # This logic might need refinement depending on how portraits are associated
        if entity.entity_type == "character":
            image_filename = f"{entity.unique_id}.png"
            if hasattr(config, "IMAGE_SAVE_DIR") and config.IMAGE_SAVE_DIR:
                expected_path = os.path.join(config.IMAGE_SAVE_DIR, image_filename)
                if os.path.exists(expected_path):
                    entity.portrait_image_path = expected_path
                else:
                    entity.portrait_image_path = None
            else:
                if not hasattr(config, "IMAGE_SAVE_DIR"):
                    logging.debug(
                        "config.IMAGE_SAVE_DIR not set. Cannot determine portrait paths."
                    )
                entity.portrait_image_path = None
        # --- End Set Portrait Path ---

        return entity

    def _add_entity(self, entity: Entity):
        """Internal helper to add an entity to the internal dictionary."""
        if not entity.unique_id:
            raise ValueError("Attempted to add entity with empty unique_id")
        if entity.unique_id in self._entities:
            # This check should ideally happen during loading (as in from_directories)
            # but added here as a safeguard.
            logging.warning("Duplicate entity ID overwrite: %s", entity.unique_id)
            # raise ValueError(f"Duplicate entity ID attempted: {entity.unique_id}")
        self._entities[entity.unique_id] = entity

    # --- Database Query Methods ---

    def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """Retrieves an entity by its unique ID."""
        return self._entities.get(entity_id)

    def get_all_entities(self) -> List[Entity]:
        """Returns a list of all entities in the database."""
        return list(self._entities.values())

    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """Returns a list of all entities of a given type."""
        return [e for e in self._entities.values() if e.entity_type == entity_type]
