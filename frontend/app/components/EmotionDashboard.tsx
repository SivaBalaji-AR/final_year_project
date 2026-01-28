"use client";

import { useEffect, useRef, useState } from "react";
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler
);

export interface EmotionDataPoint {
    timestamp: number;
    anxiety: number;
    confidence: number;
    engagement: number;
}

export interface AdaptationDecision {
    timestamp: number;
    action: string;
    reason: string;
    difficulty: string;
    tone: string;
}

interface EmotionDashboardProps {
    emotionHistory: EmotionDataPoint[];
    adaptationLog: AdaptationDecision[];
    currentEmotion: {
        anxiety: number;
        confidence: number;
        engagement: number;
    } | null;
    isVisible: boolean;
}

export default function EmotionDashboard({
    emotionHistory,
    adaptationLog,
    currentEmotion,
    isVisible,
}: EmotionDashboardProps) {
    if (!isVisible) return null;

    // Prepare chart data - last 30 data points
    const recentHistory = emotionHistory.slice(-30);
    const labels = recentHistory.map((_, i) => `${i * 0.5}s`);

    const chartData = {
        labels,
        datasets: [
            {
                label: "Anxiety",
                data: recentHistory.map((d) => d.anxiety),
                borderColor: "rgb(239, 68, 68)",
                backgroundColor: "rgba(239, 68, 68, 0.1)",
                fill: true,
                tension: 0.4,
            },
            {
                label: "Confidence",
                data: recentHistory.map((d) => d.confidence),
                borderColor: "rgb(34, 197, 94)",
                backgroundColor: "rgba(34, 197, 94, 0.1)",
                fill: true,
                tension: 0.4,
            },
            {
                label: "Engagement",
                data: recentHistory.map((d) => d.engagement),
                borderColor: "rgb(59, 130, 246)",
                backgroundColor: "rgba(59, 130, 246, 0.1)",
                fill: true,
                tension: 0.4,
            },
        ],
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                min: 0,
                max: 1,
                grid: {
                    color: "rgba(255, 255, 255, 0.1)",
                },
                ticks: {
                    color: "rgba(255, 255, 255, 0.6)",
                },
            },
            x: {
                grid: {
                    display: false,
                },
                ticks: {
                    color: "rgba(255, 255, 255, 0.6)",
                    maxTicksLimit: 6,
                },
            },
        },
        plugins: {
            legend: {
                position: "top" as const,
                labels: {
                    color: "rgba(255, 255, 255, 0.8)",
                    boxWidth: 12,
                    padding: 10,
                },
            },
        },
        animation: {
            duration: 300,
        },
    };

    // Get color for emotion level
    const getEmotionColor = (value: number, type: "anxiety" | "confidence" | "engagement") => {
        if (type === "anxiety") {
            return value > 0.7 ? "text-red-400" : value > 0.4 ? "text-yellow-400" : "text-green-400";
        }
        if (type === "confidence") {
            return value > 0.7 ? "text-green-400" : value > 0.4 ? "text-blue-400" : "text-yellow-400";
        }
        return value > 0.7 ? "text-blue-400" : value > 0.4 ? "text-gray-300" : "text-yellow-400";
    };

    // Recent adaptations (last 5)
    const recentAdaptations = adaptationLog.slice(-5).reverse();

    return (
        <div className="bg-gray-800/80 backdrop-blur border border-gray-700 rounded-xl p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                    <span className="text-xl">📊</span> Emotion Analytics
                </h3>
                <span className="text-xs text-gray-400">Real-time</span>
            </div>

            {/* Current Emotion Meters */}
            {currentEmotion && (
                <div className="grid grid-cols-3 gap-3">
                    {/* Anxiety */}
                    <div className="bg-gray-900/50 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm text-gray-400">Anxiety</span>
                            <span className={`text-lg font-bold ${getEmotionColor(currentEmotion.anxiety, "anxiety")}`}>
                                {Math.round(currentEmotion.anxiety * 100)}%
                            </span>
                        </div>
                        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 transition-all duration-300"
                                style={{ width: `${currentEmotion.anxiety * 100}%` }}
                            ></div>
                        </div>
                    </div>

                    {/* Confidence */}
                    <div className="bg-gray-900/50 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm text-gray-400">Confidence</span>
                            <span className={`text-lg font-bold ${getEmotionColor(currentEmotion.confidence, "confidence")}`}>
                                {Math.round(currentEmotion.confidence * 100)}%
                            </span>
                        </div>
                        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-yellow-500 via-blue-500 to-green-500 transition-all duration-300"
                                style={{ width: `${currentEmotion.confidence * 100}%` }}
                            ></div>
                        </div>
                    </div>

                    {/* Engagement */}
                    <div className="bg-gray-900/50 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm text-gray-400">Engagement</span>
                            <span className={`text-lg font-bold ${getEmotionColor(currentEmotion.engagement, "engagement")}`}>
                                {Math.round(currentEmotion.engagement * 100)}%
                            </span>
                        </div>
                        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-yellow-500 to-blue-500 transition-all duration-300"
                                style={{ width: `${currentEmotion.engagement * 100}%` }}
                            ></div>
                        </div>
                    </div>
                </div>
            )}

            {/* Emotion Timeline Chart */}
            <div className="h-48">
                <Line data={chartData} options={chartOptions} />
            </div>

            {/* Adaptation Log */}
            <div className="space-y-2">
                <h4 className="text-sm font-medium text-gray-300 flex items-center gap-2">
                    <span>🔄</span> Adaptation Decisions
                </h4>
                <div className="max-h-32 overflow-y-auto space-y-1">
                    {recentAdaptations.length === 0 ? (
                        <p className="text-xs text-gray-500 italic">No adaptations yet</p>
                    ) : (
                        recentAdaptations.map((adaptation, i) => (
                            <div
                                key={i}
                                className="text-xs bg-gray-900/50 rounded px-2 py-1 flex items-start gap-2"
                            >
                                <span
                                    className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${adaptation.difficulty === "easy"
                                            ? "bg-green-900/50 text-green-400"
                                            : adaptation.difficulty === "hard"
                                                ? "bg-red-900/50 text-red-400"
                                                : "bg-blue-900/50 text-blue-400"
                                        }`}
                                >
                                    {adaptation.difficulty}
                                </span>
                                <span className="text-gray-400 flex-1">{adaptation.reason}</span>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
