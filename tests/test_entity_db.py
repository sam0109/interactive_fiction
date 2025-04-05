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

    # Write character files
    char1_file = char_dir / f"{sample_entity_data_char_1['unique_id']}.json"
    char1_file.write_text(json.dumps(sample_entity_data_char_1), encoding="utf-8")
    char2_file = char_dir / f"{sample_entity_data_char_2['unique_id']}.json"
    char2_file.write_text(json.dumps(sample_entity_data_char_2), encoding="utf-8")

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
        assert "Gareth" in guard_entity.names
        assert "public_facts" in guard_entity.data
        assert guard_entity.data["public_facts"]["post"] == "Gate Sentry"
        assert "inventory" in guard_entity.data
        assert guard_entity.data["inventory"]["money"] == 30

        # Spot check a loaded item entity
        spear_entity = db.get_entity_by_id("spear_01")
        assert spear_entity is not None
        assert spear_entity.entity_type == "item"
        assert "Spear" in spear_entity.names
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


def test_init_from_directory_invalid_data(tmp_path, sample_entity_data_char_1):
    """Test initializing with invalid entity data logs error and skips file."""
    entity_dir = tmp_path / "invalid_data"
    entity_dir.mkdir()
    bad_data = sample_entity_data_char_1.copy()
    del bad_data["names"]  # Will cause validation error in Entity / _parse
    bad_file = entity_dir / "invalid.json"
    bad_file.write_text(json.dumps(bad_data))
    # Expect 0 loaded, error logged
    db = InMemoryEntityDB.from_directories([str(entity_dir)])
    # Check logs manually or use caplog fixture if precise error checking needed
    assert len(db.get_all_entities()) == 0


def test_init_from_directory_duplicate_id(tmp_path, sample_entity_data_char_1):
    """Test initializing with duplicate unique_id across files raises ValueError."""
    entity_dir = tmp_path / "duplicate_ids"
    entity_dir.mkdir()
    file1 = entity_dir / "char1a.json"
    file1.write_text(json.dumps(sample_entity_data_char_1))
    # Create another file with the same ID
    data2 = sample_entity_data_char_1.copy()
    data2["names"] = ["Duplicate Guard"]
    file2 = entity_dir / "char1b.json"
    file2.write_text(json.dumps(data2))

    with pytest.raises(ValueError, match=r"Duplicate unique_id found: guard_01"):
        InMemoryEntityDB.from_directories([str(entity_dir)])


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
    invalid_list_missing_fields = [{"entity_type": "character", "names": ["Test"]}]
    with pytest.raises(
        ValueError,
        match=r"Failed to process entity data at index 0.*unique_id cannot be empty",
    ):
        InMemoryEntityDB.from_data(invalid_list_missing_fields)

    # Test case 2: Data missing entity_type
    invalid_list_missing_type = [{"unique_id": "test01", "names": ["Test"]}]
    with pytest.raises(
        ValueError,
        match=r"Failed to process entity data at index 0.*entity_type cannot be empty",
    ):
        InMemoryEntityDB.from_data(invalid_list_missing_type)

    # Test case 3: Duplicate ID within the list
    duplicate_list = [
        {"unique_id": "dup01", "entity_type": "item", "names": ["Item A"]},
        {"unique_id": "dup01", "entity_type": "item", "names": ["Item B"]},
    ]
    with pytest.raises(
        ValueError, match=r"Duplicate unique_id found at index 1: dup01"
    ):
        InMemoryEntityDB.from_data(duplicate_list)


# --- Database Query Tests (using populated_entity_db fixture) ---


def test_get_entity_by_id_success(populated_entity_db: EntityDatabase):
    """Test retrieving entities by their correct unique ID."""
    char_entity = populated_entity_db.get_entity_by_id("guard_01")
    assert char_entity is not None
    assert char_entity.unique_id == "guard_01"
    assert char_entity.entity_type == "character"
    assert "Gareth" in char_entity.names

    item_entity = populated_entity_db.get_entity_by_id("spear_01")
    assert item_entity is not None
    assert item_entity.unique_id == "spear_01"
    assert item_entity.entity_type == "item"
    assert "Spear" in item_entity.names


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
    """Test retrieving entities filtered by type."""
    char_entities = populated_entity_db.get_entities_by_type("character")
    assert isinstance(char_entities, list)
    assert len(char_entities) == 2
    assert all(e.entity_type == "character" for e in char_entities)
    char_ids = {e.unique_id for e in char_entities}
    assert "guard_01" in char_ids and "merchant_01" in char_ids

    item_entities = populated_entity_db.get_entities_by_type("item")
    assert isinstance(item_entities, list)
    assert len(item_entities) == 2
    assert all(e.entity_type == "item" for e in item_entities)
    item_ids = {e.unique_id for e in item_entities}
    assert "spear_01" in item_ids and "helmet_01" in item_ids

    non_existent_entities = populated_entity_db.get_entities_by_type("location")
    assert isinstance(non_existent_entities, list)
    assert len(non_existent_entities) == 0


def test_get_entity_by_name_exact_match(populated_entity_db: EntityDatabase):
    """Test finding an entity by an exact name (case-insensitive)."""
    entity = populated_entity_db.get_entity_by_name("Gareth")  # Character
    assert entity is not None
    assert entity.unique_id == "guard_01"
    entity_lower = populated_entity_db.get_entity_by_name("gareth")
    assert entity_lower is not None
    assert entity_lower.unique_id == "guard_01"

    entity_item = populated_entity_db.get_entity_by_name("Spear")  # Item
    assert entity_item is not None
    assert entity_item.unique_id == "spear_01"


def test_get_entity_by_name_fuzzy_match(populated_entity_db: EntityDatabase):
    """Test finding an entity by a partial/fuzzy name."""
    entity = populated_entity_db.get_entity_by_name("Sila")  # Partial character name
    assert entity is not None
    assert entity.unique_id == "merchant_01"

    entity_item = populated_entity_db.get_entity_by_name("Helme")  # Partial item name
    assert entity_item is not None
    assert entity_item.unique_id == "helmet_01"


def test_get_entity_by_name_not_found(populated_entity_db: EntityDatabase):
    """Test looking up a name that doesn't match any entity."""
    entity = populated_entity_db.get_entity_by_name("Unknown Entity Name")
    assert entity is None


# --- Entity Attribute Access/Modification Tests ---


def test_access_entity_attributes_directly(populated_entity_db: EntityDatabase):
    """Test accessing entity attributes after retrieving from DB."""
    # Character
    char_entity = populated_entity_db.get_entity_by_id("guard_01")
    assert char_entity is not None
    assert char_entity.entity_type == "character"
    assert isinstance(char_entity.data, dict)
    assert (
        char_entity.data["public_facts"]["description"]
        == "A stern-looking guard in city livery."
    )
    assert char_entity.data["inventory"]["money"] == 30
    assert "spear_01" in char_entity.data["inventory"]["items"]

    # Item
    item_entity = populated_entity_db.get_entity_by_id("spear_01")
    assert item_entity is not None
    assert item_entity.entity_type == "item"
    assert isinstance(item_entity.data, dict)
    assert item_entity.data["description"].startswith("A standard issue")
    assert item_entity.data["properties"]["damage"] == "1d6"


def test_modify_entity_data_directly(populated_entity_db: EntityDatabase):
    """Test modifying entity data dict after retrieving from DB."""
    entity = populated_entity_db.get_entity_by_id("merchant_01")
    assert entity is not None
    assert entity.data["inventory"]["money"] == 50

    # Modify data directly on the retrieved object
    entity.data["inventory"]["money"] = 100
    entity.data["new_fact"] = "Just added"
    entity.names.add("Silas the Rich")

    # Retrieve again
    entity_again = populated_entity_db.get_entity_by_id("merchant_01")
    assert entity_again is not None
    assert entity_again.data["inventory"]["money"] == 100  # Change persists
    assert entity_again.data["new_fact"] == "Just added"  # Change persists
    assert "Silas the Rich" in entity_again.names  # Change persists

    # Verify change is reflected in get_by_name too
    entity_rich = populated_entity_db.get_entity_by_name("Silas the Rich")
    assert entity_rich is not None
    assert entity_rich.unique_id == "merchant_01"
