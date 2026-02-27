"""
Cartesia Text-to-Speech Provider

Uses Cartesia's REST API to convert text to speech audio.
Returns raw PCM audio (16-bit signed LE, 16kHz mono) for streaming.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger("cartesia_tts")

CARTESIA_TTS_URL = "https://api.cartesia.ai/tts/bytes"
CARTESIA_API_VERSION = "2025-04-16"
DEFAULT_VOICE_ID = "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
DEFAULT_MODEL_ID = "sonic-3"
SAMPLE_RATE = 16000


class CartesiaTTS:
    """Text-to-speech using Cartesia's REST API."""

    def __init__(
        self,
        api_key: str,
        voice_id: str = DEFAULT_VOICE_ID,
        model_id: str = DEFAULT_MODEL_ID,
        sample_rate: int = SAMPLE_RATE,
    ):
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        self.sample_rate = sample_rate
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-initialize the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def synthesize(self, text: str) -> bytes:
        """Convert text to speech audio.
        
        Args:
            text: The text to synthesize.
            
        Returns:
            Raw PCM audio bytes (16-bit signed LE, mono at configured sample rate).
        """
        if not text.strip():
            return b""

        client = await self._get_client()

        payload = {
            "model_id": self.model_id,
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self.voice_id,
            },
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self.sample_rate,
            },
            "language": "en",
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Cartesia-Version": CARTESIA_API_VERSION,
            "Content-Type": "application/json",
        }

        try:
            response = await client.post(
                CARTESIA_TTS_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            audio_data = response.content
            logger.info(f"Cartesia TTS: generated {len(audio_data)} bytes for {len(text)} chars")
            return audio_data
        except httpx.HTTPStatusError as e:
            logger.error(f"Cartesia TTS HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Cartesia TTS error: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("Cartesia TTS client closed")
