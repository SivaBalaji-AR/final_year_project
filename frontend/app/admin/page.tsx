"use client";

import { useState, useEffect, useRef, useCallback } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const WS_URL = BACKEND_URL.replace("http://", "ws://").replace("https://", "wss://");

// Face mesh connections for drawing lines between landmarks
const FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10];
const LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246, 33];
const RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398, 362];
const LEFT_EYEBROW = [46, 53, 52, 65, 55, 70, 63, 105, 66, 107, 46];
const RIGHT_EYEBROW = [276, 283, 282, 295, 285, 300, 293, 334, 296, 336, 276];
const LIPS_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185, 61];
const LIPS_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78];
const NOSE = [168, 6, 197, 195, 5, 4, 1, 19, 94, 2, 164, 0, 11, 12, 13, 14, 15, 16, 17, 18, 200, 199, 175, 152];

interface SessionInfo {
    session_id: string;
    participant_name: string;
    topic: string;
    is_active: boolean;
    start_time: number;
    total_frames: number;
}

interface EmotionPoint {
    timestamp: number;
    anxiety: number;
    confidence: number;
    engagement: number;
}

interface Adaptation {
    timestamp: number;
    action: string;
    difficulty: string;
    tone: string;
}

interface TranscriptEntry {
    role: string;
    text: string;
    is_final: boolean;
    timestamp: number;
}

export default function AdminPage() {
    const [sessions, setSessions] = useState<SessionInfo[]>([]);
    const [selectedSession, setSelectedSession] = useState<string>("");
    const [isConnected, setIsConnected] = useState(false);

    // Analysis data
    const [landmarks, setLandmarks] = useState<{ x: number; y: number; z: number }[] | null>(null);
    const [faceEmotions, setFaceEmotions] = useState<any>(null);
    const [microExpressions, setMicroExpressions] = useState<any>(null);
    const [vocalFeatures, setVocalFeatures] = useState<any>(null);
    const [vocalEmotions, setVocalEmotions] = useState<any>(null);
    const [fusedEmotions, setFusedEmotions] = useState<any>(null);
    const [emotionTimeline, setEmotionTimeline] = useState<EmotionPoint[]>([]);
    const [adaptationLog, setAdaptationLog] = useState<Adaptation[]>([]);
    const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
    const [sessionInfo, setSessionInfo] = useState<any>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Fetch sessions
    useEffect(() => {
        const fetchSessions = async () => {
            try {
                const res = await fetch(`${BACKEND_URL}/api/sessions`);
                const data = await res.json();
                setSessions(data.sessions || []);
            } catch (e) {
                console.error("Failed to fetch sessions:", e);
            }
        };
        fetchSessions();
        const interval = setInterval(fetchSessions, 3000);
        return () => clearInterval(interval);
    }, []);

    // Connect to admin WebSocket
    useEffect(() => {
        if (!selectedSession) return;

        const ws = new WebSocket(`${WS_URL}/ws/admin/${selectedSession}`);
        wsRef.current = ws;

        ws.onopen = () => setIsConnected(true);

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleAdminMessage(data);
            } catch (e) {
                console.error("Parse error:", e);
            }
        };

        ws.onclose = () => setIsConnected(false);
        ws.onerror = () => setIsConnected(false);

        return () => {
            ws.close();
            setIsConnected(false);
        };
    }, [selectedSession]);

    const handleAdminMessage = useCallback((data: any) => {
        switch (data.type) {
            case "session_info":
                setSessionInfo(data);
                setEmotionTimeline(data.emotion_timeline || []);
                setAdaptationLog(data.adaptation_log || []);
                setTranscript(data.transcript || []);
                break;

            case "face_update":
                if (data.landmarks) setLandmarks(data.landmarks);
                if (data.emotions) setFaceEmotions(data.emotions);
                if (data.micro_expressions) setMicroExpressions(data.micro_expressions);
                break;

            case "vocal_update":
                if (data.features) setVocalFeatures(data.features);
                if (data.emotions) setVocalEmotions(data.emotions);
                break;

            case "fused_emotions":
                if (data.emotions) {
                    setFusedEmotions(data.emotions);
                    setEmotionTimeline(prev => [...prev.slice(-200), {
                        timestamp: data.timestamp || Date.now() / 1000,
                        ...data.emotions,
                    }]);
                }
                break;

            case "transcript":
                if (data.is_final) {
                    setTranscript(prev => [...prev, data]);
                }
                break;

            case "adaptation":
                setAdaptationLog(prev => [...prev, {
                    timestamp: Date.now() / 1000,
                    action: data.action,
                    difficulty: data.difficulty,
                    tone: data.tone,
                }]);
                break;
        }
    }, []);

    // ─── Draw Face Landmarks ──────────────────────────────────────────────────

    useEffect(() => {
        if (!landmarks || !canvasRef.current) return;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        canvas.width = 400;
        canvas.height = 400;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Background
        ctx.fillStyle = "#0f0f1a";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Scale landmarks to canvas
        const sx = canvas.width;
        const sy = canvas.height;

        // Draw connections
        const drawPath = (indices: number[], color: string, width: number = 1) => {
            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.lineWidth = width;
            for (let i = 0; i < indices.length; i++) {
                const idx = indices[i];
                if (idx >= landmarks.length) continue;
                const x = landmarks[idx].x * sx;
                const y = landmarks[idx].y * sy;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
        };

        drawPath(FACE_OVAL, "#6366f1", 2);
        drawPath(LEFT_EYE, "#22d3ee", 1.5);
        drawPath(RIGHT_EYE, "#22d3ee", 1.5);
        drawPath(LEFT_EYEBROW, "#a78bfa", 1.5);
        drawPath(RIGHT_EYEBROW, "#a78bfa", 1.5);
        drawPath(LIPS_OUTER, "#f472b6", 1.5);
        drawPath(LIPS_INNER, "#fb7185", 1);

        // Draw all landmark points
        for (let i = 0; i < landmarks.length; i++) {
            const x = landmarks[i].x * sx;
            const y = landmarks[i].y * sy;
            const z = landmarks[i].z;
            const size = Math.max(0.5, 1.5 + z * 5);
            const alpha = Math.max(0.2, 0.6 + z * 2);
            ctx.beginPath();
            ctx.arc(x, y, size, 0, 2 * Math.PI);
            ctx.fillStyle = `rgba(99, 102, 241, ${alpha})`;
            ctx.fill();
        }

    }, [landmarks]);

    // ─── Render ─────────────────────────────────────────────────────────────────

    if (!selectedSession) {
        return (
            <div className="min-h-screen bg-gray-950 text-white p-8">
                <div className="max-w-3xl mx-auto">
                    <h1 className="text-3xl font-bold mb-2">Admin Dashboard</h1>
                    <p className="text-gray-400 mb-8">Monitor active interview sessions in real-time</p>

                    {sessions.length === 0 ? (
                        <div className="bg-gray-900 rounded-xl p-12 text-center border border-gray-800">
                            <div className="text-4xl mb-4">📊</div>
                            <h2 className="text-xl font-medium mb-2">No Sessions</h2>
                            <p className="text-gray-400">Start an interview on the main page to see analysis here.</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {sessions.map((s) => (
                                <button
                                    key={s.session_id}
                                    onClick={() => setSelectedSession(s.session_id)}
                                    className="w-full bg-gray-900 hover:bg-gray-800 border border-gray-800 rounded-xl p-4 text-left transition-colors flex items-center justify-between"
                                >
                                    <div>
                                        <div className="font-medium">{s.participant_name || "Unknown"}</div>
                                        <div className="text-sm text-gray-400">{s.topic} · {s.session_id}</div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {s.is_active ? (
                                            <span className="flex items-center gap-1.5 text-green-400 text-sm">
                                                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                                                Live
                                            </span>
                                        ) : (
                                            <span className="text-gray-500 text-sm">Ended</span>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className="h-screen flex flex-col bg-gray-950 text-white">
            {/* Header */}
            <div className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <button onClick={() => setSelectedSession("")}
                        className="text-gray-400 hover:text-white transition-colors">
                        ← Back
                    </button>
                    <div>
                        <h1 className="font-semibold">Session: {sessionInfo?.participant_name || selectedSession}</h1>
                        <p className="text-sm text-gray-400">{sessionInfo?.topic || "Loading..."}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500 animate-pulse" : "bg-red-500"}`}></div>
                    <span className="text-sm text-gray-400">{isConnected ? "Connected" : "Disconnected"}</span>
                </div>
            </div>

            {/* Main Grid */}
            <div className="flex-1 grid grid-cols-3 grid-rows-2 gap-px bg-gray-800 overflow-hidden">

                {/* Face Landmarks */}
                <div className="bg-gray-950 p-4 flex flex-col">
                    <h3 className="text-sm font-medium text-gray-400 mb-2">Face Mesh (468 Landmarks)</h3>
                    <div className="flex-1 flex items-center justify-center">
                        <canvas ref={canvasRef} className="rounded-lg border border-gray-800 max-w-full max-h-full" />
                    </div>
                </div>

                {/* Emotion Bars */}
                <div className="bg-gray-950 p-4">
                    <h3 className="text-sm font-medium text-gray-400 mb-3">Fused Emotions</h3>
                    <div className="space-y-4">
                        {[
                            { label: "Anxiety", value: fusedEmotions?.anxiety ?? 0, color: "bg-red-500", face: faceEmotions?.anxiety, vocal: vocalEmotions?.anxiety },
                            { label: "Confidence", value: fusedEmotions?.confidence ?? 0, color: "bg-green-500", face: faceEmotions?.confidence, vocal: vocalEmotions?.confidence },
                            { label: "Engagement", value: fusedEmotions?.engagement ?? 0, color: "bg-blue-500", face: faceEmotions?.engagement, vocal: vocalEmotions?.engagement },
                        ].map(({ label, value, color, face, vocal }) => (
                            <div key={label}>
                                <div className="flex justify-between text-sm mb-1">
                                    <span className="text-gray-300">{label}</span>
                                    <span className="text-white font-mono">{Math.round(value * 100)}%</span>
                                </div>
                                <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
                                    <div className={`h-full ${color} transition-all duration-300 rounded-full`}
                                        style={{ width: `${value * 100}%` }} />
                                </div>
                                <div className="flex justify-between text-xs text-gray-500 mt-0.5">
                                    <span>Face: {face != null ? Math.round(face * 100) + '%' : '—'}</span>
                                    <span>Vocal: {vocal != null ? Math.round(vocal * 100) + '%' : '—'}</span>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Micro-expressions */}
                    <h3 className="text-sm font-medium text-gray-400 mt-5 mb-2">Micro-Expressions</h3>
                    {microExpressions ? (
                        <div className="grid grid-cols-2 gap-2 text-xs">
                            {[
                                { label: "Blink Rate", value: microExpressions.blink_rate },
                                { label: "Eyebrow Raise", value: microExpressions.eyebrow_raise },
                                { label: "Mouth Open", value: microExpressions.mouth_open },
                                { label: "Jaw Clench", value: microExpressions.jaw_clench },
                            ].map(({ label, value }) => (
                                <div key={label} className="bg-gray-900 rounded-lg px-3 py-2">
                                    <div className="text-gray-400">{label}</div>
                                    <div className="text-white font-mono">{typeof value === 'number' ? value.toFixed(3) : '—'}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-xs text-gray-600">Waiting for face data...</p>
                    )}
                </div>

                {/* Vocal Analysis */}
                <div className="bg-gray-950 p-4">
                    <h3 className="text-sm font-medium text-gray-400 mb-3">Vocal Analysis</h3>
                    {vocalFeatures ? (
                        <div className="space-y-3">
                            {[
                                { label: "Pitch", value: `${vocalFeatures.avg_pitch?.toFixed(0) || 0} Hz`, sub: `var: ${vocalFeatures.pitch_variance?.toFixed(1)}` },
                                { label: "Volume", value: (vocalFeatures.volume * 1000).toFixed(1), sub: `var: ${(vocalFeatures.volume_variance * 1000).toFixed(2)}` },
                                { label: "Speaking", value: vocalFeatures.is_speaking ? "Yes" : "No", sub: `ratio: ${(vocalFeatures.speaking_ratio * 100).toFixed(0)}%` },
                            ].map(({ label, value, sub }) => (
                                <div key={label} className="bg-gray-900 rounded-lg px-4 py-3">
                                    <div className="flex justify-between items-center">
                                        <span className="text-gray-300 text-sm">{label}</span>
                                        <span className="text-white font-mono text-lg">{value}</span>
                                    </div>
                                    <div className="text-xs text-gray-500 mt-0.5">{sub}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-xs text-gray-600">Waiting for audio data...</p>
                    )}

                    {/* Adaptation Log */}
                    <h3 className="text-sm font-medium text-gray-400 mt-5 mb-2">Adaptation Log</h3>
                    <div className="space-y-1.5 max-h-36 overflow-y-auto">
                        {adaptationLog.slice(-8).map((a, i) => (
                            <div key={i} className="bg-gray-900 rounded px-3 py-1.5 text-xs">
                                <span className="text-purple-400">{a.difficulty}</span>
                                <span className="text-gray-500"> · </span>
                                <span className="text-cyan-400">{a.tone}</span>
                            </div>
                        ))}
                        {adaptationLog.length === 0 && (
                            <p className="text-xs text-gray-600">No adaptations yet</p>
                        )}
                    </div>
                </div>

                {/* Emotion Timeline */}
                <div className="bg-gray-950 p-4 col-span-1">
                    <h3 className="text-sm font-medium text-gray-400 mb-2">Emotion Timeline</h3>
                    <EmotionChart data={emotionTimeline} />
                </div>

                {/* Transcript */}
                <div className="bg-gray-950 p-4 col-span-2 flex flex-col">
                    <h3 className="text-sm font-medium text-gray-400 mb-2">Live Transcript</h3>
                    <div className="flex-1 overflow-y-auto space-y-2">
                        {transcript.map((entry, i) => (
                            <div key={i} className={`text-sm px-3 py-2 rounded-lg ${entry.role === "user"
                                    ? "bg-purple-900/20 text-purple-200 ml-8"
                                    : "bg-gray-800 text-gray-200 mr-8"
                                }`}>
                                <span className="text-xs text-gray-500">{entry.role === "user" ? "Candidate" : "AI"}: </span>
                                {entry.text}
                            </div>
                        ))}
                        {transcript.length === 0 && (
                            <p className="text-xs text-gray-600">Waiting for transcript...</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

// ─── Simple SVG Emotion Chart ────────────────────────────────────────────────

function EmotionChart({ data }: { data: EmotionPoint[] }) {
    if (data.length < 2) {
        return <p className="text-xs text-gray-600">Collecting emotion data...</p>;
    }

    const recent = data.slice(-60);
    const w = 380, h = 220;
    const pad = { top: 10, right: 10, bottom: 20, left: 30 };
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    const makePath = (key: "anxiety" | "confidence" | "engagement") => {
        return recent.map((p, i) => {
            const x = pad.left + (i / Math.max(recent.length - 1, 1)) * plotW;
            const y = pad.top + (1 - p[key]) * plotH;
            return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(' ');
    };

    return (
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-full">
            {/* Grid */}
            {[0, 0.25, 0.5, 0.75, 1].map(v => (
                <g key={v}>
                    <line x1={pad.left} y1={pad.top + (1 - v) * plotH} x2={w - pad.right} y2={pad.top + (1 - v) * plotH}
                        stroke="#1f2937" strokeWidth="0.5" />
                    <text x={pad.left - 4} y={pad.top + (1 - v) * plotH + 3}
                        fill="#6b7280" fontSize="8" textAnchor="end">{Math.round(v * 100)}%
                    </text>
                </g>
            ))}

            {/* Lines */}
            <path d={makePath("anxiety")} fill="none" stroke="#ef4444" strokeWidth="1.5" opacity="0.8" />
            <path d={makePath("confidence")} fill="none" stroke="#22c55e" strokeWidth="1.5" opacity="0.8" />
            <path d={makePath("engagement")} fill="none" stroke="#3b82f6" strokeWidth="1.5" opacity="0.8" />

            {/* Legend */}
            <circle cx={pad.left + 5} cy={h - 5} r="3" fill="#ef4444" />
            <text x={pad.left + 12} y={h - 2} fill="#9ca3af" fontSize="8">Anxiety</text>
            <circle cx={pad.left + 65} cy={h - 5} r="3" fill="#22c55e" />
            <text x={pad.left + 72} y={h - 2} fill="#9ca3af" fontSize="8">Confidence</text>
            <circle cx={pad.left + 140} cy={h - 5} r="3" fill="#3b82f6" />
            <text x={pad.left + 147} y={h - 2} fill="#9ca3af" fontSize="8">Engagement</text>
        </svg>
    );
}
