"""
Groq LLM Provider

Uses the Groq SDK to interact with Llama 3.3 70B (or other models).
Maintains conversation history per session for multi-turn dialogue.

Groq offers very fast inference with generous free-tier rate limits
(30 RPM, 14,400 RPD for most models).
"""

import asyncio
import logging
from typing import List, Dict, Optional

from groq import AsyncGroq

logger = logging.getLogger("groq_llm")


class GroqLLM:
    """Conversational LLM using Groq's fast inference API."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
    ):
        self.client = AsyncGroq(api_key=api_key)
        self.model_name = model_name
        self._system_prompt: str = ""
        self._history: List[Dict[str, str]] = []

    def start_conversation(self, system_prompt: str):
        """Start a new conversation with the given system prompt."""
        self._system_prompt = system_prompt
        self._history = []
        logger.info("Groq conversation started")

    def update_system_prompt(self, new_system_prompt: str):
        """Update the system prompt (e.g., when emotion context changes).
        
        Preserves existing conversation history.
        """
        self._system_prompt = new_system_prompt
        logger.debug("Groq system prompt updated with preserved history")

    async def generate_response(self, user_message: str) -> str:
        """Send a user message and get the AI response.
        
        Args:
            user_message: The transcribed speech from the candidate.
            
        Returns:
            The AI interviewer's text response.
        """
        try:
            # Add user message to history
            self._history.append({"role": "user", "content": user_message})

            # Build messages list: system prompt + conversation history
            messages = [
                {"role": "system", "content": self._system_prompt},
                *self._history,
            ]

            # Generate response via Groq
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )

            response_text = response.choices[0].message.content.strip()

            # Add assistant response to history
            self._history.append({"role": "assistant", "content": response_text})

            logger.debug(f"Groq response: {response_text[:100]}...")
            return response_text

        except Exception as e:
            logger.error(f"Error getting Groq response: {e}")
            # Remove the failed user message from history
            if self._history and self._history[-1]["role"] == "user":
                self._history.pop()
            raise

    def get_history(self) -> List[Dict]:
        """Return the conversation history for logging."""
        result = []
        for msg in self._history:
            result.append({"role": msg["role"], "text": msg["content"]})
        return result
