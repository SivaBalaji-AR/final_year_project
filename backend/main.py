import os
import json
import logging
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants
from pydantic import BaseModel
from emotion_logger import (
    get_or_create_session, 
    close_session, 
    FairnessMetrics
)

load_dotenv()

logger = logging.getLogger("main")

# Create the FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request validation
class EmotionData(BaseModel):
    session_id: str
    anxiety: float
    confidence: float
    engagement: float
    raw_facial: dict
    raw_vocal: dict
    fused_emotion: str


class SessionInit(BaseModel):
    session_id: str
    participant_name: str
    gender: str
    topic: str


class AdaptationLog(BaseModel):
    session_id: str
    emotion_state: dict
    action: str
    reason: str
    question_difficulty: str
    tone: str


class AgentResponse(BaseModel):
    session_id: str
    candidate_message: str
    adaptive_response: str
    static_response: str
    emotion_at_time: dict


@app.get("/token")
async def get_token(room_name: str, participant_name: str, topic: str = "General", gender: str = "unspecified"):
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not api_key or not api_secret:
        return {"error": "Server misconfigured"}, 500

    # Create access token with metadata containing the topic and gender
    grant = VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True)
    access_token = AccessToken(api_key, api_secret)
    access_token.with_identity(participant_name)
    access_token.with_grants(grant)
    
    # Add topic and gender as participant metadata
    access_token.with_metadata(json.dumps({
        "topic": topic,
        "gender": gender
    }))

    print(f"DEBUG: Token generated for {participant_name} in room {room_name}, topic: {topic}, gender: {gender}")
    return {"token": access_token.to_jwt(), "session_id": room_name}


@app.post("/session/init")
async def init_session(data: SessionInit):
    """Initialize a new interview session"""
    print(f"DEBUG: init_session called with session_id={data.session_id}, name={data.participant_name}, gender={data.gender}, topic={data.topic}")
    session = get_or_create_session(data.session_id)
    session.initialize_session(data.participant_name, data.gender, data.topic)
    print(f"DEBUG: Session {data.session_id} initialized")
    return {"status": "ok", "session_id": data.session_id}


@app.post("/emotion/log")
async def log_emotion(data: EmotionData):
    """Log emotion state to the session timeline"""
    print(f"DEBUG: log_emotion called for session_id={data.session_id}")
    session = get_or_create_session(data.session_id)
    entry = session.log_emotion({
        "anxiety": data.anxiety,
        "confidence": data.confidence,
        "engagement": data.engagement,
        "raw_facial": data.raw_facial,
        "raw_vocal": data.raw_vocal,
        "fused_emotion": data.fused_emotion
    })
    print(f"DEBUG: Logged emotion for {data.session_id}, total emotions: {len(session.session_data['emotion_timeline'])}")
    return {"status": "ok", "entry": entry}


@app.post("/adaptation/log")
async def log_adaptation(data: AdaptationLog):
    """Log an adaptation decision"""
    session = get_or_create_session(data.session_id)
    entry = session.log_adaptation(
        data.emotion_state,
        data.action,
        data.reason,
        data.question_difficulty,
        data.tone
    )
    return {"status": "ok", "entry": entry}


@app.post("/agent/response")
async def log_agent_response(data: AgentResponse):
    """Log both agent responses for comparison"""
    session = get_or_create_session(data.session_id)
    entry = session.log_agent_response(
        data.candidate_message,
        data.adaptive_response,
        data.static_response,
        data.emotion_at_time
    )
    return {"status": "ok", "entry": entry}


@app.post("/session/end/{session_id}")
async def end_session(session_id: str):
    """End an interview session"""
    close_session(session_id)
    return {"status": "ok"}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get current session data"""
    session = get_or_create_session(session_id)
    return session.get_session_data()


@app.get("/fairness/metrics")
async def get_fairness_metrics():
    """Get demographic parity and fairness metrics"""
    return {
        "demographic_parity": FairnessMetrics.calculate_demographic_parity(),
        "comparison_metrics": FairnessMetrics.get_comparison_metrics()
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# WebSocket for real-time emotion updates to the agent
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_emotion(self, session_id: str, emotion_data: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(emotion_data)


manager = ConnectionManager()


@app.websocket("/ws/emotion/{session_id}")
async def websocket_emotion(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time emotion streaming"""
    await manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Log the emotion
            session = get_or_create_session(session_id)
            session.log_emotion(data)
            # Broadcast back (could be used by dashboard)
            await manager.send_emotion(session_id, data)
    except WebSocketDisconnect:
        manager.disconnect(session_id)
