"""
This module defines the KnowledgeManager class, which is responsible for
tracking what each character knows about every other entity in the game world.
"""
from collections import defaultdict

class KnowledgeManager:
    """
    Manages the knowledge base of all characters.

    The core data structure is a nested dictionary:
    knowledge[knower_id][subject_id] -> [list_of_fact_strings]
    """
    def __init__(self):
        """Initializes the KnowledgeManager."""
        self.knowledge = defaultdict(lambda: defaultdict(list))

    def add_fact(self, knower_id: str, subject_id: str, fact: str):
        """
        Adds a fact to a character's knowledge base about a subject.

        Args:
            knower_id: The unique ID of the character who is learning.
            subject_id: The unique ID of the entity being learned about.
            fact: The string representation of the fact being learned.
        """
        if fact not in self.knowledge[knower_id][subject_id]:
            self.knowledge[knower_id][subject_id].append(fact)

    def get_facts(self, knower_id: str, subject_id: str) -> list[str]:
        """
        Retrieves all known facts a character has about a subject.

        Args:
            knower_id: The unique ID of the character who knows.
            subject_id: The unique ID of the entity being asked about.

        Returns:
            A list of fact strings. Returns an empty list if nothing is known.
        """
        return self.knowledge.get(knower_id, {}).get(subject_id, []) 