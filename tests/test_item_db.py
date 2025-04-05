"""Unit tests for the ItemDatabase interface."""

import pytest
import json
import os
from typing import List, Set, Optional, Dict

# Assume the interface and implementation are in items.*
from items.item_db import ItemDatabase, Item
from items.in_memory_item_db import InMemoryItemDB

# --- Fixtures ---


@pytest.fixture
def sample_item_data_1():
    return {
        "unique_id": "apple_01",
        "names": ["Apple", "Red Apple"],
        "description": "A shiny red apple, crisp and juicy.",
        "properties": {"type": "food", "healing": 1, "weight": 0.2},
    }


@pytest.fixture
def sample_item_data_2():
    return {
        "unique_id": "sword_01",
        "names": ["Sword", "Longsword"],
        "description": "A well-balanced steel longsword.",
        "properties": {"type": "weapon", "damage": "1d8", "weight": 3.0},
    }


@pytest.fixture
def sample_item_data_list(sample_item_data_1, sample_item_data_2):
    """Provides a list of sample item data dictionaries."""
    return [sample_item_data_1, sample_item_data_2]


@pytest.fixture
def temp_item_file(tmp_path, sample_item_data_list):
    """Creates a temporary JSON file with item data."""
    item_file = tmp_path / "test_items.json"
    item_file.write_text(json.dumps(sample_item_data_list), encoding="utf-8")
    return str(item_file)


@pytest.fixture
def populated_db(sample_item_data_list) -> ItemDatabase:
    """Provides a test database pre-populated using from_data."""
    try:
        db = InMemoryItemDB.get_from_data(sample_item_data_list)
        return db
    except Exception as e:
        pytest.fail(
            f"Fixture populated_db failed during InMemoryItemDB.get_from_data: {e}"
        )


# --- Test Cases ---

# --- Initialization Tests ---


def test_init_from_file_success(temp_item_file):
    """Test initializing the DB from a valid JSON file."""
    try:
        db = InMemoryItemDB(temp_item_file)
        items = db.get_all_items()
        assert len(items) == 2
        ids = {item.unique_id for item in items}
        assert "apple_01" in ids
        assert "sword_01" in ids
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        pytest.fail(f"DB initialization from file failed: {e}")


def test_init_from_file_not_found():
    """Test initializing from a non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        InMemoryItemDB("non_existent_items.json")


def test_init_from_file_invalid_json(tmp_path):
    """Test initializing with invalid JSON raises ValueError."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("[{ invalid json }")
    with pytest.raises(ValueError, match="Invalid JSON"):
        InMemoryItemDB(str(bad_file))


def test_init_from_file_not_list(tmp_path):
    """Test initializing with JSON that isn't a list raises ValueError."""
    bad_file = tmp_path / "not_list.json"
    bad_file.write_text('{"key": "value"}')  # JSON object, not list
    with pytest.raises(ValueError, match="Item data file must contain a JSON list"):
        InMemoryItemDB(str(bad_file))


def test_init_from_file_invalid_item_data(tmp_path, sample_item_data_1):
    """Test initializing with invalid item data raises ValueError."""
    bad_data = sample_item_data_1.copy()
    del bad_data["names"]  # Will cause validation error in Item
    item_list = [bad_data]
    bad_file = tmp_path / "invalid_item.json"
    bad_file.write_text(json.dumps(item_list))
    with pytest.raises(ValueError, match="Item names cannot be empty"):
        InMemoryItemDB(str(bad_file))


def test_get_from_data_success(sample_item_data_list):
    """Test initializing using the get_from_data class method."""
    try:
        db = InMemoryItemDB.get_from_data(sample_item_data_list)
        items = db.get_all_items()
        assert len(items) == 2
    except (ValueError, RuntimeError) as e:
        pytest.fail(f"DB initialization from data failed: {e}")


def test_get_from_data_invalid_data(sample_item_data_1):
    """Test get_from_data raising error with invalid dictionary."""
    bad_data = sample_item_data_1.copy()
    del bad_data["description"]  # Make data invalid
    invalid_list = [bad_data]
    with pytest.raises(ValueError, match="Item description cannot be empty"):
        InMemoryItemDB.get_from_data(invalid_list)


# --- Database Query Tests (using populated_db fixture) ---


def test_get_item_by_name_exact_match(populated_db: ItemDatabase):
    """Test finding an item by an exact name (case-insensitive)."""
    item = populated_db.get_item_by_name("Apple")
    assert item is not None
    assert item.unique_id == "apple_01"
    item_lower = populated_db.get_item_by_name("apple")
    assert item_lower is not None
    assert item_lower.unique_id == "apple_01"
    item_alias = populated_db.get_item_by_name("Red Apple")
    assert item_alias is not None
    assert item_alias.unique_id == "apple_01"


def test_get_item_by_name_fuzzy_match(populated_db: ItemDatabase):
    """Test finding an item by a partial/fuzzy name."""
    item = populated_db.get_item_by_name("sword")  # Exact lowercase
    assert item is not None
    assert item.unique_id == "sword_01"
    item_partial = populated_db.get_item_by_name("longsw")  # Partial
    assert item_partial is not None
    assert item_partial.unique_id == "sword_01"


def test_get_item_by_name_not_found(populated_db: ItemDatabase):
    """Test looking up a name that doesn't match any item."""
    item = populated_db.get_item_by_name("Unknown Item Name")
    assert item is None


def test_get_item_by_id_success(populated_db: ItemDatabase):
    """Test retrieving an item by its correct unique ID."""
    item = populated_db.get_item_by_id("apple_01")
    assert item is not None
    assert item.unique_id == "apple_01"
    assert "Apple" in item.names
    assert item.properties.get("type") == "food"


def test_get_item_by_id_not_found(populated_db: ItemDatabase):
    """Test retrieving an item by a non-existent ID."""
    item = populated_db.get_item_by_id("non_existent_id")
    assert item is None


def test_get_all_items(populated_db: ItemDatabase):
    """Test retrieving all loaded items."""
    items = populated_db.get_all_items()
    assert isinstance(items, list)
    assert len(items) == 2
    assert all(isinstance(i, Item) for i in items)
    ids = {item.unique_id for item in items}
    assert "apple_01" in ids
    assert "sword_01" in ids
