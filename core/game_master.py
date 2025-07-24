"""
This module defines the GameMaster, which is responsible for parsing player
input using an LLM and executing game actions.
"""
from typing import List, Dict, Any, Optional
import json
import logging

from google.genai import types

from core.llm_engine import LLMEngine
from core.knowledge import KnowledgeManager
from core.game_state import GameState
from entities.in_memory_entity_db import InMemoryEntityDB
from entities.entity import Entity

class GameMaster:
    """
    The GameMaster uses an LLM to interpret player commands and interact with the game world.
    """
    def __init__(
        self,
        llm_engine: LLMEngine,
        knowledge_manager: KnowledgeManager,
        entity_db: InMemoryEntityDB,
    ):
        self.llm_engine = llm_engine
        self.knowledge_manager = knowledge_manager
        self.entity_db = entity_db
        self.player_id = "player_01"  # Hardcoded for now

    # --- Tool Implementations ---

    def _tool_look_around(self, game_state: GameState) -> str:
        """Describes the current location and the items within it."""
        location = self.entity_db.get_entity_by_id(game_state.player_location_id)
        if not location:
            return f"The location '{game_state.player_location_id}' is not recognized."
        
        player = game_state.get_player_entity()
        if not player:
            return "Error: Player could not be found."

        # Find entities in the same location
        entities_in_location = self.entity_db.get_entities_by_data_property("location_id", game_state.player_location_id)
        other_entities = [e for e in entities_in_location if e.unique_id != player.unique_id and e.unique_id != game_state.player_location_id]

        if not other_entities:
            return f"{location.data.get('description', 'It is an empty room.')}"

        descriptions = []
        for entity in other_entities:
            known_facts = self.knowledge_manager.get_facts(player.unique_id, entity.unique_id)
            if not known_facts:
                perception = self._generate_initial_perception(entity)
                if perception:
                    self.knowledge_manager.add_fact(player.unique_id, entity.unique_id, perception)
        
        all_descriptions = []
        for entity in other_entities:
            facts = self.knowledge_manager.get_facts(player.unique_id, entity.unique_id)
            if facts:
                all_descriptions.extend(facts)

        if not all_descriptions:
            return f"{location.data.get('description', 'It is an empty room.')}"
        
        return f"{location.data.get('description', 'You are in a room.')} " + " ".join(all_descriptions)

    def _tool_examine(self, target_string: str, game_state: GameState) -> str:
        """Examines an object or character, revealing more details."""
        player = game_state.get_player_entity()
        if not player:
            return "Error: Player could not be found."

        entities_in_location = self.entity_db.get_entities_by_data_property("location_id", game_state.player_location_id)
        other_entities = [e for e in entities_in_location if e.unique_id != player.unique_id and e.unique_id != game_state.player_location_id]

        if not other_entities:
            return "There is nothing here to examine."

        resolved_entity_id = self._resolve_entity_for_examine(target_string, player, other_entities)

        if not resolved_entity_id:
            return f"I see nothing here that matches '{target_string}'."

        subject = self.entity_db.get_entity_by_id(resolved_entity_id)
        if not subject:
            return "Error: Could not find the specified entity."

        newly_learned_facts = self._generate_facts_for_examine(player, f"examine {target_string}", subject)
        for fact in newly_learned_facts:
            self.knowledge_manager.add_fact(player.unique_id, subject.unique_id, fact)

        all_facts = self.knowledge_manager.get_facts(player.unique_id, subject.unique_id)

        if not all_facts:
            return f"You examine the {subject.data.get('name', 'object')} and find nothing of interest."

        response = f"You examine the {subject.data.get('name', 'object')}:\n"
        response += "\n".join(all_facts)
        return response

    def _tool_go_to(self, destination_string: str) -> str:
        """Moves the player to a new location."""
        return f"OK. I can't go to '{destination_string}' yet. The game doesn't support that action."

    # --- LLM Interaction ---

    def _get_llm_tool_call(self, system_prompt: str, player_input: str, tools: List[Any]) -> Optional[types.Part]:
        """Sends a prompt to the LLM and requests a tool call."""
        logging.info("Sending command to LLM for tool generation...")
        try:
            response = self.llm_engine.client.models.generate_content(
                model=self.llm_engine.model_name,
                contents=[system_prompt, player_input],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    tools=tools,
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(mode='ANY')
                    ),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=1),
                )
            )
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        return part
        except Exception as e:
            logging.exception("Exception while getting tool call from LLM.")
        return None

    def _get_llm_narrative(self, history: List[types.Content]) -> str:
        """Sends the tool response to the LLM to generate a narrative for the player."""
        logging.info("Sending tool response back to LLM for final narrative.")
        try:
            response = self.llm_engine.client.models.generate_content(
                model=self.llm_engine.model_name,
                contents=history,
                config=types.GenerateContentConfig(temperature=0.7)
            )
            return response.text
        except Exception as e:
            logging.exception("Exception while getting narrative from LLM.")
            return f"An error occurred while generating the narrative: {e}"

    # --- Main Processing Logic ---

    def process_command(self, player_input: str, game_state: GameState) -> str:
        """
        Processes a player's command using the LLM with function calling.
        """
        logging.info(f"Processing command: '{player_input}' in location '{game_state.player_location_id}'")
        player_entity = game_state.get_player_entity()
        if not player_entity:
            logging.error("Could not find player entity in GameState.")
            return "Error: Player entity could not be found."

        # Define tools using simple Python functions that call our class methods
        def look_around() -> str:
            """Describes the current location and the items within it."""
            return self._tool_look_around(game_state)

        def examine(target_string: str) -> str:
            """Examines an object or character, revealing more details."""
            return self._tool_examine(target_string, game_state)

        def go_to(destination_string: str) -> str:
            """Moves the player to a new location."""
            return self._tool_go_to(destination_string)

        tools = [look_around, examine, go_to]
        tool_functions = {tool.__name__: tool for tool in tools}

        system_prompt = f"""You are the Game Master for a text-based adventure game. Your primary role is to interpret the player's commands and use the provided tools to respond. The player is currently in the location '{game_state.player_location_id}'. You MUST use the provided tool functions to respond. Based on the player's input: '{player_input}', select the best tool and call it."""

        function_call_part = self._get_llm_tool_call(system_prompt, player_input, tools)

        if not function_call_part:
            return "I'm not sure how to respond to that."

        function_call = function_call_part.function_call
        function_name = function_call.name
        if function_name not in tool_functions:
            return f"The game logic does not recognize the action '{function_name}'."
        
        args = dict(function_call.args)
        logging.info(f"LLM requested to call tool: {function_name} with args: {args}")

        try:
            function_to_call = tool_functions[function_name]
            tool_response = function_to_call(**args)
            logging.info(f"Tool '{function_name}' executed and returned: '{tool_response[:100]}...'")
        except Exception as e:
            logging.exception(f"Tool '{function_name}' raised an exception.")
            tool_response = f"An error occurred while trying to execute {function_name}: {e}"

        # Construct the full conversation history
        history = [
            types.Content(role="user", parts=[types.Part.from_text(text=system_prompt)]),
            types.Content(role="user", parts=[types.Part.from_text(text=player_input)]),
            types.Content(role="model", parts=[function_call_part]),
            types.Content(
                role="tool",
                parts=[
                    types.Part.from_function_response(
                        name=function_name,
                        response={"result": tool_response},
                    )
                ]
            )
        ]
        return self._get_llm_narrative(history)

    # --- Entity Resolution and Fact Generation (Helper methods) ---
    def get_player_entity(self) -> Optional[Entity]:
        """Retrieves the player's entity object."""
        return self.entity_db.get_entity_by_id(self.player_id)
        
    def _resolve_entity_for_examine(self, target_string: str, knower: Entity, potential_targets: List[Entity]) -> Optional[str]:
        """Uses the LLM to determine which entity a player is referring to for examination."""
        if not potential_targets:
            return None

        prompt = self._construct_resolution_prompt(target_string, knower, potential_targets)
        logging.info(f"Attempting to resolve entity for string: '{target_string}'")

        try:
            response = self.llm_engine.client.models.generate_content(
                model=self.llm_engine.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    candidate_count=1,
                    max_output_tokens=50,
                    temperature=0.1,
                )
            )
            if not response.candidates or not response.candidates[0].content.parts:
                 logging.warning("Entity resolution response was empty.")
                 return None

            resolved_id = self._parse_resolution_response(response.text)
            logging.info(f"LLM resolved '{target_string}' to entity_id: '{resolved_id}'")
            return resolved_id
        except Exception as e:
            logging.exception("An exception occurred during entity resolution.")
            return None

    def _construct_resolution_prompt(self, target_string: str, knower: Entity, potential_targets: List[Entity]) -> str:
        """Constructs the prompt for entity resolution."""
        target_options = []
        for entity in potential_targets:
            known_facts = self.knowledge_manager.get_facts(knower.unique_id, entity.unique_id)
            target_options.append({
                "entity_id": entity.unique_id,
                "known_facts": known_facts
            })
        prompt_template = f"""
Role: You are a helpful assistant in a text-based game. Your task is to figure out which object the player is referring to.
Context: The player typed the command referring to: "{target_string}".
Available Objects and Known Facts: {json.dumps(target_options, indent=2)}
Instruction: Based on what the player typed and the facts they know, which 'entity_id' are they most likely referring to?
Your response MUST be a valid JSON object containing a single key "entity_id". The value should be the single, most likely 'entity_id' from the list above. If no object seems to be a good match, the value should be null.
"""
        return prompt_template.strip()

    def _parse_resolution_response(self, response_text: str) -> Optional[str]:
        """Parses the JSON object from the LLM's resolution response."""
        try:
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                 response_text = response_text[3:-3].strip()
            data = json.loads(response_text)
            if isinstance(data, dict) and "entity_id" in data:
                return data["entity_id"]
            return None
        except (json.JSONDecodeError, TypeError) as e:
            logging.warning(f"Failed to parse entity resolution JSON response: '{response_text}'. Error: {e}")
            return None
            
    def _generate_facts_for_examine(self, knower: Entity, action: str, subject: Entity) -> List[str]:
        """Generates new facts a character might learn from performing an action."""
        current_knowledge = self.knowledge_manager.get_facts(knower.unique_id, subject.unique_id)
        
        prompt = self._construct_fact_generation_prompt(knower, action, subject, current_knowledge)
        logging.info(f"Generating new facts for {knower.unique_id} examining {subject.unique_id}")

        try:
            response = self.llm_engine.client.models.generate_content(
                model=self.llm_engine.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=200, temperature=0.7)
            )
            if not response.candidates or not response.candidates[0].content.parts:
                logging.warning("Fact generation response was empty.")
                return []
            new_facts = self._parse_fact_generation_response(response.text)
            logging.info(f"Generated {len(new_facts)} new facts.")
            return new_facts
        except Exception as e:
            logging.exception("An exception occurred during fact generation.")
            return []

    def _construct_fact_generation_prompt(self, knower: Entity, action: str, subject: Entity, current_knowledge: List[str]) -> str:
        """Constructs the detailed prompt for the LLM."""
        prompt_template = f"""
Role: You are a creative and subtle game master for a text-based interactive fiction game. Your goal is to reveal information about the world organically as the player interacts with it.
Context: The character '{knower.unique_id}' performs the action: '{action}' on the object '{subject.unique_id}'.
Object's Ground Truth: {json.dumps(subject.data, indent=2)}
Character's Current Knowledge: {json.dumps(current_knowledge, indent=2)}
Instruction: Based on the action, what new information would the character learn? Be concise and descriptive. The new information could be about its physical properties, purpose, history, or value. Formulate names as statements, e.g., "It looks like what most people would call a 'rusty key'." If the action would not reveal any new details, return an empty list. Your response MUST be a valid JSON list of strings. Example: ["This is a new fact.", "This is another new fact."]
"""
        return prompt_template.strip()

    def _parse_fact_generation_response(self, response_text: str) -> List[str]:
        """Parses the JSON list from the LLM's response."""
        try:
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                 response_text = response_text[3:-3].strip()
            facts = json.loads(response_text)
            if isinstance(facts, list) and all(isinstance(f, str) for f in facts):
                return facts
            return []
        except (json.JSONDecodeError, TypeError) as e:
            logging.warning(f"Failed to parse fact generation JSON response: '{response_text}'. Error: {e}")
            return []

    def _generate_initial_perception(self, subject: Entity) -> Optional[str]:
        """Generates a first-glance description for an entity."""
        prompt = self._construct_perception_prompt(subject)
        logging.info(f"Generating initial perception for {subject.unique_id}")

        try:
            response = self.llm_engine.client.models.generate_content(
                model=self.llm_engine.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(candidate_count=1, max_output_tokens=100, temperature=0.8)
            )
            if not response.candidates or not response.candidates[0].content.parts:
                logging.warning("Initial perception response was empty.")
                return "A shimmering form is here, but it's difficult to make out."
            
            perception = response.text.strip()
            logging.info(f"Generated perception for {subject.unique_id}: '{perception[:100]}...'")
            return perception
        except Exception as e:
            logging.exception(f"An exception occurred during initial perception generation for {subject.unique_id}.")
            return "A shimmering form is here, but it's difficult to make out."

    def _construct_perception_prompt(self, subject: Entity) -> str:
        """Constructs the prompt to generate a first-glance description."""
        prompt_template = f"""
Role: You are a creative writer for a text-based game.
Context: A player has just entered a room and seen an object for the first time.
Object's Ground Truth: {json.dumps(subject.data, indent=2)}
Instruction: Write a brief, one-sentence description of this object from the player's perspective. Be evocative and mysterious. Do not reveal the object's name or true purpose. Focus on its appearance and general impression. Your response must be a single string.
"""
        return prompt_template.strip()
