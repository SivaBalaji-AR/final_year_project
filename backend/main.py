import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants

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

@app.get("/token")
async def get_token(room_name: str = "interview-room", participant_name: str = "Candidate"):
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not api_key or not api_secret:
        return {"error": "Server misconfigured: missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET"}, 500

    # Create access token with room permissions
    grant = VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True)
    access_token = AccessToken(api_key, api_secret)
    access_token.with_identity(participant_name)
    access_token.with_grants(grant)

    print(f"DEBUG: Generated token for {participant_name} in room {room_name}")
    return {"token": access_token.to_jwt()}

@app.get("/health")
async def health():
    return {"status": "ok"}
