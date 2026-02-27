"""
Server-Side Vocal Analysis.

Analyzes PCM audio chunks to extract vocal features:
- Pitch (fundamental frequency via autocorrelation)
- Volume (RMS energy)
- Speaking rate (zero-crossing rate as proxy)
- Stress indicators
Maps features to interview emotions.
"""

import logging
import math
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger("vocal_analyzer")

SAMPLE_RATE = 16000


class VocalAnalyzer:
    """Analyzes audio features from PCM chunks."""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._pitch_history: List[float] = []
        self._volume_history: List[float] = []
        self._zcr_history: List[float] = []
        self._chunk_count = 0
        self._silence_chunks = 0
        self._speaking_chunks = 0

    def analyze_chunk(self, pcm_bytes: bytes) -> Optional[Dict]:
        """Analyze a PCM audio chunk.
        
        Args:
            pcm_bytes: Raw PCM 16-bit signed LE mono audio.
            
        Returns:
            Dict with vocal features and emotions, or None on error.
        """
        try:
            # Convert PCM bytes to float32 numpy array
            int16_data = np.frombuffer(pcm_bytes, dtype=np.int16)
            if len(int16_data) < 256:
                return None

            float_data = int16_data.astype(np.float32) / 32768.0
            self._chunk_count += 1

            # Calculate features
            rms = self._rms_energy(float_data)
            zcr = self._zero_crossing_rate(float_data)
            pitch = self._estimate_pitch(float_data)

            # Track silence vs speaking
            is_speaking = rms > 0.02
            if is_speaking:
                self._speaking_chunks += 1
            else:
                self._silence_chunks += 1

            # Update histories
            self._pitch_history.append(pitch if pitch > 0 else 0)
            self._volume_history.append(rms)
            self._zcr_history.append(zcr)

            # Keep last 100 chunks (~25 seconds at 4096 samples/chunk)
            for hist in [self._pitch_history, self._volume_history, self._zcr_history]:
                if len(hist) > 100:
                    del hist[:-100]

            # Calculate derived features
            volume_variance = float(np.std(self._volume_history[-20:])) if len(self._volume_history) > 5 else 0
            pitch_variance = float(np.std([p for p in self._pitch_history[-20:] if p > 0])) if sum(1 for p in self._pitch_history[-20:] if p > 0) > 3 else 0
            avg_pitch = float(np.mean([p for p in self._pitch_history[-20:] if p > 0])) if any(p > 0 for p in self._pitch_history[-20:]) else 0
            speaking_ratio = self._speaking_chunks / max(self._speaking_chunks + self._silence_chunks, 1)

            features = {
                "pitch": round(pitch, 1),
                "avg_pitch": round(avg_pitch, 1),
                "pitch_variance": round(pitch_variance, 1),
                "volume": round(rms, 4),
                "volume_variance": round(volume_variance, 4),
                "zero_crossing_rate": round(zcr, 4),
                "is_speaking": is_speaking,
                "speaking_ratio": round(speaking_ratio, 3),
            }

            # Map to emotions
            emotions = self._map_to_emotions(features)

            return {
                "features": features,
                "emotions": emotions,
                "chunk_number": self._chunk_count,
            }

        except Exception as e:
            logger.error(f"Error analyzing audio chunk: {e}")
            return None

    def _rms_energy(self, data: np.ndarray) -> float:
        """Root mean square energy."""
        return float(np.sqrt(np.mean(data ** 2)))

    def _zero_crossing_rate(self, data: np.ndarray) -> float:
        """Zero crossing rate - proxy for speaking rate / fricatives."""
        crossings = np.sum(np.abs(np.diff(np.sign(data)))) / 2
        return float(crossings / len(data))

    def _estimate_pitch(self, data: np.ndarray) -> float:
        """Estimate fundamental frequency using autocorrelation."""
        # Only estimate if signal is strong enough
        if self._rms_energy(data) < 0.02:
            return 0.0

        # Autocorrelation method
        corr = np.correlate(data, data, mode='full')
        corr = corr[len(corr) // 2:]

        # Find first peak after initial decline
        # Limit search to human voice range (80-400 Hz)
        min_lag = self.sample_rate // 400  # ~40 samples
        max_lag = self.sample_rate // 80   # ~200 samples

        if max_lag >= len(corr):
            max_lag = len(corr) - 1

        if min_lag >= max_lag:
            return 0.0

        segment = corr[min_lag:max_lag]
        if len(segment) == 0:
            return 0.0

        peak_idx = int(np.argmax(segment)) + min_lag

        if peak_idx > 0 and corr[peak_idx] > 0.1 * corr[0]:
            return float(self.sample_rate / peak_idx)

        return 0.0

    def _map_to_emotions(self, features: Dict) -> Dict:
        """Map vocal features to interview emotions."""
        # Anxiety: high pitch, high pitch variance, low volume
        anxiety = 0.0
        if features["avg_pitch"] > 200:
            anxiety += 0.3
        if features["pitch_variance"] > 30:
            anxiety += 0.3
        if features["volume"] < 0.03 and features["is_speaking"]:
            anxiety += 0.2
        if features["volume_variance"] > 0.02:
            anxiety += 0.2
        anxiety = min(anxiety, 1.0)

        # Confidence: steady pitch, good volume, moderate speaking rate
        confidence = 0.3
        if features["avg_pitch"] > 0 and features["pitch_variance"] < 20:
            confidence += 0.25
        if features["volume"] > 0.05:
            confidence += 0.2
        if 0.3 < features["speaking_ratio"] < 0.8:
            confidence += 0.25
        confidence = min(confidence, 1.0)

        # Engagement: active speaking, varied pitch (expressive)
        engagement = 0.2
        if features["is_speaking"]:
            engagement += 0.3
        if features["pitch_variance"] > 10:
            engagement += 0.2
        if features["speaking_ratio"] > 0.3:
            engagement += 0.3
        engagement = min(engagement, 1.0)

        return {
            "anxiety": round(anxiety, 3),
            "confidence": round(confidence, 3),
            "engagement": round(engagement, 3),
        }

    def get_summary(self) -> Dict:
        """Get overall vocal analysis summary."""
        return {
            "total_chunks": self._chunk_count,
            "speaking_ratio": round(
                self._speaking_chunks / max(self._speaking_chunks + self._silence_chunks, 1), 3
            ),
            "avg_pitch": round(
                float(np.mean([p for p in self._pitch_history if p > 0])) if any(p > 0 for p in self._pitch_history) else 0, 1
            ),
            "avg_volume": round(
                float(np.mean(self._volume_history)) if self._volume_history else 0, 4
            ),
        }
