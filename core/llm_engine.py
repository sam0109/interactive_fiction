"""
This module contains the LLMEngine, responsible for interacting with the
generative AI model.
"""
import logging

from google import genai
import config

class LLMEngine:
    """
    Handles the construction of prompts and parsing of responses from the LLM.
    """
    def __init__(self):
        """
        Initializes the LLM Engine.
        """
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in config.py or environment variables.")
        
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model_name = 'gemini-1.5-flash-latest' 