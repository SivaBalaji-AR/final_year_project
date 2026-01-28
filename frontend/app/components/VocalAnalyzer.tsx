"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export interface VocalFeatures {
    pitch: number;        // Average pitch (0-1 normalized)
    pitchVariation: number; // How much pitch varies
    volume: number;       // Average volume (0-1)
    speakingRate: number; // Derived from silence ratio
    stress: number;       // Calculated stress indicator
}

export interface VocalEmotions {
    anxiety: number;
    confidence: number;
    engagement: number;
}

interface VocalAnalyzerProps {
    audioStream: MediaStream | null;
    onVocalUpdate: (features: VocalFeatures, emotions: VocalEmotions) => void;
    isActive: boolean;
    showUI?: boolean; // Whether to show visual UI (default: true)
}

// Map vocal features to interview emotions
function mapToVocalEmotions(features: VocalFeatures): VocalEmotions {
    // High pitch variation + low volume indicates anxiety
    const anxiety = Math.min(1,
        features.pitchVariation * 0.4 +
        (1 - features.volume) * 0.3 +
        features.stress * 0.3
    );

    // Steady pitch + good volume indicates confidence
    const confidence = Math.min(1,
        (1 - features.pitchVariation) * 0.3 +
        features.volume * 0.4 +
        features.speakingRate * 0.3
    );

    // Higher speaking rate and volume indicates engagement
    const engagement = Math.min(1,
        features.speakingRate * 0.5 +
        features.volume * 0.3 +
        features.pitchVariation * 0.2
    );

    return {
        anxiety: Math.round(anxiety * 100) / 100,
        confidence: Math.round(confidence * 100) / 100,
        engagement: Math.round(engagement * 100) / 100,
    };
}

export default function VocalAnalyzer({
    audioStream,
    onVocalUpdate,
    isActive,
    showUI = true,
}: VocalAnalyzerProps) {
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyzerRef = useRef<AnalyserNode | null>(null);
    const [currentFeatures, setCurrentFeatures] = useState<VocalFeatures | null>(null);
    const animationFrameRef = useRef<number | null>(null);

    // Store recent values for averaging
    const recentPitches = useRef<number[]>([]);
    const recentVolumes = useRef<number[]>([]);
    const silenceFrames = useRef(0);
    const totalFrames = useRef(0);

    const analyze = useCallback(() => {
        if (!analyzerRef.current || !isActive) return;

        const analyzer = analyzerRef.current;
        const bufferLength = analyzer.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        const timeData = new Uint8Array(bufferLength);

        analyzer.getByteFrequencyData(dataArray);
        analyzer.getByteTimeDomainData(timeData);

        // Calculate volume (RMS)
        let sum = 0;
        for (let i = 0; i < timeData.length; i++) {
            const normalized = (timeData[i] - 128) / 128;
            sum += normalized * normalized;
        }
        const rms = Math.sqrt(sum / timeData.length);
        const volume = Math.min(1, rms * 3); // Scale up for visibility

        // Track silence vs speaking
        totalFrames.current++;
        if (volume < 0.05) {
            silenceFrames.current++;
        }

        // Estimate pitch from frequency data
        let maxIndex = 0;
        let maxValue = 0;
        for (let i = 0; i < bufferLength; i++) {
            if (dataArray[i] > maxValue) {
                maxValue = dataArray[i];
                maxIndex = i;
            }
        }

        // Convert to normalized pitch (0-1)
        const pitch = maxIndex / bufferLength;

        // Track recent values
        recentPitches.current.push(pitch);
        recentVolumes.current.push(volume);

        // Keep only last 30 samples (~1 second at 30fps)
        if (recentPitches.current.length > 30) {
            recentPitches.current.shift();
            recentVolumes.current.shift();
        }

        // Calculate features every 500ms (15 frames at 30fps)
        if (totalFrames.current % 15 === 0 && recentPitches.current.length >= 10) {
            const avgPitch = recentPitches.current.reduce((a, b) => a + b, 0) / recentPitches.current.length;
            const avgVolume = recentVolumes.current.reduce((a, b) => a + b, 0) / recentVolumes.current.length;

            // Pitch variation (standard deviation)
            const pitchVariance = recentPitches.current.reduce((acc, p) => acc + Math.pow(p - avgPitch, 2), 0) / recentPitches.current.length;
            const pitchVariation = Math.min(1, Math.sqrt(pitchVariance) * 5);

            // Speaking rate (inverse of silence ratio)
            const speakingRate = 1 - (silenceFrames.current / totalFrames.current);

            // Stress indicator (combination of high pitch + variation + low volume)
            const stress = Math.min(1,
                avgPitch * 0.3 +
                pitchVariation * 0.4 +
                (1 - avgVolume) * 0.3
            );

            const features: VocalFeatures = {
                pitch: Math.round(avgPitch * 100) / 100,
                pitchVariation: Math.round(pitchVariation * 100) / 100,
                volume: Math.round(avgVolume * 100) / 100,
                speakingRate: Math.round(speakingRate * 100) / 100,
                stress: Math.round(stress * 100) / 100,
            };

            setCurrentFeatures(features);
            const emotions = mapToVocalEmotions(features);
            onVocalUpdate(features, emotions);
        }

        animationFrameRef.current = requestAnimationFrame(analyze);
    }, [isActive, onVocalUpdate]);

    // Setup audio analyzer
    useEffect(() => {
        if (!audioStream || !isActive) return;

        const setupAudio = async () => {
            try {
                audioContextRef.current = new AudioContext();
                analyzerRef.current = audioContextRef.current.createAnalyser();
                analyzerRef.current.fftSize = 2048;

                const source = audioContextRef.current.createMediaStreamSource(audioStream);
                source.connect(analyzerRef.current);

                // Reset counters
                silenceFrames.current = 0;
                totalFrames.current = 0;
                recentPitches.current = [];
                recentVolumes.current = [];

                // Start analysis loop
                animationFrameRef.current = requestAnimationFrame(analyze);
            } catch (err) {
                console.error("Error setting up audio analyzer:", err);
            }
        };

        setupAudio();

        return () => {
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
            if (audioContextRef.current) {
                audioContextRef.current.close();
            }
        };
    }, [audioStream, isActive, analyze]);

    // If showUI is false, don't render anything visual
    if (!showUI) {
        return null;
    }

    return (
        <div className="space-y-2">
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isActive && audioStream ? "bg-blue-500 animate-pulse" : "bg-gray-500"}`}></div>
                <span className="text-xs text-gray-400">
                    {isActive && audioStream ? "Analyzing voice" : "Voice analysis paused"}
                </span>
            </div>

            {currentFeatures && (
                <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="flex flex-col">
                        <span className="text-gray-500">Volume</span>
                        <div className="h-1 bg-gray-700 rounded overflow-hidden">
                            <div
                                className="h-full bg-blue-500 transition-all duration-300"
                                style={{ width: `${currentFeatures.volume * 100}%` }}
                            ></div>
                        </div>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-gray-500">Pitch Var</span>
                        <div className="h-1 bg-gray-700 rounded overflow-hidden">
                            <div
                                className="h-full bg-blue-500 transition-all duration-300"
                                style={{ width: `${currentFeatures.pitchVariation * 100}%` }}
                            ></div>
                        </div>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-gray-500">Speaking</span>
                        <div className="h-1 bg-gray-700 rounded overflow-hidden">
                            <div
                                className="h-full bg-blue-500 transition-all duration-300"
                                style={{ width: `${currentFeatures.speakingRate * 100}%` }}
                            ></div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
