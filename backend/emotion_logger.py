"""
Emotion Logger - Handles logging of emotion data, adaptation decisions, and fairness metrics.
Stores data in local JSON files for analysis.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

# Create logs directory
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


@dataclass
class EmotionState:
    timestamp: str
    anxiety: float
    confidence: float
    engagement: float
    raw_facial: Dict[str, float]
    raw_vocal: Dict[str, float]
    fused_emotion: str


@dataclass
class AdaptationDecision:
    timestamp: str
    emotion_state: Dict
    action: str
    reason: str
    question_difficulty: str  # easy, medium, hard
    tone: str  # encouraging, neutral, challenging


@dataclass
class InterviewSession:
    session_id: str
    participant_name: str
    gender: str
    topic: str
    start_time: str
    end_time: Optional[str]
    emotion_timeline: List[Dict]
    adaptation_log: List[Dict]
    agent_responses: List[Dict]  # Both adaptive and static


class EmotionLogger:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_file = os.path.join(LOGS_DIR, f"session_{session_id}.json")
        
        # Load existing data from file if it exists, otherwise create new session
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r') as f:
                    self.session_data = json.load(f)
                print(f"DEBUG: Loaded existing session from {self.session_file}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"DEBUG: Error loading session file, creating new: {e}")
                self._create_new_session()
        else:
            self._create_new_session()
    
    def _create_new_session(self):
        """Create a new empty session data structure"""
        self.session_data = {
            "session_id": self.session_id,
            "participant_name": "",
            "gender": "",
            "topic": "",
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "emotion_timeline": [],
            "adaptation_log": [],
            "agent_responses": [],
        }
    
    def initialize_session(self, participant_name: str, gender: str, topic: str):
        """Initialize session with participant details"""
        self.session_data["participant_name"] = participant_name
        self.session_data["gender"] = gender
        self.session_data["topic"] = topic
        self._save()
    
    def log_emotion(self, emotion_state: Dict):
        """Log an emotion state to the timeline"""
        emotion_entry = {
            "timestamp": datetime.now().isoformat(),
            **emotion_state
        }
        self.session_data["emotion_timeline"].append(emotion_entry)
        self._save()
        return emotion_entry
    
    def log_adaptation(self, emotion_state: Dict, action: str, reason: str, 
                       question_difficulty: str, tone: str):
        """Log an adaptation decision"""
        adaptation_entry = {
            "timestamp": datetime.now().isoformat(),
            "emotion_state": emotion_state,
            "action": action,
            "reason": reason,
            "question_difficulty": question_difficulty,
            "tone": tone
        }
        self.session_data["adaptation_log"].append(adaptation_entry)
        self._save()
        return adaptation_entry
    
    def log_agent_response(self, candidate_message: str, adaptive_response: str, 
                           static_response: str, emotion_at_time: Dict):
        """Log both agent responses for comparison"""
        response_entry = {
            "timestamp": datetime.now().isoformat(),
            "candidate_message": candidate_message,
            "adaptive_response": adaptive_response,
            "static_response": static_response,
            "emotion_at_time": emotion_at_time
        }
        self.session_data["agent_responses"].append(response_entry)
        self._save()
        return response_entry
    
    def end_session(self):
        """Mark session as ended"""
        self.session_data["end_time"] = datetime.now().isoformat()
        self._save()
    
    def _save(self):
        """Save session data to JSON file"""
        with open(self.session_file, 'w') as f:
            json.dump(self.session_data, f, indent=2)
    
    def get_session_data(self):
        """Return current session data"""
        return self.session_data


class FairnessMetrics:
    """Calculate fairness metrics across sessions"""
    
    @staticmethod
    def load_all_sessions() -> List[Dict]:
        """Load all session files"""
        sessions = []
        for filename in os.listdir(LOGS_DIR):
            if filename.startswith("session_") and filename.endswith(".json"):
                filepath = os.path.join(LOGS_DIR, filename)
                with open(filepath, 'r') as f:
                    sessions.append(json.load(f))
        return sessions
    
    @staticmethod
    def calculate_demographic_parity() -> Dict:
        """
        Calculate question difficulty distribution by gender.
        Target: <5% gap between groups.
        """
        sessions = FairnessMetrics.load_all_sessions()
        
        # Group by gender
        gender_difficulties = defaultdict(lambda: {"easy": 0, "medium": 0, "hard": 0, "total": 0})
        
        for session in sessions:
            gender = session.get("gender", "unknown")
            for adaptation in session.get("adaptation_log", []):
                difficulty = adaptation.get("question_difficulty", "medium")
                gender_difficulties[gender][difficulty] += 1
                gender_difficulties[gender]["total"] += 1
        
        # Calculate percentages
        result = {}
        for gender, difficulties in gender_difficulties.items():
            total = difficulties["total"] or 1
            result[gender] = {
                "easy_pct": round(difficulties["easy"] / total * 100, 2),
                "medium_pct": round(difficulties["medium"] / total * 100, 2),
                "hard_pct": round(difficulties["hard"] / total * 100, 2),
                "total_questions": difficulties["total"]
            }
        
        # Calculate parity gap
        genders = list(result.keys())
        parity_gap = {}
        if len(genders) >= 2:
            for difficulty in ["easy_pct", "medium_pct", "hard_pct"]:
                values = [result[g][difficulty] for g in genders]
                parity_gap[difficulty.replace("_pct", "")] = round(max(values) - min(values), 2)
        
        return {
            "by_gender": result,
            "parity_gap": parity_gap,
            "within_threshold": all(gap < 5 for gap in parity_gap.values()) if parity_gap else True
        }
    
    @staticmethod
    def get_comparison_metrics() -> Dict:
        """Get metrics comparing adaptive vs static approaches"""
        sessions = FairnessMetrics.load_all_sessions()
        
        total_sessions = len(sessions)
        completed_sessions = sum(1 for s in sessions if s.get("end_time"))
        
        # Calculate average anxiety levels over time
        avg_anxiety_reduction = []
        for session in sessions:
            timeline = session.get("emotion_timeline", [])
            if len(timeline) >= 2:
                first_half = timeline[:len(timeline)//2]
                second_half = timeline[len(timeline)//2:]
                
                first_avg = sum(e.get("anxiety", 0) for e in first_half) / len(first_half) if first_half else 0
                second_avg = sum(e.get("anxiety", 0) for e in second_half) / len(second_half) if second_half else 0
                
                avg_anxiety_reduction.append(first_avg - second_avg)
        
        return {
            "total_sessions": total_sessions,
            "completion_rate": round(completed_sessions / total_sessions * 100, 2) if total_sessions else 0,
            "avg_anxiety_reduction": round(sum(avg_anxiety_reduction) / len(avg_anxiety_reduction), 3) if avg_anxiety_reduction else 0
        }


# Session manager - stores active sessions
active_sessions: Dict[str, EmotionLogger] = {}


def get_or_create_session(session_id: str) -> EmotionLogger:
    """Get existing session or create new one"""
    if session_id not in active_sessions:
        active_sessions[session_id] = EmotionLogger(session_id)
    return active_sessions[session_id]


def close_session(session_id: str):
    """Close and cleanup a session"""
    if session_id in active_sessions:
        active_sessions[session_id].end_session()
        del active_sessions[session_id]
