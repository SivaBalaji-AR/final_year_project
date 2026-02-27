"""
Audio Pipeline - Orchestrates the full interview audio pipeline.

Manages the flow: Browser Audio/Video → Server-Side Analysis → LLM → TTS → Browser
All face and vocal analysis is done server-side.
"""

import os
import json
import asyncio
import logging
import traceback
from typing import Optional

from fastapi import WebSocket

from adaptive_agent import AdaptiveInterviewerAgent
from providers.assemblyai_stt import AssemblyAIStreamingSTT
from providers.groq_llm import GroqLLM
from providers.cartesia_tts import CartesiaTTS
from providers.face_analyzer import FaceAnalyzer
from providers.vocal_analyzer import VocalAnalyzer
from analysis_store import analysis_store
from emotion_logger import get_or_create_session

logger = logging.getLogger("audio_pipeline")

# Audio config
SAMPLE_RATE = 16000
AUDIO_CHUNK_SIZE = SAMPLE_RATE * 2 * 50 // 1000  # 1600 bytes per 50ms

# Fusion weights
FACE_WEIGHT = 0.4
VOCAL_WEIGHT = 0.6

# Analyze every Nth audio chunk for vocal features (throttle)
VOCAL_ANALYSIS_INTERVAL = 3


class InterviewPipeline:
    """Manages a single interview session's audio pipeline.
    
    Receives audio + video from the browser WebSocket, processes everything
    server-side, and sends only TTS audio + transcript back.
    """

    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        topic: str,
        gender: str,
        participant_name: str,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.topic = topic
        self.gender = gender
        self.participant_name = participant_name

        # Create the adaptive agent
        self.agent = AdaptiveInterviewerAgent(topic=topic, session_id=session_id)

        # Provider instances
        self.stt: Optional[AssemblyAIStreamingSTT] = None
        self.llm: Optional[GroqLLM] = None
        self.tts: Optional[CartesiaTTS] = None

        # Server-side analyzers
        self.face_analyzer = FaceAnalyzer()
        self.vocal_analyzer = VocalAnalyzer(sample_rate=SAMPLE_RATE)

        # State
        self._running = False
        self._is_speaking = False
        self._processing_lock = asyncio.Lock()
        self._audio_chunk_count = 0

    async def start(self):
        """Initialize all providers and start the pipeline."""
        logger.info(f"Starting interview pipeline for session {self.session_id}")

        assemblyai_key = os.getenv("ASSEMBLYAI_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")
        cartesia_key = os.getenv("CARTESIA_API_KEY")

        if not all([assemblyai_key, groq_key, cartesia_key]):
            missing = []
            if not assemblyai_key: missing.append("ASSEMBLYAI_API_KEY")
            if not groq_key: missing.append("GROQ_API_KEY")
            if not cartesia_key: missing.append("CARTESIA_API_KEY")
            error_msg = f"Missing API keys: {', '.join(missing)}"
            logger.error(error_msg)
            await self._send_json({"type": "error", "message": error_msg})
            raise ValueError(error_msg)

        # Initialize LLM
        logger.info("Initializing Groq LLM...")
        self.llm = GroqLLM(api_key=groq_key)
        self.llm.start_conversation(self.agent.system_prompt)

        # Initialize TTS
        logger.info("Initializing Cartesia TTS...")
        self.tts = CartesiaTTS(api_key=cartesia_key, sample_rate=SAMPLE_RATE)

        # Connect to AssemblyAI STT
        logger.info("Connecting to AssemblyAI STT...")
        self.stt = AssemblyAIStreamingSTT(
            api_key=assemblyai_key,
            on_partial_transcript=self._on_partial_transcript,
            on_final_transcript=self._on_final_transcript,
            sample_rate=SAMPLE_RATE,
        )
        try:
            await asyncio.wait_for(self.stt.connect(), timeout=10.0)
            logger.info("AssemblyAI STT connected")
        except asyncio.TimeoutError:
            logger.error("AssemblyAI STT connection timed out")
            await self._send_json({
                "type": "error",
                "message": "Speech-to-text connection timed out."
            })
        except Exception as e:
            logger.error(f"AssemblyAI STT connection failed: {e}")
            await self._send_json({
                "type": "error",
                "message": f"Speech-to-text connection failed: {str(e)}"
            })

        self._running = True

        # Create session in analysis store
        analysis_store.create_session(
            self.session_id, self.participant_name, self.topic, self.gender
        )

        # Initialize emotion logger session
        session = get_or_create_session(self.session_id)
        session.initialize_session(self.participant_name, self.gender, self.topic)

        # Generate opening in background
        asyncio.create_task(self._generate_opening_safe())

        logger.info(f"Interview pipeline started for session {self.session_id}")

    async def _generate_opening_safe(self):
        """Generate opening message with error handling."""
        try:
            await self._generate_opening()
        except Exception as e:
            logger.error(f"Error in opening generation: {e}\n{traceback.format_exc()}")
            await self._send_json({
                "type": "error",
                "message": f"Failed to generate opening: {str(e)}"
            })

    async def _generate_opening(self):
        """Generate and send the opening message."""
        logger.info("Generating opening message...")
        await self._send_json({"type": "status", "status": "thinking"})

        opening_prompt = self.agent.get_opening_prompt()
        try:
            response = await asyncio.wait_for(
                self.llm.generate_response(opening_prompt),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.error("Gemini timed out on opening")
            await self._send_json({"type": "error", "message": "AI response timed out."})
            return

        logger.info(f"Opening: {response[:80]}...")

        await self._send_json({
            "type": "transcript", "role": "assistant", "text": response,
        })

        # Log to analysis store
        await analysis_store.add_transcript_entry(
            self.session_id, "assistant", response
        )

        # Synthesize TTS
        try:
            await asyncio.wait_for(self._synthesize_and_send(response), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Cartesia TTS timed out on opening")

        # Log to emotion logger
        session = get_or_create_session(self.session_id)
        session.log_agent_response(
            candidate_message="[session_start]",
            adaptive_response=response,
            static_response="",
            emotion_at_time=self.agent.emotion_context.to_dict(),
        )

    async def handle_audio(self, audio_data: bytes):
        """Handle incoming audio from the browser.
        
        Routes to:
        1. AssemblyAI STT for transcription
        2. VocalAnalyzer for server-side vocal analysis
        """
        if not self._running:
            return

        # Skip mic audio while TTS is playing
        if self._is_speaking:
            return

        # Forward to STT
        if self.stt and self.stt.is_connected:
            await self.stt.send_audio(audio_data)

        # Server-side vocal analysis (throttled)
        self._audio_chunk_count += 1
        if self._audio_chunk_count % VOCAL_ANALYSIS_INTERVAL == 0:
            vocal_result = self.vocal_analyzer.analyze_chunk(audio_data)
            if vocal_result:
                await analysis_store.update_vocal_analysis(
                    self.session_id, vocal_result
                )
                # Fuse with latest face emotions
                await self._fuse_emotions(vocal_emotions=vocal_result.get("emotions"))

    async def handle_video_frame(self, jpeg_data: bytes):
        """Handle incoming video frame from browser.
        
        Processes with MediaPipe Face Mesh server-side.
        """
        if not self._running:
            return

        # Analyze face in a thread pool to not block event loop
        loop = asyncio.get_event_loop()
        face_result = await loop.run_in_executor(
            None, self.face_analyzer.analyze_frame, jpeg_data
        )

        if face_result:
            await analysis_store.update_face_analysis(
                self.session_id, face_result
            )
            # Fuse with latest vocal emotions
            await self._fuse_emotions(face_emotions=face_result.get("emotions"))

    async def _fuse_emotions(
        self,
        face_emotions: Optional[dict] = None,
        vocal_emotions: Optional[dict] = None,
    ):
        """Fuse face and vocal emotions, update agent."""
        session_data = analysis_store.get_session(self.session_id)
        if not session_data:
            return

        face = face_emotions or session_data.latest_face_emotions or {"anxiety": 0.5, "confidence": 0.5, "engagement": 0.5}
        vocal = vocal_emotions or session_data.latest_vocal_emotions or {"anxiety": 0.5, "confidence": 0.5, "engagement": 0.5}

        fused = {
            "anxiety": round(FACE_WEIGHT * face["anxiety"] + VOCAL_WEIGHT * vocal["anxiety"], 3),
            "confidence": round(FACE_WEIGHT * face["confidence"] + VOCAL_WEIGHT * vocal["confidence"], 3),
            "engagement": round(FACE_WEIGHT * face["engagement"] + VOCAL_WEIGHT * vocal["engagement"], 3),
        }

        await analysis_store.update_fused_emotions(self.session_id, fused)

        # Update agent's adaptive behavior
        self.agent.update_emotions(fused["anxiety"], fused["confidence"], fused["engagement"])
        if self.llm:
            self.llm.update_system_prompt(self.agent.system_prompt)

        # Log adaptation
        adaptation = {
            "action": f"Adjusted to {self.agent.emotion_context.get_difficulty_level()} difficulty "
                      f"with {self.agent.emotion_context.get_tone()} tone",
            "difficulty": self.agent.emotion_context.get_difficulty_level(),
            "tone": self.agent.emotion_context.get_tone(),
            "fused_emotions": fused,
        }
        await analysis_store.add_adaptation(self.session_id, adaptation)

        # Also log to emotion_logger for file persistence
        el_session = get_or_create_session(self.session_id)
        el_session.log_emotion(fused)
        el_session.log_adaptation(
            fused,
            adaptation["action"],
            f"Fused anxiety={fused['anxiety']}, confidence={fused['confidence']}, engagement={fused['engagement']}",
            adaptation["difficulty"],
            adaptation["tone"],
        )

    async def _on_partial_transcript(self, text: str):
        """Handle partial transcript from AssemblyAI."""
        await self._send_json({
            "type": "transcript", "role": "user", "text": text, "is_final": False,
        })
        await analysis_store.add_transcript_entry(
            self.session_id, "user", text, is_final=False
        )

    async def _on_final_transcript(self, text: str):
        """Handle final transcript — triggers LLM response."""
        if not text.strip():
            return

        logger.info(f"Final transcript: {text}")

        await self._send_json({
            "type": "transcript", "role": "user", "text": text, "is_final": True,
        })
        await analysis_store.add_transcript_entry(
            self.session_id, "user", text, is_final=True
        )

        async with self._processing_lock:
            await self._process_user_message(text)

    async def _process_user_message(self, user_text: str):
        """Process a user message through LLM and TTS."""
        if not self.llm or not self.tts:
            return

        try:
            await self._send_json({"type": "status", "status": "thinking"})

            try:
                response = await asyncio.wait_for(
                    self.llm.generate_response(user_text), timeout=30.0
                )
            except asyncio.TimeoutError:
                await self._send_json({"type": "error", "message": "AI response timed out"})
                return

            await self._send_json({
                "type": "transcript", "role": "assistant", "text": response,
            })
            await analysis_store.add_transcript_entry(
                self.session_id, "assistant", response
            )

            session = get_or_create_session(self.session_id)
            session.log_agent_response(
                user_text, response, "",
                self.agent.emotion_context.to_dict(),
            )

            await self._synthesize_and_send(response)

        except Exception as e:
            logger.error(f"Error processing message: {e}\n{traceback.format_exc()}")
            await self._send_json({
                "type": "error", "message": f"Error: {str(e)}",
            })

    async def _synthesize_and_send(self, text: str):
        """Convert text to speech and send audio."""
        if not self.tts:
            return

        try:
            self._is_speaking = True
            await self._send_json({"type": "status", "status": "speaking"})

            try:
                audio_data = await asyncio.wait_for(
                    self.tts.synthesize(text), timeout=30.0
                )
            except asyncio.TimeoutError:
                await self._send_json({"type": "error", "message": "TTS timed out"})
                return

            if audio_data:
                for i in range(0, len(audio_data), AUDIO_CHUNK_SIZE):
                    if not self._running:
                        break
                    chunk = audio_data[i:i + AUDIO_CHUNK_SIZE]
                    try:
                        await self.websocket.send_bytes(chunk)
                    except Exception:
                        break
                    await asyncio.sleep(0.01)

                await self._send_json({"type": "status", "status": "done_speaking"})

        except Exception as e:
            logger.error(f"TTS error: {e}\n{traceback.format_exc()}")
        finally:
            self._is_speaking = False
            await self._send_json({"type": "status", "status": "listening"})

    async def _send_json(self, data: dict):
        """Send a JSON message to the client."""
        try:
            await self.websocket.send_json(data)
        except Exception as e:
            logger.error(f"Error sending JSON: {e}")

    async def stop(self):
        """Stop the pipeline and clean up."""
        self._running = False
        logger.info(f"Stopping pipeline for session {self.session_id}")

        if self.stt:
            await self.stt.close()
        if self.tts:
            await self.tts.close()

        self.face_analyzer.close()
        analysis_store.end_session(self.session_id)

        logger.info(f"Pipeline stopped for session {self.session_id}")
