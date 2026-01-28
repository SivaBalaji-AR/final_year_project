"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  StartAudio,
  VideoConference,
  useLocalParticipant,
  useTracks,
} from "@livekit/components-react";
import { Track } from "livekit-client";

import { useState, useCallback, useRef, useEffect } from "react";
import "@livekit/components-styles";

import EmotionDetector, { FacialEmotions, InterviewEmotions } from "./components/EmotionDetector";
import VocalAnalyzer, { VocalFeatures, VocalEmotions } from "./components/VocalAnalyzer";
import EmotionDashboard, { EmotionDataPoint, AdaptationDecision } from "./components/EmotionDashboard";
import FairnessPanel from "./components/FairnessPanel";

// Interview topics
const TOPICS = [
  "React & Frontend Development",
  "Node.js & Backend Development",
  "Python & Data Science",
  "System Design",
  "Data Structures & Algorithms",
  "DevOps & Cloud",
  "Machine Learning",
  "Full Stack Development",
];

const GENDERS = ["Male", "Female", "Non-binary", "Prefer not to say"];

// Multimodal fusion weights
const AUDIO_WEIGHT = 0.6;
const VISUAL_WEIGHT = 0.4;

interface FusedEmotions {
  anxiety: number;
  confidence: number;
  engagement: number;
}

export default function Home() {
  const [stage, setStage] = useState<"setup" | "interview">("setup");
  const [userName, setUserName] = useState("");
  const [gender, setGender] = useState(GENDERS[0]);
  const [topic, setTopic] = useState(TOPICS[0]);
  const [token, setToken] = useState<string>("");
  const [url, setUrl] = useState<string>("");
  const [sessionId, setSessionId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [showDashboard, setShowDashboard] = useState(true);
  const [showFairness, setShowFairness] = useState(false);

  // Emotion state
  const [facialEmotions, setFacialEmotions] = useState<InterviewEmotions | null>(null);
  const [vocalEmotions, setVocalEmotions] = useState<VocalEmotions | null>(null);
  const [fusedEmotions, setFusedEmotions] = useState<FusedEmotions | null>(null);
  const [emotionHistory, setEmotionHistory] = useState<EmotionDataPoint[]>([]);
  const [adaptationLog, setAdaptationLog] = useState<AdaptationDecision[]>([]);

  const startInterview = async () => {
    if (!userName.trim()) {
      alert("Please enter your name");
      return;
    }

    setIsLoading(true);
    try {
      const roomName = `interview-${crypto.randomUUID().slice(0, 8)}`;
      const resp = await fetch(
        `http://localhost:8000/token?participant_name=${encodeURIComponent(userName)}&room_name=${roomName}&topic=${encodeURIComponent(topic)}&gender=${encodeURIComponent(gender)}`
      );
      const data = await resp.json();
      setToken(data.token);
      setSessionId(data.session_id || roomName);
      setUrl(process.env.NEXT_PUBLIC_LIVEKIT_URL || "");

      // Initialize session on backend
      await fetch("http://localhost:8000/session/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: roomName,
          participant_name: userName,
          gender: gender,
          topic: topic,
        }),
      });

      setStage("interview");
    } catch (e) {
      console.error(e);
      alert("Failed to start interview. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const endInterview = async () => {
    try {
      await fetch(`http://localhost:8000/session/end/${sessionId}`, {
        method: "POST",
      });
    } catch (e) {
      console.error("Error ending session:", e);
    }
    setStage("setup");
    setEmotionHistory([]);
    setAdaptationLog([]);
    setFusedEmotions(null);
  };

  if (stage === "setup") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          {/* Logo/Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 mb-4">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </div>
            <h1 className="text-4xl font-bold text-white mb-2">
              AI Interviewer
            </h1>
            <p className="text-gray-400">Emotion-Aware Adaptive Interview System</p>
          </div>

          {/* Setup Form */}
          <div className="bg-gray-800/50 backdrop-blur-xl rounded-2xl p-8 border border-gray-700/50 shadow-2xl">
            <div className="space-y-5">
              {/* Name Input */}
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">
                  Your Name
                </label>
                <input
                  type="text"
                  id="name"
                  value={userName}
                  onChange={(e) => setUserName(e.target.value)}
                  placeholder="Enter your name"
                  className="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Gender Selection */}
              <div>
                <label htmlFor="gender" className="block text-sm font-medium text-gray-300 mb-2">
                  Gender (for fairness tracking)
                </label>
                <select
                  id="gender"
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all appearance-none cursor-pointer"
                >
                  {GENDERS.map((g) => (
                    <option key={g} value={g} className="bg-gray-800">
                      {g}
                    </option>
                  ))}
                </select>
              </div>

              {/* Topic Selection */}
              <div>
                <label htmlFor="topic" className="block text-sm font-medium text-gray-300 mb-2">
                  Interview Topic
                </label>
                <select
                  id="topic"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all appearance-none cursor-pointer"
                >
                  {TOPICS.map((t) => (
                    <option key={t} value={t} className="bg-gray-800">
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              {/* Start Button */}
              <button
                onClick={startInterview}
                disabled={isLoading}
                className="w-full py-4 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none shadow-lg shadow-purple-500/25"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Starting Interview...
                  </span>
                ) : (
                  "Start Adaptive Interview"
                )}
              </button>
            </div>

            {/* Features */}
            <div className="mt-8 pt-6 border-t border-gray-700/50">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl mb-1">🎭</div>
                  <div className="text-xs text-gray-400">Emotion-Aware</div>
                </div>
                <div>
                  <div className="text-2xl mb-1">🔄</div>
                  <div className="text-xs text-gray-400">Adaptive</div>
                </div>
                <div>
                  <div className="text-2xl mb-1">⚖️</div>
                  <div className="text-xs text-gray-400">Fair</div>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <p className="text-center text-gray-500 text-sm mt-6">
            Camera & microphone required for emotion detection
          </p>
        </div>
      </div>
    );
  }

  // Interview Stage
  return (
    <LiveKitRoom
      video={true}
      audio={true}
      token={token}
      serverUrl={url}
      data-lk-theme="default"
      className="h-screen bg-gray-950"
    >
      <InterviewContent
        topic={topic}
        userName={userName}
        sessionId={sessionId}
        showDashboard={showDashboard}
        setShowDashboard={setShowDashboard}
        showFairness={showFairness}
        setShowFairness={setShowFairness}
        facialEmotions={facialEmotions}
        setFacialEmotions={setFacialEmotions}
        vocalEmotions={vocalEmotions}
        setVocalEmotions={setVocalEmotions}
        fusedEmotions={fusedEmotions}
        setFusedEmotions={setFusedEmotions}
        emotionHistory={emotionHistory}
        setEmotionHistory={setEmotionHistory}
        adaptationLog={adaptationLog}
        setAdaptationLog={setAdaptationLog}
        endInterview={endInterview}
      />
      <RoomAudioRenderer />
      <StartAudio label="Click to enable audio" />
    </LiveKitRoom>
  );
}

// Separate component to use hooks inside LiveKitRoom
interface InterviewContentProps {
  topic: string;
  userName: string;
  sessionId: string;
  showDashboard: boolean;
  setShowDashboard: (v: boolean) => void;
  showFairness: boolean;
  setShowFairness: (v: boolean) => void;
  facialEmotions: InterviewEmotions | null;
  setFacialEmotions: (v: InterviewEmotions | null) => void;
  vocalEmotions: VocalEmotions | null;
  setVocalEmotions: (v: VocalEmotions | null) => void;
  fusedEmotions: FusedEmotions | null;
  setFusedEmotions: (v: FusedEmotions | null) => void;
  emotionHistory: EmotionDataPoint[];
  setEmotionHistory: React.Dispatch<React.SetStateAction<EmotionDataPoint[]>>;
  adaptationLog: AdaptationDecision[];
  setAdaptationLog: React.Dispatch<React.SetStateAction<AdaptationDecision[]>>;
  endInterview: () => void;
}

function InterviewContent({
  topic,
  userName,
  sessionId,
  showDashboard,
  setShowDashboard,
  showFairness,
  setShowFairness,
  facialEmotions,
  setFacialEmotions,
  vocalEmotions,
  setVocalEmotions,
  fusedEmotions,
  setFusedEmotions,
  emotionHistory,
  setEmotionHistory,
  adaptationLog,
  setAdaptationLog,
  endInterview,
}: InterviewContentProps) {
  const { localParticipant } = useLocalParticipant();
  const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null);
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null);

  // Function to send emotion data via data channel
  const sendEmotionToAgent = useCallback(async (emotionData: FusedEmotions) => {
    if (!localParticipant) {
      return;
    }

    try {
      const encoder = new TextEncoder();
      const data = encoder.encode(
        JSON.stringify({
          type: "emotion_update",
          data: emotionData,
        })
      );
      // Use DataPublishOptions with reliability setting
      await localParticipant.publishData(data, {
        reliable: true,
        destinationIdentities: undefined, // Broadcast to all
      });
    } catch (err) {
      // Silently fail - don't spam console during interview
      if (err instanceof Error && !err.message.includes('closed')) {
        console.warn("Could not publish emotion data:", err.message);
      }
    }
  }, [localParticipant]);

  // Get video element reference
  const tracks = useTracks([Track.Source.Camera], { onlySubscribed: false });

  useEffect(() => {
    // Find local video track
    const localVideoTrack = tracks.find(
      (track) => track.participant.isLocal && track.source === Track.Source.Camera
    );

    if (localVideoTrack?.publication?.track) {
      const mediaTrack = localVideoTrack.publication.track.mediaStreamTrack;
      const stream = new MediaStream([mediaTrack]);
      const tempVideo = document.createElement("video");
      tempVideo.srcObject = stream;
      tempVideo.autoplay = true;
      tempVideo.muted = true;
      tempVideo.playsInline = true;
      tempVideo.play().then(() => {
        setVideoElement(tempVideo);
        console.log("DEBUG: Video element ready for emotion detection");
      });
    }
  }, [tracks]);

  // Get audio stream
  useEffect(() => {
    const getAudio = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        setAudioStream(stream);
      } catch (err) {
        console.error("Error getting audio stream:", err);
      }
    };
    getAudio();

    return () => {
      if (audioStream) {
        audioStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  // Multimodal fusion
  const fuseEmotions = useCallback(() => {
    if (!facialEmotions && !vocalEmotions) return;

    const facial = facialEmotions || { anxiety: 0.5, confidence: 0.5, engagement: 0.5 };
    const vocal = vocalEmotions || { anxiety: 0.5, confidence: 0.5, engagement: 0.5 };

    const fused: FusedEmotions = {
      anxiety: AUDIO_WEIGHT * vocal.anxiety + VISUAL_WEIGHT * facial.anxiety,
      confidence: AUDIO_WEIGHT * vocal.confidence + VISUAL_WEIGHT * facial.confidence,
      engagement: AUDIO_WEIGHT * vocal.engagement + VISUAL_WEIGHT * facial.engagement,
    };

    setFusedEmotions(fused);

    // Add to history
    setEmotionHistory((prev) => [
      ...prev,
      {
        timestamp: Date.now(),
        anxiety: fused.anxiety,
        confidence: fused.confidence,
        engagement: fused.engagement,
      },
    ]);

    // Send to agent via data channel
    sendEmotionToAgent(fused);

    // Log to backend
    logEmotionToBackend(fused, facial, vocal);
  }, [facialEmotions, vocalEmotions, sendEmotionToAgent, setFusedEmotions, setEmotionHistory]);

  // Fuse when either emotion updates
  useEffect(() => {
    fuseEmotions();
  }, [facialEmotions, vocalEmotions]);

  const logEmotionToBackend = async (
    fused: FusedEmotions,
    facial: InterviewEmotions,
    vocal: VocalEmotions
  ) => {
    try {
      await fetch("http://localhost:8000/emotion/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          anxiety: fused.anxiety,
          confidence: fused.confidence,
          engagement: fused.engagement,
          raw_facial: facial,
          raw_vocal: vocal,
          fused_emotion: getDominantEmotion(fused),
        }),
      });
    } catch (err) {
      console.error("Error logging emotion:", err);
    }
  };

  const getDominantEmotion = (emotions: FusedEmotions): string => {
    if (emotions.anxiety > 0.7) return "anxious";
    if (emotions.confidence > 0.7) return "confident";
    if (emotions.engagement > 0.7) return "engaged";
    if (emotions.engagement < 0.3) return "disengaged";
    return "neutral";
  };

  const handleFacialUpdate = useCallback(
    (facial: FacialEmotions, interview: InterviewEmotions) => {
      setFacialEmotions(interview);
    },
    [setFacialEmotions]
  );

  const handleVocalUpdate = useCallback(
    (features: VocalFeatures, emotions: VocalEmotions) => {
      setVocalEmotions(emotions);
    },
    [setVocalEmotions]
  );

  return (
    <div className="h-full flex">
      {/* Main Interview Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-gray-900/80 backdrop-blur border-b border-gray-800 px-6 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">AI Interview</h1>
            <p className="text-sm text-gray-400">{topic}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-400">Candidate: {userName}</span>

            {/* Toggle buttons */}
            <button
              onClick={() => setShowDashboard(!showDashboard)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${showDashboard
                ? "bg-purple-500/20 text-purple-400"
                : "bg-gray-700/50 text-gray-400"
                }`}
            >
              📊 Analytics
            </button>
            <button
              onClick={() => setShowFairness(!showFairness)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${showFairness
                ? "bg-blue-500/20 text-blue-400"
                : "bg-gray-700/50 text-gray-400"
                }`}
            >
              ⚖️ Fairness
            </button>

            <button
              onClick={endInterview}
              className="px-4 py-2 text-sm bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg transition-colors"
            >
              End Interview
            </button>
          </div>
        </div>

        {/* Video Conference */}
        <div className="flex-1 relative">
          <VideoConference />
        </div>
      </div>

      {/* Emotion Detection - Always active (hidden) */}
      <EmotionDetector
        videoElement={videoElement}
        onEmotionUpdate={handleFacialUpdate}
        isActive={true}
        showUI={false}
      />
      <VocalAnalyzer
        audioStream={audioStream}
        onVocalUpdate={handleVocalUpdate}
        isActive={true}
        showUI={false}
      />

      {/* Side Panel - Dashboard & Fairness */}
      {(showDashboard || showFairness) && (
        <div className="w-96 bg-gray-900/50 border-l border-gray-800 p-4 overflow-y-auto space-y-4">
          <EmotionDashboard
            emotionHistory={emotionHistory}
            adaptationLog={adaptationLog}
            currentEmotion={fusedEmotions}
            isVisible={showDashboard}
          />
          <FairnessPanel sessionId={sessionId} isVisible={showFairness} />
        </div>
      )}
    </div>
  );
}
