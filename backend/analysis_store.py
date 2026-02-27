"""
Analysis Store - In-memory per-session analysis data store.

Holds all analysis data for active interview sessions and streams
updates to connected admin WebSocket clients.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field, asdict

from fastapi import WebSocket

logger = logging.getLogger("analysis_store")


@dataclass
class AnalysisSnapshot:
    """A single snapshot of analysis data at a point in time."""
    timestamp: float
    face_landmarks: Optional[List[Dict]] = None
    face_emotions: Optional[Dict] = None
    micro_expressions: Optional[Dict] = None
    vocal_features: Optional[Dict] = None
    vocal_emotions: Optional[Dict] = None
    fused_emotions: Optional[Dict] = None


@dataclass
class SessionAnalysis:
    """All analysis data for a session."""
    session_id: str
    participant_name: str = ""
    topic: str = ""
    gender: str = ""
    start_time: float = 0
    is_active: bool = True

    # Timelines
    emotion_timeline: List[Dict] = field(default_factory=list)
    adaptation_log: List[Dict] = field(default_factory=list)
    transcript: List[Dict] = field(default_factory=list)

    # Latest snapshot (for real-time display)
    latest_face_landmarks: Optional[List[Dict]] = None
    latest_face_emotions: Optional[Dict] = None
    latest_micro_expressions: Optional[Dict] = None
    latest_vocal_features: Optional[Dict] = None
    latest_vocal_emotions: Optional[Dict] = None
    latest_fused_emotions: Optional[Dict] = None

    # Metrics
    total_frames_analyzed: int = 0
    total_audio_chunks_analyzed: int = 0


class AnalysisStore:
    """In-memory store for analysis data with admin WebSocket streaming."""

    def __init__(self):
        self._sessions: Dict[str, SessionAnalysis] = {}
        self._admin_clients: Dict[str, Set[WebSocket]] = {}  # session_id -> set of admin WS

    def create_session(self, session_id: str, participant_name: str, topic: str, gender: str):
        """Create a new session analysis store."""
        self._sessions[session_id] = SessionAnalysis(
            session_id=session_id,
            participant_name=participant_name,
            topic=topic,
            gender=gender,
            start_time=time.time(),
        )
        logger.info(f"Analysis session created: {session_id}")

    def get_session(self, session_id: str) -> Optional[SessionAnalysis]:
        """Get session analysis data."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[Dict]:
        """List all sessions with basic info."""
        return [
            {
                "session_id": s.session_id,
                "participant_name": s.participant_name,
                "topic": s.topic,
                "gender": s.gender,
                "start_time": s.start_time,
                "is_active": s.is_active,
                "total_frames": s.total_frames_analyzed,
            }
            for s in self._sessions.values()
        ]

    async def update_face_analysis(self, session_id: str, face_data: Dict):
        """Update face analysis data and notify admin clients."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.latest_face_landmarks = face_data.get("landmarks")
        session.latest_face_emotions = face_data.get("emotions")
        session.latest_micro_expressions = face_data.get("micro_expressions")
        session.total_frames_analyzed += 1

        # Add to emotion timeline
        if face_data.get("emotions"):
            session.emotion_timeline.append({
                "timestamp": time.time(),
                "source": "face",
                **face_data["emotions"],
            })
            # Keep last 500 entries
            if len(session.emotion_timeline) > 500:
                session.emotion_timeline = session.emotion_timeline[-500:]

        # Stream to admin
        await self._broadcast_to_admins(session_id, {
            "type": "face_update",
            "landmarks": face_data.get("landmarks"),
            "emotions": face_data.get("emotions"),
            "micro_expressions": face_data.get("micro_expressions"),
            "frame_number": face_data.get("frame_number"),
        })

    async def update_vocal_analysis(self, session_id: str, vocal_data: Dict):
        """Update vocal analysis data and notify admin clients."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.latest_vocal_features = vocal_data.get("features")
        session.latest_vocal_emotions = vocal_data.get("emotions")
        session.total_audio_chunks_analyzed += 1

        # Stream to admin (throttle - every 5th chunk)
        if vocal_data.get("chunk_number", 0) % 5 == 0:
            await self._broadcast_to_admins(session_id, {
                "type": "vocal_update",
                "features": vocal_data.get("features"),
                "emotions": vocal_data.get("emotions"),
            })

    async def update_fused_emotions(self, session_id: str, fused: Dict):
        """Update fused emotions and notify admin clients."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.latest_fused_emotions = fused

        await self._broadcast_to_admins(session_id, {
            "type": "fused_emotions",
            "emotions": fused,
            "timestamp": time.time(),
        })

    async def add_transcript_entry(self, session_id: str, role: str, text: str, is_final: bool = True):
        """Add a transcript entry."""
        session = self._sessions.get(session_id)
        if not session:
            return

        entry = {
            "timestamp": time.time(),
            "role": role,
            "text": text,
            "is_final": is_final,
        }
        if is_final:
            session.transcript.append(entry)

        await self._broadcast_to_admins(session_id, {
            "type": "transcript",
            "role": role,
            "text": text,
            "is_final": is_final,
        })

    async def add_adaptation(self, session_id: str, adaptation: Dict):
        """Add an adaptation log entry."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.adaptation_log.append({
            "timestamp": time.time(),
            **adaptation,
        })

        await self._broadcast_to_admins(session_id, {
            "type": "adaptation",
            **adaptation,
        })

    def end_session(self, session_id: str):
        """Mark session as inactive."""
        session = self._sessions.get(session_id)
        if session:
            session.is_active = False

    # ─── Admin WebSocket Management ───────────────────────────────────────────

    async def connect_admin(self, session_id: str, websocket: WebSocket):
        """Connect an admin WebSocket client."""
        if session_id not in self._admin_clients:
            self._admin_clients[session_id] = set()
        self._admin_clients[session_id].add(websocket)
        logger.info(f"Admin connected to session {session_id}")

        # Send initial state
        session = self._sessions.get(session_id)
        if session:
            await websocket.send_json({
                "type": "session_info",
                "session_id": session.session_id,
                "participant_name": session.participant_name,
                "topic": session.topic,
                "gender": session.gender,
                "start_time": session.start_time,
                "is_active": session.is_active,
                "emotion_timeline": session.emotion_timeline[-50:],  # Last 50
                "adaptation_log": session.adaptation_log,
                "transcript": session.transcript,
            })

    def disconnect_admin(self, session_id: str, websocket: WebSocket):
        """Disconnect an admin WebSocket client."""
        if session_id in self._admin_clients:
            self._admin_clients[session_id].discard(websocket)
            if not self._admin_clients[session_id]:
                del self._admin_clients[session_id]
        logger.info(f"Admin disconnected from session {session_id}")

    async def _broadcast_to_admins(self, session_id: str, data: Dict):
        """Send data to all connected admin clients for a session."""
        clients = self._admin_clients.get(session_id, set())
        if not clients:
            return

        disconnected = set()
        for ws in clients:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)

        # Remove disconnected clients
        for ws in disconnected:
            clients.discard(ws)

    def get_session_analysis(self, session_id: str) -> Optional[Dict]:
        """Get full session analysis data for REST API."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "participant_name": session.participant_name,
            "topic": session.topic,
            "gender": session.gender,
            "start_time": session.start_time,
            "is_active": session.is_active,
            "emotion_timeline": session.emotion_timeline,
            "adaptation_log": session.adaptation_log,
            "transcript": session.transcript,
            "latest_fused_emotions": session.latest_fused_emotions,
            "latest_micro_expressions": session.latest_micro_expressions,
            "latest_vocal_features": session.latest_vocal_features,
            "total_frames_analyzed": session.total_frames_analyzed,
            "total_audio_chunks_analyzed": session.total_audio_chunks_analyzed,
        }


# Global singleton instance
analysis_store = AnalysisStore()
