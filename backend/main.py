import os
import json
import logging
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from emotion_logger import (
    get_or_create_session,
    close_session,
    FairnessMetrics
)
from audio_pipeline import InterviewPipeline
from analysis_store import analysis_store

load_dotenv()

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
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


# ─── Active Pipelines ─────────────────────────────────────────────────────────

active_pipelines: dict[str, InterviewPipeline] = {}


# ─── Interview WebSocket ──────────────────────────────────────────────────────

@app.websocket("/ws/interview/{session_id}")
async def websocket_interview(websocket: WebSocket, session_id: str):
    """Main WebSocket for the interview.
    
    Protocol:
    - First message: JSON {"type": "init", ...}
    - After init:
      - Binary frames starting with 0x01: audio (PCM 16-bit mono 16kHz)
      - Binary frames starting with 0x02: video frame (JPEG)
      - Text frames (JSON): {"type": "end"} to close
    - Server sends:
      - Binary frames: TTS audio
      - Text frames: transcript, status messages
    """
    await websocket.accept()
    pipeline: Optional[InterviewPipeline] = None

    try:
        # Wait for init
        init_data = await websocket.receive_json()
        if init_data.get("type") != "init":
            await websocket.send_json({"type": "error", "message": "First message must be init"})
            await websocket.close()
            return

        topic = init_data.get("topic", "General")
        gender = init_data.get("gender", "unspecified")
        participant_name = init_data.get("participant_name", "Candidate")

        logger.info(f"Interview WS init: session={session_id}, topic={topic}, name={participant_name}")

        pipeline = InterviewPipeline(
            websocket=websocket,
            session_id=session_id,
            topic=topic,
            gender=gender,
            participant_name=participant_name,
        )
        active_pipelines[session_id] = pipeline
        await pipeline.start()

        # Message loop
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.receive":
                if "bytes" in message and message["bytes"]:
                    raw = message["bytes"]
                    if len(raw) < 2:
                        continue

                    # First byte is type prefix
                    msg_type = raw[0]
                    payload = raw[1:]

                    if msg_type == 0x01:
                        # Audio frame
                        await pipeline.handle_audio(payload)
                    elif msg_type == 0x02:
                        # Video frame (JPEG)
                        await pipeline.handle_video_frame(payload)
                    else:
                        # Legacy: no prefix = audio
                        await pipeline.handle_audio(raw)

                elif "text" in message and message["text"]:
                    try:
                        data = json.loads(message["text"])
                        if data.get("type") == "end":
                            logger.info(f"Client ended interview: {session_id}")
                            break
                    except json.JSONDecodeError:
                        pass

    except WebSocketDisconnect:
        logger.info(f"Interview WS disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Interview WS error: {e}")
    finally:
        if pipeline:
            await pipeline.stop()
        if session_id in active_pipelines:
            del active_pipelines[session_id]
        close_session(session_id)
        logger.info(f"Session cleaned up: {session_id}")


# ─── Admin WebSocket ──────────────────────────────────────────────────────────

@app.websocket("/ws/admin/{session_id}")
async def websocket_admin(websocket: WebSocket, session_id: str):
    """WebSocket for admin real-time analysis dashboard.
    
    Streams face landmarks, emotions, vocal features, transcript,
    and adaptation data in real-time.
    """
    await websocket.accept()
    await analysis_store.connect_admin(session_id, websocket)

    try:
        while True:
            # Keep alive - admin can also send commands
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "get_state":
                # Send full current state
                analysis = analysis_store.get_session_analysis(session_id)
                if analysis:
                    await websocket.send_json({
                        "type": "full_state",
                        **analysis,
                    })

    except WebSocketDisconnect:
        logger.info(f"Admin WS disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Admin WS error: {e}")
    finally:
        analysis_store.disconnect_admin(session_id, websocket)


# ─── REST Endpoints ───────────────────────────────────────────────────────────

@app.post("/session/init")
async def init_session(data: SessionInit):
    """Initialize a new interview session."""
    logger.info(f"init_session: {data.session_id}, name={data.participant_name}")
    session = get_or_create_session(data.session_id)
    session.initialize_session(data.participant_name, data.gender, data.topic)
    return {"status": "ok", "session_id": data.session_id}


@app.get("/api/sessions")
async def list_sessions():
    """List all interview sessions."""
    return {"sessions": analysis_store.list_sessions()}


@app.get("/api/session/{session_id}/analysis")
async def get_session_analysis(session_id: str):
    """Get full analysis data for a session."""
    analysis = analysis_store.get_session_analysis(session_id)
    if not analysis:
        return {"error": "Session not found"}, 404
    return analysis


@app.post("/adaptation/log")
async def log_adaptation(data: AdaptationLog):
    """Log an adaptation decision."""
    session = get_or_create_session(data.session_id)
    entry = session.log_adaptation(
        data.emotion_state, data.action, data.reason,
        data.question_difficulty, data.tone,
    )
    return {"status": "ok", "entry": entry}


@app.post("/agent/response")
async def log_agent_response(data: AgentResponse):
    """Log agent responses."""
    session = get_or_create_session(data.session_id)
    entry = session.log_agent_response(
        data.candidate_message, data.adaptive_response,
        data.static_response, data.emotion_at_time,
    )
    return {"status": "ok", "entry": entry}


@app.post("/session/end/{session_id}")
async def end_session(session_id: str):
    """End an interview session."""
    pipeline = active_pipelines.pop(session_id, None)
    if pipeline:
        await pipeline.stop()
    close_session(session_id)
    return {"status": "ok"}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get current session data."""
    session = get_or_create_session(session_id)
    return session.get_session_data()


@app.get("/fairness/metrics")
async def get_fairness_metrics():
    """Get demographic parity and fairness metrics."""
    return {
        "demographic_parity": FairnessMetrics.calculate_demographic_parity(),
        "comparison_metrics": FairnessMetrics.get_comparison_metrics()
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
