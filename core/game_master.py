"""
This module defines the GameMaster, which is responsible for parsing player
input using an LLM and executing game actions.
"""
from typing import List, Dict, Any, Optional
import json

from google.genai import types

from core.llm_engine import LLMEngine
from core.knowledge import KnowledgeManager
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

    def get_player_entity(self) -> Optional[Entity]:
        """Retrieves the player's entity object."""
        return self.entity_db.get_entity_by_id(self.player_id)

    def process_command(self, player_input: str, player_location_id: str) -> str:
        """
        Processes a player's command using the LLM with function calling.

        Args:
            player_input: The raw text command from the player.
            player_location_id: The unique ID of the player's current location.

        Returns:
            A string response to be shown to the player.
        """
        player_entity = self.get_player_entity()
        if not player_entity:
            return "Error: Player entity could not be found."

        tools = [
            self._look_around,
            self._examine,
            self._go_to,
        ]

        # We pass the player's location to the tools via a closure/lambda
        # This is a bit of a hack, but avoids making player location a global
        # or passing it to every single tool function.
        # A better long-term solution might involve a "context" object.
        tool_functions = {
            tool.__name__: (lambda t=tool: lambda **kwargs: t(player_location_id=player_location_id, **kwargs))
            for tool in tools
        }

        try:
            response = self.llm_engine.client.models.generate_content(
                model=self.llm_engine.model_name,
                contents=[player_input],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    tools=tools,
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode='AUTO'
                        )
                    ),
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                        ),
                    ]
                )
            )

            if response.prompt_feedback and response.prompt_feedback.block_reason != 0:
                return f"Your request was blocked by the safety filter: {response.prompt_feedback.block_reason.name}"
            
            if not response.candidates or not response.candidates[0].content.parts:
                return "I'm not sure how to respond to that."

            for part in response.candidates[0].content.parts:
                if part.function_call:
                    function_name = part.function_call.name
                    args = types.to_dict(part.function_call.args)
                    
                    if function_name in tool_functions:
                        function_to_call = tool_functions[function_name]
                        function_response = function_to_call(**args)

                        # Send the response back to the model
                        response = self.llm_engine.client.models.generate_content(
                            model=self.llm_engine.model_name,
                            contents=[
                                response.candidates[0].content,
                                types.Content(
                                    parts=[types.Part(
                                        function_response=types.FunctionResponse(
                                            name=function_name,
                                            response={
                                                "content": function_response,
                                            },
                                        )
                                    )],
                                    role="tool"
                                )
                            ],
                            config=types.GenerateContentConfig(
                                temperature=0.7,
                                tools=tools,
                                tool_config=types.ToolConfig(
                                    function_calling_config=types.FunctionCallingConfig(
                                        mode='NONE'
                                    )
                                ),
                                safety_settings=[
                                    types.SafetySetting(
                                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                                        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                                    ),
                                    types.SafetySetting(
                                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                                        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                                    ),
                                ]
                            )
                        )

                        if response.prompt_feedback and response.prompt_feedback.block_reason != 0:
                            return f"The tool's response was blocked by the safety filter: {response.prompt_feedback.block_reason.name}"
                            
                        return response.text
            
            # If no function was called, return the model's text response
            return response.text

        except Exception as e:
            # Basic error handling
            return f"An error occurred: {e}"

    def _resolve_entity_for_examine(self, target_string: str, knower: Entity, potential_targets: List[Entity]) -> Optional[str]:
        """Uses the LLM to determine which entity a player is referring to for examination."""
        if not potential_targets:
            return None

        prompt = self._construct_resolution_prompt(target_string, knower, potential_targets)

        try:
            response = self.llm_engine.client.models.generate_content(
                model=self.llm_engine.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    candidate_count=1,
                    max_output_tokens=50,
                    temperature=0.1,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                        ),
                    ]
                )
            )
            # Make sure to handle blocked responses
            if response.prompt_feedback and response.prompt_feedback.block_reason != 0:
                return None # Or handle error appropriately

            if not response.candidates or not response.candidates[0].content.parts:
                 return None

            return self._parse_resolution_response(response.text)
        except Exception as e:
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

Available Objects and Known Facts: Here is a list of objects the player might be referring to, along with the facts the player already knows about them.

{json.dumps(target_options, indent=2)}

Instruction: Based on what the player typed and the facts they know, which 'entity_id' are they most likely referring to?
- Your response MUST be a valid JSON object containing a single key "entity_id".
- The value should be the single, most likely 'entity_id' from the list above.
- If no object seems to be a good match, the value should be null.
"""
        return prompt_template.strip()

    def _parse_resolution_response(self, response_text: str) -> Optional[str]:
        """Parses the JSON object from the LLM's resolution response."""
        try:
            # The response may have leading/trailing ```json ... ``` markers
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                 response_text = response_text[3:-3].strip()

            data = json.loads(response_text)
            if isinstance(data, dict) and "entity_id" in data:
                return data["entity_id"]
            return None
        except (json.JSONDecodeError, TypeError):
            return None
            
    def _generate_facts_for_examine(self, knower: Entity, action: str, subject: Entity) -> List[str]:
        """Generates new facts a character might learn from performing an action."""
        current_knowledge = self.knowledge_manager.get_facts(knower.unique_id, subject.unique_id)
        
        prompt = self._construct_fact_generation_prompt(knower, action, subject, current_knowledge)

        try:
            response = self.llm_engine.client.models.generate_content(
                model=self.llm_engine.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=200,
                    temperature=0.7,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                        ),
                    ]
                )
            )

            if response.prompt_feedback and response.prompt_feedback.block_reason != 0:
                return [] # Or handle error appropriately
            
            if not response.candidates or not response.candidates[0].content.parts:
                return []

            return self._parse_fact_generation_response(response.text)
        except Exception as e:
            return []

    def _construct_fact_generation_prompt(self, knower: Entity, action: str, subject: Entity, current_knowledge: List[str]) -> str:
        """Constructs the detailed prompt for the LLM."""

        prompt_template = f"""
Role: You are a creative and subtle game master for a text-based interactive fiction game. Your goal is to reveal information about the world organically as the player interacts with it.

Context: The character '{knower.unique_id}' performs the action: '{action}' on the object '{subject.unique_id}'.

Object's Ground Truth: This is the objective, hidden information about the object.
{json.dumps(subject.data, indent=2)}

Character's Current Knowledge: This is what the character '{knower.unique_id}' already knows about '{subject.unique_id}'. Do not repeat these facts in your response.
{json.dumps(current_knowledge, indent=2)}

Instruction: Based on the action, what new information would the character learn?
- Be concise and descriptive.
- The new information could be about its physical properties, purpose, history, or value.
- Formulate names as statements, e.g., "It looks like what most people would call a 'rusty key'."
- If the action would not reveal any new details, return an empty list.
- Your response MUST be a valid JSON list of strings. Example: ["This is a new fact.", "This is another new fact."]
"""
        return prompt_template.strip()

    def _parse_fact_generation_response(self, response_text: str) -> List[str]:
        """Parses the JSON list from the LLM's response."""
        try:
            # The response may have leading/trailing ```json ... ``` markers
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                 response_text = response_text[3:-3].strip()

            facts = json.loads(response_text)
            if isinstance(facts, list) and all(isinstance(f, str) for f in facts):
                return facts
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    def _generate_initial_perception(self, subject: Entity) -> Optional[str]:
        """Generates a first-glance description for an entity."""
        prompt = self._construct_perception_prompt(subject)

        try:
            response = self.llm_engine.client.models.generate_content(
                model=self.llm_engine.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    candidate_count=1,
                    max_output_tokens=100,
                    temperature=0.8,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
                        ),
                    ]
                )
            )
            if response.prompt_feedback and response.prompt_feedback.block_reason != 0:
                return "A shimmering form is here, but it's difficult to make out." # Or handle error appropriately
            
            if not response.candidates or not response.candidates[0].content.parts:
                return "A shimmering form is here, but it's difficult to make out."
            
            return response.text.strip()
        except Exception:
            return "A shimmering form is here, but it's difficult to make out."

    def _construct_perception_prompt(self, subject: Entity) -> str:
        """Constructs the prompt to generate a first-glance description."""
        prompt_template = f"""
Role: You are a creative writer for a text-based game.

Context: A player has just entered a room and seen an object for the first time.

Object's Ground Truth: This is the objective, hidden information about the object.
{json.dumps(subject.data, indent=2)}

Instruction: Write a brief, one-sentence description of this object from the player's perspective.
- Be evocative and mysterious.
- Do not reveal the object's name or true purpose.
- Focus on its appearance and general impression.
- Your response must be a single string.
"""
        return prompt_template.strip()

    def _look_around(self, player_location_id: str) -> str:
        """Describes the current location and the items within it."""
        if not player_location_id:
            return "I need a player location ID to look around."

        location = self.entity_db.get(player_location_id)
        if not location:
            return f"The location '{player_location_id}' is not recognized."
        
        player = self.get_player_entity()
        if not player:
            return "Error: Player could not be found."

        # Find entities in the same location
        entities_in_location = self.entity_db.get_entities_by_property("location_id", player_location_id)
        other_entities = [e for e in entities_in_location if e.unique_id != player.unique_id and e.unique_id != player_location_id]

        if not other_entities:
            return f"{location.data.get('description', 'It is an empty room.')}"

        descriptions = []
        for entity in other_entities:
            # If the player has seen this entity before, use its known name.
            # Otherwise, generate a first-glance perception.
            known_facts = self.knowledge_manager.get_facts(player.unique_id, entity.unique_id)
            if known_facts:
                # A simple way to get a "name" from facts. This could be improved.
                # It is not used now, but it's a good idea for the future
                # descriptions.append(f"You see a {entity.data.get('name', 'mysterious object')}.")
                pass
            else:
                perception = self._generate_initial_perception(entity)
                if perception:
                    # Add the perception as the first fact the player learns.
                    self.knowledge_manager.add_fact(player.unique_id, entity.unique_id, perception)
        
        # Now get all the facts again to construct the final description
        all_descriptions = []
        for entity in other_entities:
            facts = self.knowledge_manager.get_facts(player.unique_id, entity.unique_id)
            if facts:
                 all_descriptions.extend(facts)

        if not all_descriptions:
             return f"{location.data.get('description', 'It is an empty room.')}"
        
        return f"{location.data.get('description', 'You are in a room.')} " + " ".join(all_descriptions)

    def _examine(self, target_string: str, player_location_id: str) -> str:
        """Examines an object or character, revealing more details."""
        if not player_location_id:
            return "I need a player location ID to examine something."

        location = self.entity_db.get(player_location_id)
        if not location:
            return f"The location '{player_location_id}' is not recognized."
        
        player = self.get_player_entity()
        if not player:
            return "Error: Player could not be found."

        # Find entities in the same location
        entities_in_location = self.entity_db.get_entities_by_property("location_id", player_location_id)
        other_entities = [e for e in entities_in_location if e.unique_id != player.unique_id and e.unique_id != player_location_id]

        if not other_entities:
            return "There is nothing here to examine."

        # Use the LLM to resolve the entity
        resolved_entity_id = self._resolve_entity_for_examine(target_string, player, other_entities)

        if not resolved_entity_id:
            return f"I see nothing here that matches '{target_string}'."

        subject = self.entity_db.get(resolved_entity_id)
        if not subject:
            return "Error: Could not find the specified entity."

        # Generate a description of the entity
        newly_learned_facts = self._generate_facts_for_examine(player, f"examine {target_string}", subject)
        for fact in newly_learned_facts:
            self.knowledge_manager.add_fact(player.unique_id, subject.unique_id, fact)

        all_facts = self.knowledge_manager.get_facts(player.unique_id, subject.unique_id)

        if not all_facts:
            return f"You examine the {subject.data.get('name', 'object')} and find nothing of interest."

        # The first fact is usually the initial perception. We can make the output nicer.
        response = f"You examine the {subject.data.get('name', 'object')}:\n"
        response += "\n".join(all_facts)
        return response

    def _go_to(self, destination_string: str, player_location_id: str) -> str:
        """Moves the player to a new location."""
        # This is a stub for now.
        return f"OK. I can't go to '{destination_string}' yet. The game doesn't support that action." 