"""
Adaptive Interviewer Agent

Standalone agent class (no LiveKit dependency) that manages the interview
system prompt based on candidate emotion state. Supports dynamic adaptation
of question difficulty and interviewer tone.
"""

import logging
from typing import Optional

logger = logging.getLogger("adaptive_agent")


class EmotionContext:
    """Holds current emotion state for the interview."""

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
        """Determine question difficulty based on emotions."""
        if self.anxiety > 0.7:
            return "easy"
        elif self.confidence > 0.7 and self.anxiety < 0.4:
            return "hard"
        else:
            return "medium"

    def get_tone(self) -> str:
        """Determine interviewer tone based on emotions."""
        if self.anxiety > 0.7:
            return "encouraging"
        elif self.confidence > 0.7:
            return "challenging"
        elif self.engagement < 0.3:
            return "engaging"
        else:
            return "neutral"


    def to_dict(self) -> dict:
        """Return current state as a dictionary."""
        return {
            "anxiety": self.anxiety,
            "confidence": self.confidence,
            "engagement": self.engagement,
            "difficulty": self.get_difficulty_level(),
            "tone": self.get_tone(),
        }


class AdaptiveInterviewerAgent:
    """Interviewer agent that adapts based on candidate emotions.
    
    This is a standalone class - no LiveKit dependency. It generates
    the system prompt for the Gemini LLM based on the current emotion context.
    """

    def __init__(self, topic: str, session_id: str):
        self.topic = topic
        self.session_id = session_id
        self.emotion_context = EmotionContext()
        self._system_prompt = self._generate_system_prompt()

    def _generate_system_prompt(self) -> str:
        """Generate the full system prompt based on current emotion context."""
        difficulty = self.emotion_context.get_difficulty_level()
        tone = self.emotion_context.get_tone()
        anxiety = self.emotion_context.anxiety
        confidence = self.emotion_context.confidence
        engagement = self.emotion_context.engagement

        return f"""You are a professional technical interviewer in a live interview on {self.topic}.

CANDIDATE EMOTIONAL STATE (Real-time tracking from face/voice analysis):
- Anxiety: {anxiety:.0%}
- Confidence: {confidence:.0%}
- Engagement: {engagement:.0%}

EMOTIONAL ADAPTATION RULES:
You must organically adapt your response to the candidate's real-time emotional state:
- If Anxiety is high (>60%), start by calmly reassuring them (e.g., "Take your time", "Deep breath, you're doing fine") and ask a slightly simpler question to build momentum.
- If Confidence is high (>70%), acknowledge their strong answer ("Great point") and push them with a harder, deeper follow-up question.
- If Engagement is low (<40%), change your approach to re-engage them (e.g., "Let's try a different angle" or "Imagine a scenario where...").
Do this naturally like a human interviewer. Do not sound robotic.

RESPONSE FORMAT (STRICT):
- Maximum 1-2 short sentences per response. 
- Ask exactly ONE question per turn.
- Feedback is ONE brief sentence, then your question.
- NEVER give long explanations, lists, or lectures.
- Speak like a real person in conversation, not a textbook.

INTERVIEW RULES:
- Adapt difficulty based on emotional state above.
- Probe deeper when answers are shallow.
- No emojis, no formatting, no filler.
- Focus on {self.topic} real-world applications.
"""

    def get_opening_prompt(self) -> str:
        """Generate the opening message prompt for the interviewer."""
        return (
            f"Briefly introduce yourself in one sentence, then ask your first question about {self.topic}. "
            f"Keep it to 2 sentences total."
        )

    def update_emotions(self, anxiety: float, confidence: float, engagement: float):
        """Update emotion context and regenerate system prompt."""
        self.emotion_context.update(anxiety, confidence, engagement)
        self._system_prompt = self._generate_system_prompt()
        logger.debug(
            f"Agent emotions updated - anxiety: {anxiety:.2f}, "
            f"confidence: {confidence:.2f}, engagement: {engagement:.2f}, "
            f"difficulty: {self.emotion_context.get_difficulty_level()}, "
            f"tone: {self.emotion_context.get_tone()}"
        )

    @property
    def system_prompt(self) -> str:
        return self._system_prompt
