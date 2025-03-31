from utils.llm_api import generate_response

class BaseCharacter:
    def __init__(self, name, description):
        self.name = name
        self.description = description
        # TODO: Add conversation history management

    def get_character_context(self):
        """Returns the base context string for the character."""
        # This can be expanded to include recent conversation history
        return f"You are {self.name}, {self.description}. You are talking to a player in a medieval fantasy tavern."

    def talk(self, player_input):
        """Handles player interaction, gets response from LLM."""
        print(f"{self.name} heard: {player_input}")
        character_context = self.get_character_context()
        # Generate response using the LLM
        response = generate_response(player_input, character_context)
        return response
