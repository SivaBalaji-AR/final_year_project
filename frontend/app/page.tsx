"use client";

import { useState, useCallback, useRef, useEffect } from "react";

// Audio config - must match backend
const SAMPLE_RATE = 16000;         // Mic/STT sample rate
const TTS_SAMPLE_RATE = 44100;     // TTS playback sample rate (must match backend)
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const WS_URL = BACKEND_URL.replace("http://", "ws://").replace("https://", "wss://");

// Video frame capture interval (ms)
const FRAME_INTERVAL = 500;

// Binary message type prefixes (matching backend protocol)
const MSG_AUDIO = 0x01;
const MSG_VIDEO = 0x02;

interface TranscriptEntry {
  role: "user" | "assistant";
  text: string;
  timestamp: number;
  isFinal?: boolean;
}

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

export default function Home() {
  const [stage, setStage] = useState<"setup" | "interview">("setup");
  const [userName, setUserName] = useState("");
  const [gender, setGender] = useState(GENDERS[0]);
  const [topic, setTopic] = useState(TOPICS[0]);
  const [sessionId, setSessionId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

  const startInterview = async () => {
    if (!userName.trim()) {
      alert("Please enter your name");
      return;
    }

    setIsLoading(true);
    try {
      const newSessionId = `interview-${crypto.randomUUID().slice(0, 8)}`;
      setSessionId(newSessionId);

      await fetch(`${BACKEND_URL}/session/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: newSessionId,
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
      await fetch(`${BACKEND_URL}/session/end/${sessionId}`, { method: "POST" });
    } catch (e) {
      console.error("Error ending session:", e);
    }
    setStage("setup");
  };

  if (stage === "setup") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 mb-4">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </div>
            <h1 className="text-4xl font-bold text-white mb-2">AI Interviewer</h1>
            <p className="text-gray-400">Emotion-Aware Adaptive Interview System</p>
          </div>

          <div className="bg-gray-800/50 backdrop-blur-xl rounded-2xl p-8 border border-gray-700/50 shadow-2xl">
            <div className="space-y-5">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">Your Name</label>
                <input
                  type="text" id="name" value={userName}
                  onChange={(e) => setUserName(e.target.value)}
                  placeholder="Enter your name"
                  className="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                />
              </div>

              <div>
                <label htmlFor="gender" className="block text-sm font-medium text-gray-300 mb-2">Gender (for fairness tracking)</label>
                <select
                  id="gender" value={gender} onChange={(e) => setGender(e.target.value)}
                  className="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all appearance-none cursor-pointer"
                >
                  {GENDERS.map((g) => <option key={g} value={g} className="bg-gray-800">{g}</option>)}
                </select>
              </div>

              <div>
                <label htmlFor="topic" className="block text-sm font-medium text-gray-300 mb-2">Interview Topic</label>
                <select
                  id="topic" value={topic} onChange={(e) => setTopic(e.target.value)}
                  className="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all appearance-none cursor-pointer"
                >
                  {TOPICS.map((t) => <option key={t} value={t} className="bg-gray-800">{t}</option>)}
                </select>
              </div>

              <button
                onClick={startInterview} disabled={isLoading}
                className="w-full py-4 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-purple-500/25"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Starting...
                  </span>
                ) : "Start Interview"}
              </button>
            </div>

            <div className="mt-8 pt-6 border-t border-gray-700/50">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div><div className="text-2xl mb-1">🎭</div><div className="text-xs text-gray-400">Emotion-Aware</div></div>
                <div><div className="text-2xl mb-1">🔄</div><div className="text-xs text-gray-400">Adaptive</div></div>
                <div><div className="text-2xl mb-1">⚖️</div><div className="text-xs text-gray-400">Fair</div></div>
              </div>
            </div>
          </div>

          <p className="text-center text-gray-500 text-sm mt-6">Camera & microphone required</p>
        </div>
      </div>
    );
  }

  return (
    <InterviewPage
      topic={topic}
      userName={userName}
      gender={gender}
      sessionId={sessionId}
      endInterview={endInterview}
    />
  );
}


// ─── Clean Interview Page Component ───────────────────────────────────────────

function InterviewPage({
  topic, userName, gender, sessionId, endInterview,
}: {
  topic: string; userName: string; gender: string;
  sessionId: string; endInterview: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const frameIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [partialText, setPartialText] = useState<string>("");
  const [agentStatus, setAgentStatus] = useState<string>("connecting");

  // ─── WebSocket Connection ─────────────────────────────────────────────────

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/interview/${sessionId}`);
    wsRef.current = ws;

    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      console.log("Interview WebSocket connected");
      ws.send(JSON.stringify({
        type: "init",
        topic, gender,
        participant_name: userName,
      }));
      setAgentStatus("initializing");
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        handleAudioPlayback(event.data);
      } else {
        try {
          handleServerMessage(JSON.parse(event.data));
        } catch (e) {
          console.error("Parse error:", e);
        }
      }
    };

    ws.onclose = () => {
      setAgentStatus("disconnected");
    };

    ws.onerror = () => {
      setAgentStatus("error");
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "end" }));
        ws.close();
      }
    };
  }, [sessionId]);

  // ─── Server Message Handler ───────────────────────────────────────────────

  const handleServerMessage = useCallback((data: any) => {
    switch (data.type) {
      case "transcript":
        if (data.role === "user") {
          if (data.is_final) {
            setTranscript(prev => [...prev, {
              role: "user", text: data.text,
              timestamp: Date.now(), isFinal: true,
            }]);
            setPartialText("");
          } else {
            setPartialText(data.text);
          }
        } else if (data.role === "assistant") {
          setTranscript(prev => [...prev, {
            role: "assistant", text: data.text, timestamp: Date.now(),
          }]);
        }
        break;
      case "status":
        setAgentStatus(data.status);
        break;
      case "error":
        console.error("Server error:", data.message);
        break;
    }
  }, []);

  // ─── Audio Playback ───────────────────────────────────────────────────────

  const playbackCtxRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const stoppedRef = useRef(false);
  const nextPlayTimeRef = useRef(0);

  const handleAudioPlayback = useCallback((buffer: ArrayBuffer) => {
    if (stoppedRef.current) return;
    audioQueueRef.current.push(buffer);
    if (!isPlayingRef.current) playAudioQueue();
  }, []);

  const playAudioQueue = useCallback(async () => {
    if (isPlayingRef.current) return;
    isPlayingRef.current = true;

    if (!playbackCtxRef.current) {
      playbackCtxRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
    }
    const ctx = playbackCtxRef.current;

    while (audioQueueRef.current.length > 0 && !stoppedRef.current) {
      const buf = audioQueueRef.current.shift()!;
      const int16 = new Int16Array(buf);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0;

      const audioBuf = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
      audioBuf.getChannelData(0).set(float32);

      const src = ctx.createBufferSource();
      src.buffer = audioBuf;
      src.connect(ctx.destination);

      // Schedule buffers back-to-back using precise timing to avoid gaps
      const now = ctx.currentTime;
      const startAt = Math.max(now, nextPlayTimeRef.current);
      src.start(startAt);
      nextPlayTimeRef.current = startAt + audioBuf.duration;

      // Wait for this chunk to finish (with small overlap for queue check)
      await new Promise<void>((resolve) => {
        setTimeout(resolve, (audioBuf.duration * 1000) + 10);
      });
    }

    isPlayingRef.current = false;
  }, []);

  const stopAllAudio = useCallback(() => {
    stoppedRef.current = true;
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    nextPlayTimeRef.current = 0;
    if (playbackCtxRef.current) {
      playbackCtxRef.current.close().catch(() => { });
      playbackCtxRef.current = null;
    }
  }, []);

  // ─── Camera + Mic Setup ───────────────────────────────────────────────────

  useEffect(() => {
    let mounted = true;

    const setup = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480 },
          audio: {
            sampleRate: SAMPLE_RATE,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });

        if (!mounted) {
          stream.getTracks().forEach(t => t.stop());
          return;
        }

        mediaStreamRef.current = stream;

        // Video
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }

        // Audio capture → WebSocket
        setupAudioCapture(stream);

        // Video frame capture → WebSocket (every 500ms)
        startVideoFrameCapture();

      } catch (err) {
        console.error("Media access error:", err);
      }
    };

    setup();

    return () => {
      mounted = false;
      if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
      if (audioContextRef.current) audioContextRef.current.close();
      if (mediaStreamRef.current) mediaStreamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  const setupAudioCapture = (stream: MediaStream) => {
    const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
    audioContextRef.current = ctx;

    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (e) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      const input = e.inputBuffer.getChannelData(0);
      const pcm16 = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }

      // Prefix with 0x01 (audio type)
      const prefixed = new Uint8Array(1 + pcm16.buffer.byteLength);
      prefixed[0] = MSG_AUDIO;
      prefixed.set(new Uint8Array(pcm16.buffer), 1);
      wsRef.current.send(prefixed.buffer);
    };

    source.connect(processor);
    const muteNode = ctx.createGain();
    muteNode.gain.value = 0;
    processor.connect(muteNode);
    muteNode.connect(ctx.destination);
  };

  const startVideoFrameCapture = () => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    const captureCtx = canvas.getContext("2d");
    if (!captureCtx) return;

    frameIntervalRef.current = setInterval(() => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      if (!video.videoWidth) return;

      canvas.width = 320;  // Lower res for bandwidth
      canvas.height = 240;
      captureCtx.drawImage(video, 0, 0, 320, 240);

      canvas.toBlob((blob) => {
        if (!blob || !wsRef.current) return;
        blob.arrayBuffer().then((buf) => {
          // Prefix with 0x02 (video type)
          const prefixed = new Uint8Array(1 + buf.byteLength);
          prefixed[0] = MSG_VIDEO;
          prefixed.set(new Uint8Array(buf), 1);
          wsRef.current!.send(prefixed.buffer);
        });
      }, "image/jpeg", 0.6);
    }, FRAME_INTERVAL);
  };

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, partialText]);

  const handleEnd = () => {
    stopAllAudio();
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "end" }));
      wsRef.current.close();
    }
    endInterview();
  };

  const getStatusText = () => {
    switch (agentStatus) {
      case "connecting": return "Connecting...";
      case "initializing": return "Starting interview...";
      case "thinking": return "AI is thinking...";
      case "speaking": return "AI is speaking...";
      case "listening": case "done_speaking": return "Listening...";
      case "disconnected": return "Disconnected";
      case "error": return "Connection error";
      default: return agentStatus;
    }
  };

  const getStatusColor = () => {
    switch (agentStatus) {
      case "listening": case "done_speaking": return "bg-green-500";
      case "thinking": return "bg-yellow-500";
      case "speaking": return "bg-blue-500";
      case "error": case "disconnected": return "bg-red-500";
      default: return "bg-gray-500";
    }
  };

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="h-screen flex flex-col bg-gray-950">
      {/* Header */}
      <div className="bg-gray-900/80 backdrop-blur border-b border-gray-800 px-6 py-3 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-white">AI Interview</h1>
          <p className="text-sm text-gray-400">{topic}</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full animate-pulse ${getStatusColor()}`}></div>
            <span className="text-sm text-gray-400">{getStatusText()}</span>
          </div>
          <span className="text-sm text-gray-500">{userName}</span>
          <button onClick={handleEnd}
            className="px-4 py-2 text-sm bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg transition-colors">
            End Interview
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Video Panel */}
        <div className="w-1/2 flex flex-col bg-gray-900/50 border-r border-gray-800">
          <div className="flex-1 relative">
            <video ref={videoRef} autoPlay muted playsInline
              className="w-full h-full object-cover" />
            <div className="absolute bottom-3 left-3 px-3 py-1 bg-black/60 backdrop-blur rounded-lg">
              <span className="text-xs text-white">{userName} (You)</span>
            </div>
          </div>

          {/* AI Agent Status */}
          <div className="h-24 bg-gradient-to-r from-gray-900 to-gray-800 border-t border-gray-800 flex items-center px-6 gap-4">
            <div className={`w-14 h-14 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center ${agentStatus === "speaking" ? "animate-pulse" : ""}`}>
              <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </div>
            <div>
              <h3 className="text-white font-medium">AI Interviewer</h3>
              <p className="text-sm text-gray-400">{getStatusText()}</p>
            </div>
            {agentStatus === "speaking" && (
              <div className="flex items-center gap-1 ml-auto">
                {[0, 1, 2, 3, 4].map(i => (
                  <div key={i} className="w-1 bg-blue-500 rounded-full animate-pulse"
                    style={{ height: `${8 + Math.random() * 16}px`, animationDelay: `${i * 0.1}s` }} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Transcript Panel */}
        <div className="w-1/2 flex flex-col bg-gray-950">
          <div className="px-4 py-3 border-b border-gray-800">
            <h2 className="text-sm font-medium text-gray-300">Conversation</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {transcript.map((entry, i) => (
              <div key={i} className={`flex ${entry.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${entry.role === "user"
                  ? "bg-purple-600/20 text-purple-100 rounded-br-md"
                  : "bg-gray-800/80 text-gray-200 rounded-bl-md"
                  }`}>
                  <div className="text-xs text-gray-500 mb-1">
                    {entry.role === "user" ? userName : "AI Interviewer"}
                  </div>
                  {entry.text}
                </div>
              </div>
            ))}

            {partialText && (
              <div className="flex justify-end">
                <div className="max-w-[85%] px-4 py-3 rounded-2xl text-sm bg-purple-600/10 text-purple-200/70 rounded-br-md border border-purple-500/20">
                  <div className="text-xs text-gray-500 mb-1">{userName} (speaking...)</div>
                  {partialText}
                </div>
              </div>
            )}

            {agentStatus === "thinking" && (
              <div className="flex justify-start">
                <div className="px-4 py-3 rounded-2xl bg-gray-800/80 rounded-bl-md">
                  <div className="flex items-center gap-1">
                    {[0, 1, 2].map(i => (
                      <div key={i} className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"
                        style={{ animationDelay: `${i * 150}ms` }} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div ref={transcriptEndRef} />
          </div>
        </div>
      </div>

      {/* Hidden canvas for video frame capture */}
      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
