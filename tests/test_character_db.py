"""Unit tests for the CharacterDatabase interface."""

import pytest
import json
import os

# Assume the interface is in characters.character_db
from characters.character_db import CharacterDatabase, Character

# Import the concrete implementation
from characters.in_memory_character_db import InMemoryCharacterDB


@pytest.fixture
def sample_char_data_1():
    return {
        "unique_id": "guard_01",
        "names": ["Gareth", "Guard"],
        "inventory": ["spear", "helmet"],  # Use key "inventory" for initial items
        "public_facts": {
            "description": "A stern-looking guard in city livery.",
            "location": "City Gate",
        },
        "private_facts": {
            "internal_description": "Just trying to make it through the shift.",
            "opinion_mayor": "Thinks the mayor is corrupt.",
            "wealth": "30 gold coins",
        },
    }


@pytest.fixture
def sample_char_data_2():
    return {
        "unique_id": "merchant_01",
        "names": ["Silas", "Merchant", "Silas the Shrewd"],
        "inventory": ["coin purse", "ledger", "cart key"],  # Use key "inventory"
        "public_facts": {
            "description": "A thin man with darting eyes and fine, but worn, clothes.",
            "wares": "Sells 'exotic' goods (mostly trinkets).",
        },
        "private_facts": {
            "internal_description": "Always looking for the next big score.",
            "debt": "Owes money to the local gang.",
            "wealth": "50 gold coins",
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
        # Spot check initialized inventory
        guard = db.get_character_by_id("guard_01")
        assert guard.inventory["money"] == 30
        assert guard.inventory["items"] == {"spear": 1, "helmet": 1}
    except (ValueError, FileNotFoundError, RuntimeError) as e:
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
    except (ValueError, RuntimeError) as e:
        pytest.fail(f"DB initialization from data failed: {e}")


def test_from_data_invalid_data(sample_char_data_1):
    """Test from_data raising error with invalid dictionary."""
    bad_data = sample_char_data_1.copy()
    del bad_data["names"]  # Make data invalid
    invalid_list = [bad_data]
    # Match the specific error from Character validation, wrapped by from_data error
    with pytest.raises(
        ValueError,
        match=r"Failed to process character data at index 0.*Character names cannot be empty",
    ):
        InMemoryCharacterDB.from_data(invalid_list)


def test_load_actual_cast_files():
    """Test loading all actual character JSON files from characters/cast/ using the constructor."""
    cast_dir = "characters/cast"
    expected_character_count = 5  # Based on previous listing

    assert os.path.isdir(
        cast_dir
    ), f"Test setup error: Directory '{cast_dir}' not found."

    try:
        db_instance = InMemoryCharacterDB(cast_dir)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        pytest.fail(f"DB initialization raised an unexpected error: {e}")

    loaded_characters = db_instance.get_all_characters()
    assert (
        len(loaded_characters) == expected_character_count
    ), f"Expected {expected_character_count} characters, but loaded {len(loaded_characters)}"

    borin = db_instance.get_character_by_name("Borin Stonehand")
    assert borin is not None
    assert borin.unique_id == "borin_stonehand_01"
    assert "Polishing Rag" in borin.inventory["items"]
    assert borin.inventory["money"] == 50

    elenara = db_instance.get_character_by_id("elenara_01")
    assert elenara is not None
    assert "Ancient Tome" in elenara.inventory["items"]
    assert elenara.inventory["money"] == 20


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
    assert char.inventory["items"] == {"spear": 1, "helmet": 1}


def test_modify_character_inventory_directly(populated_db: CharacterDatabase):
    """Test modifying character inventory after retrieving from DB."""
    char_id = "merchant_01"
    char = populated_db.get_character_by_id(char_id)
    assert char is not None
    original_money = char.inventory["money"]
    assert original_money == 50

    char.inventory["money"] = 75
    char.inventory["items"] = {"ledger": 1, "shiny charm": 1}

    char_again = populated_db.get_character_by_id(char_id)
    assert char_again is not None
    assert char_again.inventory["money"] == 75
    assert char_again.inventory["items"] == {"ledger": 1, "shiny charm": 1}


def test_get_character_by_added_name(populated_db: CharacterDatabase):
    """Test finding a character by a name added *after* initial loading."""
    char_id_to_modify = "guard_01"
    new_alias = "Gazza"
    new_alias_lower = new_alias.lower()

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
