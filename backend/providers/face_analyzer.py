"""
Server-Side Face Analysis using MediaPipe FaceLandmarker (Tasks API).

Processes JPEG video frames and extracts:
- 478 3D face landmarks (FaceLandmarker returns 478 including iris landmarks)
- Interview emotions (anxiety, confidence, engagement)
- Micro-expressions (blink rate, eyebrow raise, lip tension, jaw clench)
"""

import os
import logging
import math
from typing import Optional, Dict, List, Tuple

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

logger = logging.getLogger("face_analyzer")

# Path to the downloaded .task model file
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "face_landmarker.task")

# Key landmark indices (MediaPipe canonical face mesh)
LEFT_EYE_TOP = 159
LEFT_EYE_BOTTOM = 145
RIGHT_EYE_TOP = 386
RIGHT_EYE_BOTTOM = 374
LEFT_EYEBROW_INNER = 107
RIGHT_EYEBROW_INNER = 336
UPPER_LIP = 13
LOWER_LIP = 14
LEFT_MOUTH_CORNER = 61
RIGHT_MOUTH_CORNER = 291
CHIN = 152
FOREHEAD = 10
JAW_LEFT = 172
JAW_RIGHT = 397


class FaceAnalyzer:
    """Analyzes face frames using MediaPipe FaceLandmarker Tasks API."""

    def __init__(self):
        abs_model_path = os.path.abspath(MODEL_PATH)
        if not os.path.exists(abs_model_path):
            logger.warning(f"FaceLandmarker model not found at {abs_model_path}. Face analysis disabled.")
            self._landmarker = None
        else:
            options = FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=abs_model_path),
                running_mode=RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_face_blendshapes=False,
            )
            self._landmarker = FaceLandmarker.create_from_options(options)
            logger.info("FaceLandmarker initialized successfully")

        # State for temporal analysis
        self._blink_history: List[bool] = []
        self._eyebrow_history: List[float] = []
        self._mouth_history: List[float] = []
        self._frame_count = 0

    def analyze_frame(self, jpeg_bytes: bytes) -> Optional[Dict]:
        """Analyze a single JPEG frame.
        
        Returns dict with landmarks, emotions, and micro-expressions, or None.
        """
        if not self._landmarker:
            return None

        try:
            # Decode JPEG
            nparr = np.frombuffer(jpeg_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return None

            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, _ = rgb_frame.shape

            # Create MediaPipe Image
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Detect
            result = self._landmarker.detect(mp_image)

            if not result.face_landmarks or len(result.face_landmarks) == 0:
                return None

            face_lms = result.face_landmarks[0]  # First face
            self._frame_count += 1

            # Extract normalized landmarks (0-1 range)
            landmarks = []
            for lm in face_lms:
                landmarks.append({
                    "x": round(lm.x, 4),
                    "y": round(lm.y, 4),
                    "z": round(lm.z, 4),
                })

            # Calculate micro-expressions
            micro = self._analyze_micro_expressions(face_lms, w, h)

            # Map to interview emotions
            emotions = self._map_to_emotions(micro)

            return {
                "landmarks": landmarks,
                "landmark_count": len(landmarks),
                "micro_expressions": micro,
                "emotions": emotions,
                "frame_number": self._frame_count,
            }

        except Exception as e:
            logger.error(f"Error analyzing frame: {e}")
            return None

    def _get_point(self, landmarks, idx, w, h) -> Tuple[float, float]:
        """Get pixel coordinates for a landmark index."""
        lm = landmarks[idx]
        return (lm.x * w, lm.y * h)

    def _distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Euclidean distance between two points."""
        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

    def _analyze_micro_expressions(self, landmarks, w: int, h: int) -> Dict:
        """Extract micro-expression features from landmarks."""
        # Eye Aspect Ratio (EAR) for blink detection
        left_eye_top = self._get_point(landmarks, LEFT_EYE_TOP, w, h)
        left_eye_bottom = self._get_point(landmarks, LEFT_EYE_BOTTOM, w, h)
        right_eye_top = self._get_point(landmarks, RIGHT_EYE_TOP, w, h)
        right_eye_bottom = self._get_point(landmarks, RIGHT_EYE_BOTTOM, w, h)

        left_ear = self._distance(left_eye_top, left_eye_bottom)
        right_ear = self._distance(right_eye_top, right_eye_bottom)
        avg_ear = (left_ear + right_ear) / 2

        # Normalize EAR by face height
        face_height = self._distance(
            self._get_point(landmarks, FOREHEAD, w, h),
            self._get_point(landmarks, CHIN, w, h)
        )
        normalized_ear = avg_ear / max(face_height, 1) * 10

        # Blink detection
        is_blinking = normalized_ear < 0.2
        self._blink_history.append(is_blinking)
        if len(self._blink_history) > 60:
            self._blink_history = self._blink_history[-60:]
        blink_rate = sum(self._blink_history) / max(len(self._blink_history), 1)

        # Eyebrow position
        left_brow = self._get_point(landmarks, LEFT_EYEBROW_INNER, w, h)
        right_brow = self._get_point(landmarks, RIGHT_EYEBROW_INNER, w, h)
        left_eye = self._get_point(landmarks, LEFT_EYE_TOP, w, h)
        right_eye = self._get_point(landmarks, RIGHT_EYE_TOP, w, h)

        brow_eye_dist = (
            self._distance(left_brow, left_eye) +
            self._distance(right_brow, right_eye)
        ) / 2
        eyebrow_raise = brow_eye_dist / max(face_height, 1) * 10
        self._eyebrow_history.append(eyebrow_raise)
        if len(self._eyebrow_history) > 30:
            self._eyebrow_history = self._eyebrow_history[-30:]

        # Mouth analysis
        upper_lip = self._get_point(landmarks, UPPER_LIP, w, h)
        lower_lip = self._get_point(landmarks, LOWER_LIP, w, h)
        left_corner = self._get_point(landmarks, LEFT_MOUTH_CORNER, w, h)
        right_corner = self._get_point(landmarks, RIGHT_MOUTH_CORNER, w, h)

        mouth_open = self._distance(upper_lip, lower_lip) / max(face_height, 1) * 10
        mouth_width = self._distance(left_corner, right_corner) / max(face_height, 1) * 10
        self._mouth_history.append(mouth_open)
        if len(self._mouth_history) > 30:
            self._mouth_history = self._mouth_history[-30:]

        # Jaw tension
        jaw_l = self._get_point(landmarks, JAW_LEFT, w, h)
        jaw_r = self._get_point(landmarks, JAW_RIGHT, w, h)
        jaw_clench = self._distance(jaw_l, jaw_r) / max(face_height, 1)

        return {
            "eye_aspect_ratio": round(normalized_ear, 3),
            "is_blinking": is_blinking,
            "blink_rate": round(blink_rate, 3),
            "eyebrow_raise": round(eyebrow_raise, 3),
            "mouth_open": round(mouth_open, 3),
            "mouth_width": round(mouth_width, 3),
            "jaw_clench": round(jaw_clench, 3),
        }

    def _map_to_emotions(self, micro: Dict) -> Dict:
        """Map micro-expressions to interview emotions."""
        # Anxiety: high blink rate, raised eyebrows, tight mouth
        anxiety = 0.0
        anxiety += min(micro["blink_rate"] * 2, 0.4)
        anxiety += min(max(micro["eyebrow_raise"] - 0.3, 0) * 2, 0.3)
        anxiety += min(max(0.3 - micro["mouth_open"], 0) * 3, 0.3)
        anxiety = min(anxiety, 1.0)

        # Confidence: relaxed face, steady gaze, natural mouth
        confidence = 0.5
        if micro["blink_rate"] < 0.15:
            confidence += 0.2
        if 0.2 < micro["eyebrow_raise"] < 0.5:
            confidence += 0.15
        if micro["mouth_width"] > 0.3:
            confidence += 0.15
        confidence = min(confidence, 1.0)

        # Engagement: varied expressions, mouth movement
        engagement = 0.3
        mouth_variance = float(np.std(self._mouth_history)) if len(self._mouth_history) > 5 else 0
        engagement += min(mouth_variance * 10, 0.3)
        brow_variance = float(np.std(self._eyebrow_history)) if len(self._eyebrow_history) > 5 else 0
        engagement += min(brow_variance * 5, 0.2)
        if micro["mouth_open"] > 0.15:
            engagement += 0.2
        engagement = min(engagement, 1.0)

        return {
            "anxiety": round(anxiety, 3),
            "confidence": round(confidence, 3),
            "engagement": round(engagement, 3),
        }

    def close(self):
        """Release resources."""
        if self._landmarker:
            self._landmarker.close()
