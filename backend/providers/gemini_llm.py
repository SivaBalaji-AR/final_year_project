"""
Google Gemini LLM Provider

Uses the google-genai SDK to interact with Gemini 2.0 Flash.
Maintains conversation history per session for multi-turn dialogue.

Rate-limit handling:
  - SDK internal retries are DISABLED (they cause request storms).
  - We handle 429 ourselves with long delays (10s → 30s → 60s).
  - A global lock prevents concurrent calls from racing on quota.
"""

import asyncio
import logging
from typing import List, Dict, Optional

from google import genai
from google.genai import types
from google.genai.errors import ClientError

logger = logging.getLogger("gemini_llm")

# Retry configuration for 429 rate-limit errors
MAX_RETRIES = 3
# Longer delays so the per-minute quota actually resets between retries
RETRY_DELAYS = [10.0, 30.0, 60.0]


class GeminiLLM:
    """Conversational LLM using Google Gemini 2.0 Flash."""

    # Global lock: only one Gemini request at a time to avoid quota storms
    _request_lock = asyncio.Lock()

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.0-flash-lite",
    ):
        # Disable the SDK's internal tenacity retry (attempts=0)
        # This prevents the SDK from making 4+ rapid retries on 429 errors
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                api_version="v1beta",
            ),
        )
        self.model_name = model_name
        self._system_prompt: str = ""
        self._history: List[types.Content] = []

    def start_conversation(self, system_prompt: str):
        """Start a new conversation with the given system prompt."""
        self._system_prompt = system_prompt
        self._history = []
        logger.info("Gemini conversation started")

    def update_system_prompt(self, new_system_prompt: str):
        """Update the system prompt (e.g., when emotion context changes).
        
        Preserves existing conversation history.
        """
        self._system_prompt = new_system_prompt
        logger.debug("Gemini system prompt updated with preserved history")

    async def _call_with_retry(self):
        """Call Gemini API with controlled retry for 429 errors.
        
        Uses long delays between retries to let the per-minute quota reset.
        Only one request at a time via the global lock.
        """
        async with self._request_lock:
            last_error = None
            for attempt in range(MAX_RETRIES):
                try:
                    response = await self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=self._history,
                        config=types.GenerateContentConfig(
                            system_instruction=self._system_prompt,
                        ),
                    )
                    return response
                except ClientError as e:
                    last_error = e
                    if e.status == 429 and attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(
                            f"Gemini rate-limited (429). Waiting {delay}s before "
                            f"retry {attempt + 1}/{MAX_RETRIES}..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise
            raise last_error

    async def generate_response(self, user_message: str) -> str:
        """Send a user message and get the AI response.
        
        Args:
            user_message: The transcribed speech from the candidate.
            
        Returns:
            The AI interviewer's text response.
        """
        try:
            # Add user message to history
            self._history.append(
                types.Content(role="user", parts=[types.Part(text=user_message)])
            )

            # Generate response with controlled retry for rate limits
            response = await self._call_with_retry()

            response_text = response.text.strip()

            # Add assistant response to history
            self._history.append(
                types.Content(role="model", parts=[types.Part(text=response_text)])
            )

            logger.debug(f"Gemini response: {response_text[:100]}...")
            return response_text

        except Exception as e:
            logger.error(f"Error getting Gemini response: {e}")
            # Remove the failed user message from history
            if self._history and self._history[-1].role == "user":
                self._history.pop()
            raise

    def get_history(self) -> List[Dict]:
        """Return the conversation history for logging."""
        result = []
        for content in self._history:
            role = content.role
            text = content.parts[0].text if content.parts else ""
            result.append({"role": role, "text": text})
        return result

