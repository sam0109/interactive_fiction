# Interactive Fiction Game Outline

This document outlines the design, mechanics, and architecture of the LLM-powered interactive fiction game.

## 1. Game Concept

The game is a slice of life style game where the player can move around an interact with a world. However, the world is also populated by LLM powered agents living their lives completely independently of the player, with their own needs, wants, and goals. The player can move around and interact with these other characters, interact with objects in the world, and take actions, all mediated by an LLM powered "game master" that interprets what actions the player takes and issues function calls to enact them in the game world, then describes the results.

## 2. Game Mechanics

The core of the game is the interaction loop between the player and the AI Game Master.

*   **Natural Language Input:** The player types commands in plain English (e.g., "look at the room," "pick up the small brass key," "unlock the oak door with the key").
*   **LLM as Game Master:** A Large Language Model (LLM), specifically Google's Gemini, acts as the central "Game Master." It is responsible for:
    1.  **Understanding Intent:** Parsing the player's command to understand their intent.
    2.  **Entity Resolution:** Identifying which in-game objects the player is referring to (e.g., mapping "the oak door" to the specific `door` entity in the current location).
    3.  **Action Execution:** Determining the correct in-game action to take based on the player's intent.
    4.  **Narrative Generation:** Describing the outcome of the action to the player in a narrative style.
*   **Tool-Based World Interaction:** The LLM does not directly modify the game state. Instead, it uses a "function calling" or "tool use" approach. It is provided with a set of Python functions (tools) that represent all possible actions in the game. When the player issues a command, the LLM selects the appropriate tool and determines its parameters.
*   **Game State:** A central `GameState` object holds the "source of truth" for the game world. It tracks:
    *   The player's current location.
    *   The player's inventory.
    *   The properties and states of all objects and locations in the game.
*   **Interaction Loop:**
    1.  The player enters a command in the web UI.
    2.  The Flask backend receives the command.
    3.  It passes the command and the current `GameState` to the `GameMaster`.
    4.  The `GameMaster` invokes the LLM with the command and a set of available tools.
    5.  The LLM responds with a request to call a specific tool (e.g., `_examine(item='desk')`).
    6.  The `GameMaster` executes this function, which may modify the `GameState`.
    7.  The `GameMaster` generates a final narrative response for the player and sends it back to the UI.

## 3. Code Architecture

The project is a Python-based web application, structured into several key packages.

### 3.1. Main Application (`web_app.py`)

*   **`web_app.py`**:
    *   **Framework:** A Flask web server.
    *   **Responsibilities:**
        *   Serves the main `index.html` and static assets.
        *   Provides a `/chat` API endpoint for player input and a `/set_location` endpoint for testing.
        *   Initializes and holds the singleton instances for the application: `InMemoryEntityDB`, `KnowledgeManager`, `LLMEngine`, `GameState`, and `GameMaster`.
        *   Orchestrates the high-level request-response flow by passing player commands and the `GameState` object to the `GameMaster`.

### 3.2. Core Game Logic (`core/`)

*   **`core/game_state.py`**:
    *   **Class:** `GameState`
    *   **Responsibilities:** Acts as the single source of truth for all dynamic game data. It holds the player's ID and current location, and provides helper methods to access player information from the entity database.
*   **`core/game_master.py`**:
    *   **Class:** `GameMaster`
    *   **Responsibilities:**
        *   The "brain" of the game's AI. It orchestrates the entire LLM interaction.
        *   Receives raw player input from the `web_app` along with the current `GameState`.
        *   Defines a set of tools (Python functions like `_look_around`, `_examine`) that represent the possible actions a player can take in the world. These tools now receive the `GameState` object, giving them full context for their actions.
        *   Invokes the LLM with the player's command and the available tools, using function calling to determine the player's intent.
        *   Manages a multi-step conversation with the LLM to get a final narrative response.
        *   Contains the logic for "entity resolution" and "fact generation".
*   **`core/llm_engine.py`**:
    *   **Class:** `LLMEngine`
    *   **Responsibilities:** A lightweight wrapper around the `google-genai` client library. It initializes the API client with the correct key and holds a reference to the client and the desired model name. It does *not* contain any prompt construction or response parsing logic.
*   **`core/knowledge.py`**:
    *   **Class:** `KnowledgeManager`
    *   **Responsibilities:** Manages what each character (including the player) knows about every other entity in the game. It uses a dictionary to store a list of learned facts (strings) for each `(knower, subject)` pair.

### 3.3. Game Data & Entities (`data/`, `entities/`)

*   **`data/*.json` (`characters.json`, `items.json`, `locations.json`)**: These JSON files define the initial "ground truth" of the game world. They contain lists of objects that are loaded into the `InMemoryEntityDB` at startup.
*   **`entities/entity.py`**:
    *   **Class:** `Entity`
    *   **Responsibilities:** A dataclass representing a single object, character, or location in the game. It holds the "ground truth" for that entity, including its `unique_id`, `entity_type`, a `data` dictionary for its objective properties, and an optional path to a portrait image.
*   **`entities/entity_db.py`**:
    *   **Class:** `EntityDatabase`
    *   **Responsibilities:** An abstract base class that defines the required interface for an entity database. It specifies methods for loading data and retrieving entities (e.g., `get_entity_by_id`).
*   **`entities/in_memory_entity_db.py`**:
    *   **Class:** `InMemoryEntityDB`
    *   **Responsibilities:** An in-memory implementation of the `EntityDatabase` interface. It handles loading all entity data from the JSON files in the `/data` directory at startup. Its loading process is robust, logging errors and skipping invalid or duplicate data rather than crashing. It provides methods to query for entities by ID or type.

### 3.4. Web Frontend (`static/`, `templates/`)

*   **`templates/index.html`**: The main HTML file for the web UI, which structures the page.
*   **`static/style.css`**: The stylesheet for the web UI.
*   **`static/script.js`**: Handles client-side logic, such as sending commands to the server and updating the display.
*   **`static/favicon.svg`**: The icon for the website.
*   **`templates/404.html`**: The page shown for invalid URLs.

### 3.5. Utilities (`utils/`)

*   **`utils/llm_api.py`**: Provides utility functions for interacting with the LLM, possibly for tasks outside the core game loop, like content generation.
*   **`utils/generate_character_images.py`**: A script to automatically generate images for characters, likely using an image generation API.

### 3.6. Testing (`tests/`)

*   **`tests/test_lib.py`**: A reusable `TestHarness` class for setting up integration tests.
*   **`tests/run_scene.py`**: A script using `TestHarness` to run a sequence of commands for manual testing.
*   **`tests/test_entity_db.py`**: Pytest tests for the entity database.

### 3.7. Project & Configuration

*   **`config.py`**: Stores application configuration, including API keys.
*   **`keys.json`**: Stores secret API keys, loaded by `config.py`.
*   **`requirements.txt`**: Lists the Python project dependencies.
*   **`pyproject.toml`**: Defines project metadata and build system configuration (PEP 518).
*   **`pylintrc`**: Configuration file for the Pylint linter.
*   **`README.md`**: The main project README file.
*   **`.gitignore`**: Specifies files and directories for Git to ignore.
*   **`TODO`**: A file containing a list of tasks to be done. 