"""Unit tests for the CharacterDatabase interface."""

import pytest
import json
import os
from pathlib import Path
from typing import Dict

# Assume the interface is in characters.character_db
from characters.character_db import CharacterDatabase, Character

# Import the concrete implementation
from characters.in_memory_character_db import InMemoryCharacterDB


@pytest.fixture
def sample_char_data_1() -> Dict:
    """Provides sample data for a single character (Guard)."""
    return {
        "unique_id": "guard_01",
        "names": ["Gareth", "Guard"],
        "public_facts": {
            "description": "A stern-looking guard in city livery.",
            "post": "Gate Sentry",
        },
        "private_facts": {
            "internal_description": "Just trying to get through the shift.",
            "wealth": "30 gold coins",  # Keep original note, but use actual inventory dict
            "secret": "Has a gambling problem.",
        },
        # Use new inventory format
        "inventory": {"money": 30, "items": {"spear_01": 1, "helmet_01": 1}},
    }


@pytest.fixture
def sample_char_data_2() -> Dict:
    """Provides sample data for a second character (Merchant)."""
    return {
        "unique_id": "merchant_01",
        "names": ["Silas", "Merchant"],
        "public_facts": {
            "description": "A thin man with darting eyes and fine, but worn, clothes.",
            "wares": "Sells 'exotic' goods (mostly trinkets).",
        },
        "private_facts": {
            "internal_description": "Always looking for the next big score.",
            "wealth": "Moderate savings",  # Keep original note
            "secret": "Owes money to the Thieves Guild.",
        },
        # Use new inventory format
        "inventory": {
            "money": 50,
            "items": {
                "coin_purse_01": 1,
                "ledger_01": 1,
                "cart_key_01": 1,
            },
        },
    }


@pytest.fixture
def sample_data_list(sample_char_data_1, sample_char_data_2):
    """Provides a list of sample character data dictionaries."""
    return [sample_char_data_1, sample_char_data_2]


@pytest.fixture
def populated_db(sample_data_list) -> CharacterDatabase:
    """Provides a test database pre-populated using from_data."""
    try:
        db = InMemoryCharacterDB.from_data(sample_data_list)
        return db
    except Exception as e:
        pytest.fail(
            f"Fixture populated_db failed during InMemoryCharacterDB.from_data: {e}"
        )


@pytest.fixture
def temp_char_dir(tmp_path, sample_char_data_1, sample_char_data_2):
    """Creates a temporary directory with character JSON files."""
    char_dir = tmp_path / "characters"
    char_dir.mkdir()
    # Ensure the correct key ("inventory") is used when writing test files
    file1_data = sample_char_data_1
    file2_data = sample_char_data_2
    file1 = char_dir / f"{file1_data['unique_id']}.json"
    file1.write_text(json.dumps(file1_data), encoding="utf-8")
    file2 = char_dir / f"{file2_data['unique_id']}.json"
    file2.write_text(json.dumps(file2_data), encoding="utf-8")
    return char_dir


# --- Test Cases ---

# --- Initialization Tests ---


def test_init_from_directory_success(temp_char_dir):
    """Test initializing the DB from a valid directory."""
    try:
        db = InMemoryCharacterDB(str(temp_char_dir))
        chars = db.get_all_characters()
        assert len(chars) == 2
        ids = {char.unique_id for char in chars}
        assert "guard_01" in ids
        assert "merchant_01" in ids
        # Spot check initialized inventory (should now work)
        guard = db.get_character_by_id("guard_01")
        assert guard.inventory["money"] == 30
        # Update assertion to check for item IDs
        assert "spear_01" in guard.inventory["items"]
        assert guard.inventory["items"]["spear_01"] == 1
        assert "helmet_01" in guard.inventory["items"]
    except Exception as e:
        pytest.fail(f"DB initialization from directory failed: {e}")


def test_init_from_directory_not_found():
    """Test initializing from a non-existent directory raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        InMemoryCharacterDB("non_existent_path")


def test_init_from_directory_invalid_json(tmp_path):
    """Test initializing with invalid JSON raises ValueError."""
    char_dir = tmp_path / "invalid_json"
    char_dir.mkdir()
    bad_file = char_dir / "bad.json"
    bad_file.write_text("{ invalid json")
    with pytest.raises(ValueError, match="Failed to load character from bad.json"):
        InMemoryCharacterDB(str(char_dir))


def test_init_from_directory_invalid_data(tmp_path, sample_char_data_1):
    """Test initializing with invalid character data raises ValueError."""
    char_dir = tmp_path / "invalid_data"
    char_dir.mkdir()
    bad_data = sample_char_data_1.copy()
    del bad_data["names"]  # Will cause validation error in Character
    bad_file = char_dir / "invalid.json"
    bad_file.write_text(json.dumps(bad_data))
    # Match the specific error from Character validation, wrapped by the loader error
    with pytest.raises(
        ValueError,
        match=r"Failed to load character from invalid\.json.*Character names cannot be empty",
    ):
        InMemoryCharacterDB(str(char_dir))


def test_from_data_success(sample_data_list):
    """Test initializing using the from_data class method."""
    try:
        db = InMemoryCharacterDB.from_data(sample_data_list)
        chars = db.get_all_characters()
        assert len(chars) == 2
        ids = {char.unique_id for char in chars}
        assert "guard_01" in ids
        assert "merchant_01" in ids
        # Add spot check for inventory here too
        guard = db.get_character_by_id("guard_01")
        assert guard.inventory["money"] == 30
        assert "spear_01" in guard.inventory["items"]
    except Exception as e:
        pytest.fail(f"DB initialization from data list failed: {e}")


def test_from_data_invalid(sample_data_list):
    """Test initializing with invalid data structure using from_data."""
    # Test case 1: Data missing required fields (unique_id is checked first)
    invalid_list_missing_fields = [
        {"id": "char1"}
    ]  # Still missing unique_id, names, facts
    with pytest.raises(
        ValueError,
        # Update match to expect the unique_id error
        match=r"Failed to process character data at index 0.*Character unique_id cannot be empty.",
    ):
        InMemoryCharacterDB.from_data(invalid_list_missing_fields)

    # Test case 2: Data valid structure but empty names list
    invalid_list_empty_name = [
        {
            "unique_id": "char1",
            "names": [],  # Invalid: names list is empty
            "public_facts": {"description": "Desc"},
            "private_facts": {"internal_description": "Internal"},
            "inventory": {"money": 0, "items": {}},
        }
    ]
    with pytest.raises(
        ValueError,
        match=r"Failed to process character data at index 0.*Character names cannot be empty",
    ):
        InMemoryCharacterDB.from_data(invalid_list_empty_name)


def test_load_actual_cast_files():
    """Test loading all actual character JSON files from characters/cast/ using the constructor."""
    base_dir = Path(__file__).resolve().parent.parent
    cast_dir = base_dir / "characters" / "cast"

    if not cast_dir.is_dir():
        pytest.skip(f"Cast directory not found at {cast_dir}")

    json_files = list(cast_dir.glob("*.json"))
    if not json_files:
        pytest.skip(f"No JSON files found in {cast_dir}")

    try:
        db_instance = InMemoryCharacterDB(cast_dir)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        pytest.fail(f"DB initialization raised an unexpected error: {e}")

    all_chars = db_instance.get_all_characters()
    assert len(all_chars) == len(
        json_files
    ), "Number of loaded characters should match number of JSON files"

    # Optional: Spot check a known character if structure is stable
    # borin = db_instance.get_character_by_id("borin_stonehand")
    # assert borin is not None
    # assert borin.name == "Borin Stonehand"
    # assert "pickaxe_01" in borin.inventory["items"]


# --- Database Query Tests (using populated_db fixture) ---


def test_get_character_by_name_exact_match(populated_db: CharacterDatabase):
    """Test finding a character by an exact name (case-insensitive)."""
    char = populated_db.get_character_by_name("Gareth")
    assert char is not None
    assert char.unique_id == "guard_01"
    char_lower = populated_db.get_character_by_name("gareth")
    assert char_lower is not None
    assert char_lower.unique_id == "guard_01"
    char_alias = populated_db.get_character_by_name("Guard")
    assert char_alias is not None
    assert char_alias.unique_id == "guard_01"


def test_get_character_by_name_fuzzy_match(populated_db: CharacterDatabase):
    """Test finding a character by a partial/fuzzy name (simple substring test)."""
    char = populated_db.get_character_by_name("Silas")  # Exact
    assert char is not None
    assert char.unique_id == "merchant_01"
    char_partial = populated_db.get_character_by_name("Merch")  # Partial
    assert char_partial is not None
    assert char_partial.unique_id == "merchant_01"


def test_get_character_by_name_not_found(populated_db: CharacterDatabase):
    """Test looking up a name that doesn't match any character."""
    char = populated_db.get_character_by_name("Unknown Name")
    assert char is None


def test_get_character_by_id_success(populated_db: CharacterDatabase):
    """Test retrieving a character by their correct unique ID."""
    char = populated_db.get_character_by_id("merchant_01")
    assert char is not None
    assert char.unique_id == "merchant_01"
    assert "Silas" in char.names


def test_get_character_by_id_not_found(populated_db: CharacterDatabase):
    """Test retrieving a character by a non-existent ID."""
    char = populated_db.get_character_by_id("non_existent_id")
    assert char is None


def test_get_all_characters(populated_db: CharacterDatabase):
    """Test retrieving all loaded characters."""
    chars = populated_db.get_all_characters()
    assert isinstance(chars, list)
    assert len(chars) == 2
    assert all(isinstance(c, Character) for c in chars)
    ids = {char.unique_id for char in chars}
    assert "guard_01" in ids
    assert "merchant_01" in ids


# --- Character Attribute Access/Modification Tests (using populated_db fixture) ---


def test_access_character_attributes_directly(populated_db: CharacterDatabase):
    """Test accessing character attributes after retrieving from DB."""
    char_id = "guard_01"
    char = populated_db.get_character_by_id(char_id)
    assert char is not None
    assert isinstance(char.public_facts, dict)
    assert char.public_facts["description"] == "A stern-looking guard in city livery."
    assert isinstance(char.private_facts, dict)
    assert char.private_facts["wealth"] == "30 gold coins"
    assert isinstance(char.inventory, dict)
    assert char.inventory["money"] == 30
    assert "spear" not in char.inventory["items"]
    assert "spear_01" in char.inventory["items"]
    assert char.inventory["items"]["spear_01"] == 1
    assert "helmet_01" in char.inventory["items"]


def test_modify_character_inventory_directly(populated_db: CharacterDatabase):
    """Test modifying character inventory after retrieving from DB."""
    char_id = "merchant_01"
    char = populated_db.get_character_by_id(char_id)
    assert char is not None
    original_money = char.inventory["money"]
    assert original_money == 50

    char.inventory["money"] = 75
    char.inventory["items"] = {"ledger_01": 1, "shiny_charm_01": 1}

    char_again = populated_db.get_character_by_id(char_id)
    assert char_again is not None
    assert char_again.inventory["money"] == 75
    assert char_again.inventory["items"] == {"ledger_01": 1, "shiny_charm_01": 1}
    assert "ledger_01" in char_again.inventory["items"]
    assert "shiny_charm_01" in char_again.inventory["items"]
    assert char_again.inventory["items"]["ledger_01"] == 1


def test_get_character_by_added_name(populated_db: CharacterDatabase):
    """Test finding a character by a name added *after* initial loading."""
    char_id_to_modify = "guard_01"
    new_alias = "Gazza"

    # 1. Verify the new name doesn't work initially (optional sanity check)
    char_before = populated_db.get_character_by_name(new_alias)
    assert (
        char_before is None
    ), f"Character found by alias '{new_alias}' before it was added."

    # 2. Get the character object
    char_to_modify = populated_db.get_character_by_id(char_id_to_modify)
    assert (
        char_to_modify is not None
    ), f"Could not retrieve character {char_id_to_modify} to modify."
    assert isinstance(char_to_modify.names, set), "Character.names should be a set."

    # 3. Modify the names set directly on the object
    char_to_modify.names.add(new_alias)
    print(f"Added alias '{new_alias}' to character {char_id_to_modify}")
    print(f"Character {char_id_to_modify} names are now: {char_to_modify.names}")

    # 4. Try finding the character by the new name
    char_after = populated_db.get_character_by_name(new_alias)

    # 5. Assert the correct character is found
    assert (
        char_after is not None
    ), f"Character not found by newly added alias '{new_alias}'."
    assert (
        char_after.unique_id == char_id_to_modify
    ), f"Found wrong character ({char_after.unique_id}) using new alias '{new_alias}'."

    # 6. Verify the original names still work
    char_orig = populated_db.get_character_by_name("Gareth")
    assert char_orig is not None and char_orig.unique_id == char_id_to_modify


def test_get_character_by_name_fuzzy_first_name(populated_db: CharacterDatabase):
    """Test finding a character by lowercase first name using fuzzy matching."""
    # Silas has names: "Silas", "Merchant", "Silas the Shrewd"
    char_id_to_find = "merchant_01"
    search_name = "silas"  # Lowercase first name only

    # Perform the fuzzy lookup
    found_char = populated_db.get_character_by_name(search_name)

    # Assert the correct character is found via fuzzy match
    assert (
        found_char is not None
    ), f"Character not found using fuzzy search for '{search_name}'."
    assert (
        found_char.unique_id == char_id_to_find
    ), f"Found wrong character ({found_char.unique_id}) using fuzzy search for '{search_name}'."

    # Also test a slightly more ambiguous partial match
    search_name_partial = "merc"
    found_char_partial = populated_db.get_character_by_name(search_name_partial)
    assert (
        found_char_partial is not None
    ), f"Character not found using fuzzy search for '{search_name_partial}'."
    assert (
        found_char_partial.unique_id == char_id_to_find
    ), f"Found wrong character ({found_char_partial.unique_id}) using fuzzy search for '{search_name_partial}'."
