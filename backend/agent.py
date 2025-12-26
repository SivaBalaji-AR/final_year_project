import os
from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import silero, assemblyai, google, cartesia

load_dotenv()


class InterviewerAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a professional yet friendly AI interviewer.
            Your goal is to conduct a technical interview for a software engineering role.
            Ask one question at a time. Listen carefully to the candidate's response.
            Be encouraging but rigorous. Start by introducing yourself and asking the candidate to introduce themselves.
            Your responses are concise and conversational.""",
        )


async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    
    session = AgentSession(
        stt=assemblyai.STT(),
        llm=google.LLM(
            model="gemini-2.0-flash",
        ),
        tts=cartesia.TTS(),  # Uses CARTESIA_API_KEY from env
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=InterviewerAgent(),
    )

    print("DEBUG: Session started, waiting a moment before speaking...")
    import asyncio
    await asyncio.sleep(1)  # Give a moment for connection to stabilize
    
    print("DEBUG: Generating greeting...")
    await session.generate_reply(
        instructions="Greet the user warmly. Introduce yourself as an AI interviewer and ask the candidate to introduce themselves."
    )
    print("DEBUG: Greeting generated!")


async def on_job_request(req: agents.JobRequest):
    """Auto-accept all job requests"""
    print(f"DEBUG: Received job request for room: {req.room.name}")
    await req.accept()
    print(f"DEBUG: Accepted job!")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            request_fnc=on_job_request,
        )
    )
