"""Unit tests for the generic EntityDatabase interface and InMemoryEntityDB implementation."""

import pytest
import json
import os
from pathlib import Path
from typing import Dict, List, Any

# Import the interface and implementation
from entities.entity_db import EntityDatabase
from entities.entity import Entity
from entities.in_memory_entity_db import InMemoryEntityDB

# --- Test Fixtures ---


@pytest.fixture
def sample_entity_data_char_1() -> Dict[str, Any]:
    """Provides sample data for a single character entity."""
    # Corresponds to old sample_char_data_1
    return {
        "unique_id": "guard_01",
        "entity_type": "character",
        "names": ["Gareth", "Guard"],
        # Character-specific data goes here (will be parsed into entity.data)
        "public_facts": {
            "description": "A stern-looking guard in city livery.",
            "post": "Gate Sentry",
        },
        "private_facts": {
            "internal_description": "Just trying to get through the shift.",
            "wealth": "30 gold coins",
            "secret": "Has a gambling problem.",
        },
        "inventory": {"money": 30, "items": {"spear_01": 1, "helmet_01": 1}},
    }


@pytest.fixture
def sample_entity_data_char_2() -> Dict[str, Any]:
    """Provides sample data for a second character entity."""
    # Corresponds to old sample_char_data_2
    return {
        "unique_id": "merchant_01",
        "entity_type": "character",
        "names": ["Silas", "Merchant"],
        "public_facts": {
            "description": "A thin man with darting eyes and fine, but worn, clothes.",
            "wares": "Sells 'exotic' goods (mostly trinkets).",
        },
        "private_facts": {
            "internal_description": "Always looking for the next big score.",
            "wealth": "Moderate savings",
            "secret": "Owes money to the Thieves Guild.",
        },
        "inventory": {
            "money": 50,
            "items": {"coin_purse_01": 1, "ledger_01": 1, "cart_key_01": 1},
        },
    }


@pytest.fixture
def sample_entity_data_item_1() -> Dict[str, Any]:
    """Provides sample data for a single item entity."""
    return {
        "unique_id": "spear_01",
        "entity_type": "item",
        "names": ["Spear", "Guard Spear"],
        # Item-specific data
        "description": "A standard issue guard's spear. Sharp and functional.",
        "properties": {"damage": "1d6", "type": "weapon", "range": "melee"},
    }


@pytest.fixture
def sample_entity_data_item_2() -> Dict[str, Any]:
    """Provides sample data for a second item entity."""
    return {
        "unique_id": "helmet_01",
        "entity_type": "item",
        "names": ["Helmet", "Guard Helmet"],
        "description": "A sturdy iron helmet, dented from use.",
        "properties": {"armor_class": 1, "type": "armor", "slot": "head"},
    }


@pytest.fixture
def sample_entity_list(
    sample_entity_data_char_1,
    sample_entity_data_char_2,
    sample_entity_data_item_1,
    sample_entity_data_item_2,
) -> List[Dict[str, Any]]:
    """Provides a list combining sample character and item entity data."""
    return [
        sample_entity_data_char_1,
        sample_entity_data_char_2,
        sample_entity_data_item_1,
        sample_entity_data_item_2,
    ]


@pytest.fixture
def populated_entity_db(sample_entity_list) -> EntityDatabase:
    """Provides a test entity database pre-populated using from_data."""
    try:
        db = InMemoryEntityDB.from_data(sample_entity_list)
        return db
    except Exception as e:
        pytest.fail(
            f"Fixture populated_entity_db failed during InMemoryEntityDB.from_data: {e}"
        )


@pytest.fixture
def temp_entity_dirs(
    tmp_path,
    sample_entity_data_char_1,
    sample_entity_data_char_2,
    sample_entity_data_item_1,
    sample_entity_data_item_2,
):
    """Creates temporary directories with character and item JSON files/list."""
    base_dir = tmp_path / "entities_root"
    base_dir.mkdir()
    char_dir = base_dir / "characters"
    char_dir.mkdir()
    item_dir = base_dir / "items"
    item_dir.mkdir()

    # Write character files, ensuring each contains a LIST of entities
    char1_file = char_dir / f"{sample_entity_data_char_1['unique_id']}.json"
    char1_file.write_text(json.dumps([sample_entity_data_char_1]), encoding="utf-8")
    char2_file = char_dir / f"{sample_entity_data_char_2['unique_id']}.json"
    char2_file.write_text(json.dumps([sample_entity_data_char_2]), encoding="utf-8")

    # Write items file (list format)
    items_list = [sample_entity_data_item_1, sample_entity_data_item_2]
    items_file = item_dir / "items.json"
    items_file.write_text(json.dumps(items_list), encoding="utf-8")

    # Return the list of directories to load from
    return [str(char_dir), str(item_dir)]


# --- Test Cases ---

# --- Initialization Tests ---


def test_init_from_directories_success(temp_entity_dirs):
    """Test initializing the DB from directories with mixed content types."""
    try:
        db = InMemoryEntityDB.from_directories(temp_entity_dirs)
        entities = db.get_all_entities()
        assert len(entities) == 4  # 2 chars + 2 items

        ids = {entity.unique_id for entity in entities}
        assert "guard_01" in ids
        assert "merchant_01" in ids
        assert "spear_01" in ids
        assert "helmet_01" in ids

        # Spot check a loaded character entity
        guard_entity = db.get_entity_by_id("guard_01")
        assert guard_entity is not None
        assert guard_entity.entity_type == "character"
        assert "Gareth" in guard_entity.data["names"]
        assert "public_facts" in guard_entity.data
        assert guard_entity.data["public_facts"]["post"] == "Gate Sentry"
        assert "inventory" in guard_entity.data
        assert guard_entity.data["inventory"]["money"] == 30

        # Spot check a loaded item entity
        spear_entity = db.get_entity_by_id("spear_01")
        assert spear_entity is not None
        assert spear_entity.entity_type == "item"
        assert "Spear" in spear_entity.data["names"]
        assert "description" in spear_entity.data
        assert spear_entity.data["description"].startswith("A standard issue")
        assert "properties" in spear_entity.data
        assert spear_entity.data["properties"]["type"] == "weapon"

    except Exception as e:
        pytest.fail(f"DB initialization from directories failed: {e}")


def test_init_from_directory_not_found(tmp_path):
    """Test initializing from a non-existent directory logs warning and loads 0."""
    # Note: from_directories now logs warning and continues, doesn't raise FileNotFoundError
    non_existent_dir = str(tmp_path / "nope")
    db = InMemoryEntityDB.from_directories([non_existent_dir])
    assert len(db.get_all_entities()) == 0


def test_init_from_directory_invalid_json(tmp_path):
    """Test initializing with invalid JSON logs error and skips file."""
    entity_dir = tmp_path / "invalid_json"
    entity_dir.mkdir()
    bad_file = entity_dir / "bad.json"
    bad_file.write_text("{ invalid json")
    # Expect 0 loaded, error logged (can't easily check logs in pytest without caplog)
    db = InMemoryEntityDB.from_directories([str(entity_dir)])
    assert len(db.get_all_entities()) == 0


def test_init_from_directory_partially_invalid_data(tmp_path, sample_entity_data_char_1):
    """Test initializing with a file containing some invalid entity data."""
    entity_dir = tmp_path / "invalid_data"
    entity_dir.mkdir()
    
    # Create a list with one valid and one invalid entity
    valid_data = sample_entity_data_char_1.copy()
    invalid_data = sample_entity_data_char_1.copy()
    invalid_data["unique_id"] = "" # Invalid because ID is missing

    bad_file = entity_dir / "invalid.json"
    bad_file.write_text(json.dumps([valid_data, invalid_data]))
    
    # Expect only the valid entity to be loaded
    db = InMemoryEntityDB.from_directories([str(entity_dir)])
    assert len(db.get_all_entities()) == 1
    assert db.get_entity_by_id("guard_01") is not None


def test_init_from_directory_duplicate_id(tmp_path, sample_entity_data_char_1, sample_entity_data_char_2):
    """Test initializing with duplicate unique_id across files raises ValueError."""
    entity_dir = tmp_path / "duplicate_ids"
    entity_dir.mkdir()
    
    # File 1 has two characters
    file1 = entity_dir / "char1.json"
    file1.write_text(json.dumps([sample_entity_data_char_1, sample_entity_data_char_2]))
    
    # File 2 attempts to re-use an ID from File 1
    data2 = sample_entity_data_char_1.copy()
    data2["names"] = ["Duplicate Guard"]
    file2 = entity_dir / "char1_dup.json"
    file2.write_text(json.dumps([data2]))

    # The loader should log an error and skip the duplicate, not raise an exception
    db = InMemoryEntityDB.from_directories([str(entity_dir)])
    assert len(db.get_all_entities()) == 2
    guard_entity = db.get_entity_by_id("guard_01")
    # Verify it is the first one that was loaded, not the duplicate
    assert "Gareth" in guard_entity.data["names"]


def test_from_data_success(sample_entity_list):
    """Test initializing using the from_data class method."""
    try:
        db = InMemoryEntityDB.from_data(sample_entity_list)
        entities = db.get_all_entities()
        assert len(entities) == 4
        ids = {e.unique_id for e in entities}
        assert "guard_01" in ids
        assert "merchant_01" in ids
        assert "spear_01" in ids
        assert "helmet_01" in ids
    except Exception as e:
        pytest.fail(f"DB initialization from data list failed: {e}")


def test_from_data_invalid():
    """Test initializing with invalid data structure using from_data."""
    # Test case 1: Data missing required fields (unique_id)
    invalid_list_missing_fields = [{"entity_type": "character", "data": {}}]
    with pytest.raises(
        ValueError,
        match=r"Failed to process entity data at index 0: Source 'input data': 'unique_id' and 'entity_type' are required.",
    ):
        InMemoryEntityDB.from_data(invalid_list_missing_fields)

    # Test case 2: Data with wrong type for a field (e.g., facts not a dict)
    invalid_list_wrong_type = [
        {"unique_id": "test_01", "entity_type": "item", "facts": "not-a-dict"}
    ]
    with pytest.raises(
        ValueError,
        match=r"Source 'input data', Entity 'test_01': 'facts' field must be a dictionary.",
    ):
        InMemoryEntityDB.from_data(invalid_list_wrong_type)


# --- Database Query Tests (using populated_entity_db fixture) ---


def test_get_entity_by_id_success(populated_entity_db: EntityDatabase):
    """Test retrieving entities by their correct unique ID."""
    char_entity = populated_entity_db.get_entity_by_id("guard_01")
    assert char_entity is not None
    assert char_entity.unique_id == "guard_01"
    assert char_entity.entity_type == "character"
    assert "Gareth" in char_entity.data["names"]

    item_entity = populated_entity_db.get_entity_by_id("spear_01")
    assert item_entity is not None
    assert item_entity.unique_id == "spear_01"
    assert item_entity.entity_type == "item"
    assert "Spear" in item_entity.data["names"]


def test_get_entity_by_id_not_found(populated_entity_db: EntityDatabase):
    """Test retrieving an entity by a non-existent ID."""
    entity = populated_entity_db.get_entity_by_id("non_existent_id")
    assert entity is None


def test_get_all_entities(populated_entity_db: EntityDatabase):
    """Test retrieving all loaded entities."""
    entities = populated_entity_db.get_all_entities()
    assert isinstance(entities, list)
    assert len(entities) == 4
    assert all(isinstance(e, Entity) for e in entities)
    ids = {e.unique_id for e in entities}
    assert (
        "guard_01" in ids
        and "merchant_01" in ids
        and "spear_01" in ids
        and "helmet_01" in ids
    )


def test_get_entities_by_type(populated_entity_db: EntityDatabase):
    """Test retrieving entities by their type."""
    # Test getting characters
    characters = populated_entity_db.get_entities_by_type("character")
    assert len(characters) == 2
    char_ids = {c.unique_id for c in characters}
    assert "guard_01" in char_ids
    assert "merchant_01" in char_ids

    # Test getting items
    items = populated_entity_db.get_entities_by_type("item")
    assert len(items) == 2
    item_ids = {i.unique_id for i in items}
    assert "spear_01" in item_ids
    assert "helmet_01" in item_ids

    # Test getting a type that doesn't exist
    locations = populated_entity_db.get_entities_by_type("location")
    assert len(locations) == 0


def test_access_entity_attributes_directly(populated_entity_db: EntityDatabase):
    """Test accessing entity attributes and data after retrieving from DB."""
    entity = populated_entity_db.get_entity_by_id("guard_01")
    assert entity is not None

    # Access basic attributes
    assert entity.unique_id == "guard_01"
    assert entity.entity_type == "character"
    assert entity.portrait_image_path is None  # Assuming not set in this fixture

    # Access the data dictionary
    assert isinstance(entity.data, dict)
    assert "public_facts" in entity.data
    assert entity.data["public_facts"]["post"] == "Gate Sentry"
    assert entity.data["inventory"]["money"] == 30


def test_modify_entity_data_directly(populated_entity_db: EntityDatabase):
    """Test modifying entity data dict after retrieving from DB."""
    entity = populated_entity_db.get_entity_by_id("merchant_01")
    assert entity is not None
    assert entity.data["inventory"]["money"] == 50

    # Modify data directly on the retrieved object
    entity.data["inventory"]["money"] = 100
    entity.data["new_fact"] = "Just added"
    entity.data["names"].append("Silas the Rich")

    # Retrieve the entity again to ensure the object in the DB was modified
    entity_again = populated_entity_db.get_entity_by_id("merchant_01")
    assert entity_again is not None
    assert entity_again.data["inventory"]["money"] == 100
    assert entity_again.data["new_fact"] == "Just added"
    assert "Silas the Rich" in entity_again.data["names"]
