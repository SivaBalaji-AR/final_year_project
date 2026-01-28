"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as faceapi from "face-api.js";

export interface FacialEmotions {
    angry: number;
    disgusted: number;
    fearful: number;
    happy: number;
    neutral: number;
    sad: number;
    surprised: number;
}

export interface InterviewEmotions {
    anxiety: number;
    confidence: number;
    engagement: number;
}

interface EmotionDetectorProps {
    videoElement: HTMLVideoElement | null;
    onEmotionUpdate: (facial: FacialEmotions, interview: InterviewEmotions) => void;
    isActive: boolean;
    showUI?: boolean;
}

// Smoothing factor for temporal averaging (0-1, higher = more smoothing)
// Reduced for more responsive detection
const SMOOTHING_FACTOR = 0.3;
const HISTORY_SIZE = 3; // Number of frames to average

// Improved mapping with better weights for interview context
function mapToInterviewEmotions(facial: FacialEmotions): InterviewEmotions {
    // Anxiety indicators: fearful, sad, disgusted, angry (negative emotions)
    // Higher weight on fearful as it's most directly related to anxiety
    const anxiety = Math.min(1,
        facial.fearful * 2.0 +
        facial.sad * 1.2 +
        facial.angry * 0.5 +
        facial.disgusted * 0.3
    );

    // Confidence indicators: happy, neutral (calm/composed), slightly surprised (alert)
    // Reduce influence of pure neutral as it might just mean no expression detected
    const confidence = Math.min(1,
        facial.happy * 1.5 +
        facial.neutral * 0.4 +
        facial.surprised * 0.3 +
        (1 - anxiety) * 0.3 // Less anxiety = more confident
    );

    // Engagement: expressive face (not neutral), happy, surprised
    // Being neutral/unexpressive often indicates disengagement
    const expressiveness = 1 - facial.neutral;
    const engagement = Math.min(1,
        expressiveness * 0.4 +
        facial.happy * 0.4 +
        facial.surprised * 0.3 +
        Math.abs(facial.angry + facial.disgusted) * 0.1 // Even negative expressions show engagement
    );

    return {
        anxiety: Math.round(anxiety * 100) / 100,
        confidence: Math.round(confidence * 100) / 100,
        engagement: Math.round(engagement * 100) / 100,
    };
}

// Smooth emotions using exponential moving average
function smoothEmotions(
    current: FacialEmotions,
    previous: FacialEmotions | null
): FacialEmotions {
    if (!previous) return current;

    const smooth = (curr: number, prev: number) =>
        prev * SMOOTHING_FACTOR + curr * (1 - SMOOTHING_FACTOR);

    return {
        angry: smooth(current.angry, previous.angry),
        disgusted: smooth(current.disgusted, previous.disgusted),
        fearful: smooth(current.fearful, previous.fearful),
        happy: smooth(current.happy, previous.happy),
        neutral: smooth(current.neutral, previous.neutral),
        sad: smooth(current.sad, previous.sad),
        surprised: smooth(current.surprised, previous.surprised),
    };
}

// Average multiple emotion samples
function averageEmotions(history: FacialEmotions[]): FacialEmotions {
    if (history.length === 0) {
        return { angry: 0, disgusted: 0, fearful: 0, happy: 0, neutral: 1, sad: 0, surprised: 0 };
    }

    const sum = history.reduce((acc, e) => ({
        angry: acc.angry + e.angry,
        disgusted: acc.disgusted + e.disgusted,
        fearful: acc.fearful + e.fearful,
        happy: acc.happy + e.happy,
        neutral: acc.neutral + e.neutral,
        sad: acc.sad + e.sad,
        surprised: acc.surprised + e.surprised,
    }), { angry: 0, disgusted: 0, fearful: 0, happy: 0, neutral: 0, sad: 0, surprised: 0 });

    const len = history.length;
    return {
        angry: sum.angry / len,
        disgusted: sum.disgusted / len,
        fearful: sum.fearful / len,
        happy: sum.happy / len,
        neutral: sum.neutral / len,
        sad: sum.sad / len,
        surprised: sum.surprised / len,
    };
}

export default function EmotionDetector({
    videoElement,
    onEmotionUpdate,
    isActive,
    showUI = true,
}: EmotionDetectorProps) {
    const [isModelLoaded, setIsModelLoaded] = useState(false);
    const [currentEmotions, setCurrentEmotions] = useState<FacialEmotions | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [detectionCount, setDetectionCount] = useState(0);
    const [missedDetections, setMissedDetections] = useState(0);

    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const previousEmotionsRef = useRef<FacialEmotions | null>(null);
    const emotionHistoryRef = useRef<FacialEmotions[]>([]);

    // Load face-api models - use SSD MobileNet for better accuracy
    useEffect(() => {
        const loadModels = async () => {
            try {
                const MODEL_URL = "/models";

                await Promise.all([
                    // Try SSD MobileNet first (more accurate), fallback to TinyFaceDetector
                    faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL).catch(() =>
                        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL)
                    ),
                    faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL),
                ]);

                setIsModelLoaded(true);
                console.log("Face-api models loaded successfully (enhanced)");
            } catch (err) {
                console.error("Error loading face-api models:", err);
                setError("Failed to load emotion detection models");
            }
        };

        loadModels();
    }, []);

    // Detect emotions from video with improved accuracy
    const detectEmotions = useCallback(async () => {
        if (!videoElement || !isModelLoaded || !isActive) return;

        try {
            // Use SSD MobileNet if available, otherwise TinyFaceDetector
            let detections;

            if (faceapi.nets.ssdMobilenetv1.isLoaded) {
                detections = await faceapi
                    .detectSingleFace(videoElement, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.5 }))
                    .withFaceExpressions();
            } else {
                detections = await faceapi
                    .detectSingleFace(videoElement, new faceapi.TinyFaceDetectorOptions({ scoreThreshold: 0.5 }))
                    .withFaceExpressions();
            }

            if (detections) {
                setDetectionCount(c => c + 1);
                const expressions = detections.expressions;

                const rawEmotions: FacialEmotions = {
                    angry: expressions.angry,
                    disgusted: expressions.disgusted,
                    fearful: expressions.fearful,
                    happy: expressions.happy,
                    neutral: expressions.neutral,
                    sad: expressions.sad,
                    surprised: expressions.surprised,
                };

                // Apply temporal smoothing
                const smoothedEmotions = smoothEmotions(rawEmotions, previousEmotionsRef.current);
                previousEmotionsRef.current = smoothedEmotions;

                // Add to history for averaging
                emotionHistoryRef.current.push(smoothedEmotions);
                if (emotionHistoryRef.current.length > HISTORY_SIZE) {
                    emotionHistoryRef.current.shift();
                }

                // Use averaged emotions for final output
                const averagedEmotions = averageEmotions(emotionHistoryRef.current);

                setCurrentEmotions(averagedEmotions);
                const interview = mapToInterviewEmotions(averagedEmotions);
                onEmotionUpdate(averagedEmotions, interview);
            } else {
                // No face detected - increment missed count
                setMissedDetections(m => m + 1);

                // If we have previous emotions, decay them slowly towards neutral
                if (previousEmotionsRef.current && emotionHistoryRef.current.length > 0) {
                    const lastEmotion = emotionHistoryRef.current[emotionHistoryRef.current.length - 1];
                    const decayed: FacialEmotions = {
                        ...lastEmotion,
                        neutral: Math.min(1, lastEmotion.neutral * 1.05), // Slowly increase neutral
                    };
                    setCurrentEmotions(decayed);
                    const interview = mapToInterviewEmotions(decayed);
                    onEmotionUpdate(decayed, interview);
                }
            }
        } catch (err) {
            console.error("Error detecting emotions:", err);
        }
    }, [videoElement, isModelLoaded, isActive, onEmotionUpdate]);

    // Run detection at intervals (slightly faster for smoother experience)
    useEffect(() => {
        if (isActive && isModelLoaded && videoElement) {
            intervalRef.current = setInterval(detectEmotions, 400); // 400ms = 2.5 fps
        }

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [isActive, isModelLoaded, videoElement, detectEmotions]);

    // If showUI is false, don't render anything visual
    if (!showUI) {
        return null;
    }

    if (error) {
        return (
            <div className="text-red-400 text-sm p-2 bg-red-900/20 rounded">
                {error}
            </div>
        );
    }

    if (!isModelLoaded) {
        return (
            <div className="text-gray-400 text-sm p-2 flex items-center gap-2">
                <div className="animate-spin w-4 h-4 border-2 border-purple-500 border-t-transparent rounded-full"></div>
                Loading emotion detection...
            </div>
        );
    }

    const detectionRate = detectionCount > 0
        ? Math.round((detectionCount / (detectionCount + missedDetections)) * 100)
        : 0;

    return (
        <div className="space-y-2">
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isActive ? "bg-green-500 animate-pulse" : "bg-gray-500"}`}></div>
                <span className="text-xs text-gray-400">
                    {isActive ? `Detecting (${detectionRate}% success)` : "Detection paused"}
                </span>
            </div>

            {currentEmotions && (
                <div className="grid grid-cols-4 gap-1 text-xs">
                    {Object.entries(currentEmotions).map(([emotion, value]) => (
                        <div key={emotion} className="flex flex-col">
                            <span className="text-gray-500 capitalize">{emotion.slice(0, 3)}</span>
                            <div className="h-1 bg-gray-700 rounded overflow-hidden">
                                <div
                                    className="h-full bg-purple-500 transition-all duration-300"
                                    style={{ width: `${value * 100}%` }}
                                ></div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
