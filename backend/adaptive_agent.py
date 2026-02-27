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

    def get_adaptation_instructions(self) -> str:
        """Generate adaptation instructions for the LLM."""
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
        adaptation = self.emotion_context.get_adaptation_instructions()
        difficulty = self.emotion_context.get_difficulty_level()
        tone = self.emotion_context.get_tone()

        return f"""You are a professional technical interviewer conducting a real interview.
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

    def get_opening_prompt(self) -> str:
        """Generate the opening message prompt for the interviewer."""
        return (
            f"Introduce yourself as an AI interviewer using the adaptive interview system. "
            f"Tell the candidate you'll be interviewing them on {self.topic}. "
            f"Mention that the system adapts to help them perform their best. "
            f"Then ask your first question about {self.topic}."
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
