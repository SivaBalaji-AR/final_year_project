"""
AssemblyAI Universal Streaming (v3) Speech-to-Text Provider

Connects to AssemblyAI's v3 Universal Streaming WebSocket API to stream
audio and receive transcripts. Sends raw PCM 16-bit mono audio bytes.

Migration from v2:
  - Endpoint changed to wss://streaming.assemblyai.com/v3/ws
  - Auth via temporary token (fetched from REST API), not header
  - Audio sent as raw binary, not base64 JSON
  - Receives 'Turn' messages with end_of_turn flag instead of
    PartialTranscript / FinalTranscript
"""

import json
import asyncio
import logging
from typing import Callable, Optional, Awaitable

import httpx
import websockets

logger = logging.getLogger("assemblyai_stt")

ASSEMBLYAI_TOKEN_URL = "https://streaming.assemblyai.com/v3/token"
ASSEMBLYAI_WS_URL = "wss://streaming.assemblyai.com/v3/ws"
SAMPLE_RATE = 16000
TOKEN_EXPIRY_SECONDS = 480  # 8 minutes (max 600)


class AssemblyAIStreamingSTT:
    """Real-time speech-to-text using AssemblyAI's v3 Universal Streaming API."""

    def __init__(
        self,
        api_key: str,
        on_partial_transcript: Optional[Callable[[str], Awaitable[None]]] = None,
        on_final_transcript: Optional[Callable[[str], Awaitable[None]]] = None,
        sample_rate: int = SAMPLE_RATE,
    ):
        self.api_key = api_key
        self.on_partial_transcript = on_partial_transcript
        self.on_final_transcript = on_final_transcript
        self.sample_rate = sample_rate
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False
        # AssemblyAI v3 can fire end_of_turn=true more than once per utterance.
        # We track the last turn_order we already dispatched and ignore repeats.
        self._last_fired_turn_order: int = -1
        self._dispatch_lock = asyncio.Lock()

    async def _get_temporary_token(self) -> str:
        """Fetch a short-lived token from AssemblyAI's token endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                ASSEMBLYAI_TOKEN_URL,
                headers={"Authorization": self.api_key},
                params={"expires_in_seconds": TOKEN_EXPIRY_SECONDS},
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("token")
            if not token:
                raise ValueError(f"No token in AssemblyAI response: {data}")
            return token

    async def connect(self):
        """Open WebSocket connection to AssemblyAI v3 Universal Streaming."""
        try:
            token = await self._get_temporary_token()
            logger.info("Obtained AssemblyAI temporary streaming token")
        except Exception as e:
            logger.error(f"Failed to get AssemblyAI temp token: {e}")
            raise

        url = (
            f"{ASSEMBLYAI_WS_URL}"
            f"?token={token}"
            f"&sample_rate={self.sample_rate}"
            f"&format_turns=true"
        )

        try:
            self._ws = await websockets.connect(
                url,
                ping_interval=5,
                ping_timeout=20,
            )
            self._connected = True
            # Start receiving messages in background
            self._receive_task = asyncio.create_task(self._receive_loop())
            logger.info("Connected to AssemblyAI v3 Universal Streaming STT")
        except Exception as e:
            logger.error(f"Failed to connect to AssemblyAI: {e}")
            raise

    async def send_audio(self, audio_chunk: bytes):
        """Send a chunk of raw PCM audio (16-bit mono) to AssemblyAI.

        v3 API accepts raw binary audio directly — no base64 encoding needed.
        """
        if not self._ws or not self._connected:
            return

        try:
            await self._ws.send(audio_chunk)
        except Exception as e:
            logger.error(f"Error sending audio to AssemblyAI: {e}")

    async def _receive_loop(self):
        """Continuously receive transcript messages from AssemblyAI v3."""
        try:
            async for message in self._ws:
                # v3 sends JSON text messages for transcripts
                if isinstance(message, str):
                    data = json.loads(message)
                    msg_type = data.get("type", "")

                    if msg_type == "Turn":
                        transcript = data.get("transcript", "")
                        end_of_turn = data.get("end_of_turn", False)
                        turn_order = data.get("turn_order", -1)

                        if transcript:
                            if end_of_turn:
                                # Use turn_order as the canonical dedup key.
                                # AssemblyAI v3 can fire end_of_turn=true
                                # multiple times for the same utterance (same
                                # turn_order). The lock prevents a race if two
                                # such messages arrive back-to-back.
                                async with self._dispatch_lock:
                                    if turn_order != self._last_fired_turn_order:
                                        self._last_fired_turn_order = turn_order
                                        logger.debug(
                                            "Final turn %d: %s",
                                            turn_order, transcript[:80],
                                        )
                                        if self.on_final_transcript:
                                            await self.on_final_transcript(transcript)
                                    else:
                                        logger.debug(
                                            "Duplicate end_of_turn for turn_order=%d ignored",
                                            turn_order,
                                        )
                            else:
                                # Partial transcript — show live text
                                if self.on_partial_transcript:
                                    await self.on_partial_transcript(transcript)

                    elif msg_type == "Begin":
                        session_id = data.get("id", "")
                        logger.info(
                            f"AssemblyAI v3 session started: {session_id}"
                        )

                    elif msg_type == "Termination":
                        audio_dur = data.get("audio_duration_seconds", 0)
                        logger.info(
                            f"AssemblyAI session terminated "
                            f"({audio_dur}s of audio processed)"
                        )
                        break

                    elif msg_type == "Error":
                        error = data.get("error", "Unknown error")
                        logger.error(f"AssemblyAI error: {error}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"AssemblyAI WebSocket connection closed: {e}")
        except Exception as e:
            logger.error(f"Error in AssemblyAI receive loop: {e}")
        finally:
            self._connected = False

    async def close(self):
        """Close the WebSocket connection."""
        self._connected = False
        if self._ws:
            try:
                # v3 terminate message format
                await self._ws.send(json.dumps({"type": "Terminate"}))
                await self._ws.close()
            except Exception:
                pass
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        logger.info("AssemblyAI STT connection closed")

    @property
    def is_connected(self) -> bool:
        return self._connected
