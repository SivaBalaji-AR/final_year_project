import json
import asyncio
import aiohttp
from dotenv import load_dotenv
from typing import Optional, Dict

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv()

# Backend API URL for logging
API_BASE_URL = "http://localhost:8000"


class EmotionContext:
    """Holds current emotion state for the interview"""
    def __init__(self):
        self.anxiety = 0.5
        self.confidence = 0.5
        self.engagement = 0.5
        self.last_update = None
    
    def update(self, anxiety: float, confidence: float, engagement: float):
        self.anxiety = anxiety
        self.confidence = confidence
        self.engagement = engagement
    
    def get_difficulty_level(self) -> str:
        """Determine question difficulty based on emotions"""
        if self.anxiety > 0.7:
            return "easy"
        elif self.confidence > 0.7 and self.anxiety < 0.4:
            return "hard"
        else:
            return "medium"
    
    def get_tone(self) -> str:
        """Determine interviewer tone based on emotions"""
        if self.anxiety > 0.7:
            return "encouraging"
        elif self.confidence > 0.7:
            return "challenging"
        elif self.engagement < 0.3:
            return "engaging"
        else:
            return "neutral"
    
    def get_adaptation_instructions(self) -> str:
        """Generate adaptation instructions for the LLM"""
        instructions = []
        
        if self.anxiety > 0.7:
            instructions.append(
                "The candidate appears anxious. Use an encouraging and supportive tone. "
                "Ask simpler follow-up questions. Give them time to think. "
                "Acknowledge their efforts positively."
            )
        elif self.anxiety > 0.5:
            instructions.append(
                "The candidate shows some nervousness. Maintain a calm, reassuring pace."
            )
        
        if self.confidence > 0.7:
            instructions.append(
                "The candidate appears confident. Feel free to ask more challenging questions "
                "and probe deeper into their responses. Push them to demonstrate expertise."
            )
        
        if self.engagement < 0.3:
            instructions.append(
                "The candidate seems disengaged. Try to make the questions more interesting "
                "or ask about real-world applications. Vary your approach to recapture attention."
            )
        elif self.engagement > 0.7:
            instructions.append(
                "The candidate is highly engaged. This is a good opportunity for deeper technical discussion."
            )
        
        return " ".join(instructions) if instructions else "Proceed with standard interview pacing."


class AdaptiveInterviewerAgent(Agent):
    """Interviewer agent that adapts based on candidate emotions"""
    
    def __init__(self, topic: str, emotion_context: EmotionContext, session_id: str) -> None:
        self.emotion_context = emotion_context
        self.session_id = session_id
        self.topic = topic
        
        super().__init__(
            instructions=self._generate_instructions(),
        )
    
    def _generate_instructions(self) -> str:
        adaptation = self.emotion_context.get_adaptation_instructions()
        difficulty = self.emotion_context.get_difficulty_level()
        tone = self.emotion_context.get_tone()
        
        return f"""
You are a professional technical interviewer conducting a real interview.
The interview topic is: {self.topic}.

ADAPTATION MODE: You are the ADAPTIVE interviewer that adjusts based on candidate emotions.
Current difficulty level: {difficulty}
Current tone: {tone}

Emotion-based guidance: {adaptation}

Your behavior:
- Ask clear, focused questions one at a time about {self.topic}.
- IMPORTANT: Adapt difficulty based on the emotion guidance above.
- If difficulty is "easy", ask fundamental concepts and provide more guidance.
- If difficulty is "hard", ask complex scenarios operating and system design questions.
- If difficulty is "medium", follow standard interview progression.
- Probe deeper when answers are shallow and challenge assumptions politely.
- Think like a hiring manager evaluating real-world ability, not textbook knowledge.
- Guide the interview forward and keep it structured.
- Give short feedback when needed but do not teach unless asked.
- Match your tone to the guidance: {tone}.
- Keep the conversation natural and realistic, like a live interview.
- Do not use emojis, special formatting, or unnecessary explanations.
- Focus your questions specifically on {self.topic} concepts and real-world applications.
"""

    def update_instructions(self):
        """Update instructions when emotion context changes"""
        self._instructions = self._generate_instructions()


class StaticInterviewerAgent(Agent):
    """Standard interviewer agent without emotion adaptation (for comparison)"""
    
    def __init__(self, topic: str, session_id: str) -> None:
        self.session_id = session_id
        self.topic = topic
        
        super().__init__(
            instructions=f"""
You are a professional technical interviewer conducting a real interview.
The interview topic is: {topic}.

STATIC MODE: You are the STANDARD interviewer that maintains consistent difficulty.

Your behavior:
- Ask clear, focused questions one at a time about {topic}.
- Progress from basic to advanced questions in a fixed pattern.
- Probe deeper when answers are shallow and challenge assumptions politely.
- Think like a hiring manager evaluating real-world ability, not textbook knowledge.
- Guide the interview forward and keep it structured.
- Give short feedback when needed but do not teach unless asked.
- Stay neutral, confident, and slightly demanding.
- Keep the conversation natural and realistic, like a live interview.
- Do not use emojis, special formatting, or unnecessary explanations.
- Continue asking questions until the interview feels complete.
- Focus your questions specifically on {topic} concepts and real-world applications.
""",
        )


server = AgentServer()


@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    # Connect to the room first
    await ctx.connect()
    
    # Wait for participant to join and get their metadata
    participant = await ctx.wait_for_participant()
    
    # Get topic and gender from participant metadata
    topic = "General"
    gender = "unspecified"
    session_id = ctx.room.name
    
    for participant in ctx.room.remote_participants.values():
        if participant.metadata:
            try:
                metadata = json.loads(participant.metadata)
                topic = metadata.get("topic", "General")
                gender = metadata.get("gender", "unspecified")
                print(f"DEBUG: Interview topic: {topic}, gender: {gender}")
                break
            except json.JSONDecodeError:
                pass
    
    print(f"DEBUG: Starting interview on topic: {topic}, session: {session_id}")
    
    # Create emotion context for this session
    emotion_context = EmotionContext()
    
    # Create the adaptive agent
    adaptive_agent = AdaptiveInterviewerAgent(
        topic=topic,
        emotion_context=emotion_context,
        session_id=session_id
    )
    
    # Create the static agent for comparison (runs in parallel for logging)
    static_agent = StaticInterviewerAgent(
        topic=topic,
        session_id=session_id
    )
    
    # Main session uses the adaptive agent
    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="gemini-2.0-flash",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )
    
    # Static comparison session (for logging alternative responses)
    static_session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="gemini-2.0-flash",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )
    
    # Start listening for emotion updates via data channel
    @ctx.room.on("data_received")
    def on_data_received(data: rtc.DataPacket):
        print(f"DEBUG: Received data packet from {data.participant.identity if data.participant else 'unknown'}")
        try:
            payload = json.loads(data.data.decode())
            if payload.get("type") == "emotion_update":
                emotion_data = payload.get("data", {})
                emotion_context.update(
                    anxiety=emotion_data.get("anxiety", 0.5),
                    confidence=emotion_data.get("confidence", 0.5),
                    engagement=emotion_data.get("engagement", 0.5)
                )
                # Update agent instructions based on new emotion state
                adaptive_agent.update_instructions()
                
                # Log the adaptation decision
                asyncio.create_task(log_adaptation(
                    session_id=session_id,
                    emotion_state=emotion_data,
                    difficulty=emotion_context.get_difficulty_level(),
                    tone=emotion_context.get_tone()
                ))
                
                print(f"DEBUG: Emotion update - anxiety: {emotion_context.anxiety:.2f}, "
                      f"confidence: {emotion_context.confidence:.2f}, "
                      f"engagement: {emotion_context.engagement:.2f}")
                print(f"DEBUG: Adaptation - difficulty: {emotion_context.get_difficulty_level()}, "
                      f"tone: {emotion_context.get_tone()}")
        except Exception as e:
            print(f"Error processing emotion data: {e}")
    
    await session.start(
        room=ctx.room,
        agent=adaptive_agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony() if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP else noise_cancellation.BVC(),
            ),
        ),
    )
    
    await session.generate_reply(
        instructions=f"""Introduce yourself as an AI interviewer using the adaptive interview system. 
        Tell the candidate you'll be interviewing them on {topic}. 
        Mention that the system adapts to help them perform their best.
        Then ask your first question about {topic}."""
    )


async def log_adaptation(session_id: str, emotion_state: dict, difficulty: str, tone: str):
    """Log adaptation decision to the backend"""
    try:
        async with aiohttp.ClientSession() as http_session:
            await http_session.post(
                f"{API_BASE_URL}/adaptation/log",
                json={
                    "session_id": session_id,
                    "emotion_state": emotion_state,
                    "action": f"Adjusted to {difficulty} difficulty with {tone} tone",
                    "reason": f"Based on anxiety={emotion_state.get('anxiety', 0):.2f}, "
                              f"confidence={emotion_state.get('confidence', 0):.2f}, "
                              f"engagement={emotion_state.get('engagement', 0):.2f}",
                    "question_difficulty": difficulty,
                    "tone": tone
                }
            )
    except Exception as e:
        print(f"Error logging adaptation: {e}")


if __name__ == "__main__":
    agents.cli.run_app(server)