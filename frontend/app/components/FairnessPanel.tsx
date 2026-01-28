"use client";

import { useEffect, useState } from "react";

interface FairnessData {
    demographic_parity: {
        by_gender: {
            [key: string]: {
                easy_pct: number;
                medium_pct: number;
                hard_pct: number;
                total_questions: number;
            };
        };
        parity_gap: {
            easy: number;
            medium: number;
            hard: number;
        };
        within_threshold: boolean;
    };
    comparison_metrics: {
        total_sessions: number;
        completion_rate: number;
        avg_anxiety_reduction: number;
    };
}

interface FairnessPanelProps {
    sessionId: string;
    isVisible: boolean;
}

export default function FairnessPanel({ sessionId, isVisible }: FairnessPanelProps) {
    const [data, setData] = useState<FairnessData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!isVisible) return;

        const fetchData = async () => {
            try {
                const resp = await fetch("http://localhost:8000/fairness/metrics");
                const json = await resp.json();
                setData(json);
            } catch (err) {
                console.error("Error fetching fairness metrics:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
        // Refresh every 10 seconds
        const interval = setInterval(fetchData, 10000);
        return () => clearInterval(interval);
    }, [isVisible]);

    if (!isVisible) return null;

    if (loading) {
        return (
            <div className="bg-gray-800/80 backdrop-blur border border-gray-700 rounded-xl p-4">
                <div className="flex items-center gap-2 text-gray-400">
                    <div className="animate-spin w-4 h-4 border-2 border-purple-500 border-t-transparent rounded-full"></div>
                    Loading fairness metrics...
                </div>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="bg-gray-800/80 backdrop-blur border border-gray-700 rounded-xl p-4">
                <p className="text-gray-500 text-sm">No fairness data available</p>
            </div>
        );
    }

    const { demographic_parity, comparison_metrics } = data;
    const genders = Object.keys(demographic_parity.by_gender);

    return (
        <div className="bg-gray-800/80 backdrop-blur border border-gray-700 rounded-xl p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                    <span className="text-xl">⚖️</span> Fairness Metrics
                </h3>
                <span
                    className={`px-2 py-1 rounded text-xs font-medium ${demographic_parity.within_threshold
                            ? "bg-green-900/50 text-green-400"
                            : "bg-red-900/50 text-red-400"
                        }`}
                >
                    {demographic_parity.within_threshold ? "Within 5% threshold" : "Exceeds 5% gap"}
                </span>
            </div>

            {/* Parity Gap */}
            <div className="bg-gray-900/50 rounded-lg p-3">
                <h4 className="text-sm font-medium text-gray-300 mb-2">Demographic Parity Gap</h4>
                <div className="grid grid-cols-3 gap-2">
                    {Object.entries(demographic_parity.parity_gap).map(([difficulty, gap]) => (
                        <div key={difficulty} className="text-center">
                            <div className="text-xs text-gray-500 capitalize mb-1">{difficulty}</div>
                            <div
                                className={`text-lg font-bold ${gap < 5 ? "text-green-400" : "text-red-400"
                                    }`}
                            >
                                {gap}%
                            </div>
                            <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden mt-1">
                                <div
                                    className={`h-full ${gap < 5 ? "bg-green-500" : "bg-red-500"}`}
                                    style={{ width: `${Math.min(100, gap * 10)}%` }}
                                ></div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* By Gender Breakdown */}
            {genders.length > 0 && (
                <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-300">Question Distribution by Gender</h4>
                    <div className="grid gap-2">
                        {genders.map((gender) => {
                            const stats = demographic_parity.by_gender[gender];
                            return (
                                <div key={gender} className="bg-gray-900/50 rounded-lg p-2">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-sm text-white capitalize">{gender}</span>
                                        <span className="text-xs text-gray-500">
                                            {stats.total_questions} questions
                                        </span>
                                    </div>
                                    <div className="flex gap-1 h-2 rounded-full overflow-hidden">
                                        <div
                                            className="bg-green-500"
                                            style={{ width: `${stats.easy_pct}%` }}
                                            title={`Easy: ${stats.easy_pct}%`}
                                        ></div>
                                        <div
                                            className="bg-blue-500"
                                            style={{ width: `${stats.medium_pct}%` }}
                                            title={`Medium: ${stats.medium_pct}%`}
                                        ></div>
                                        <div
                                            className="bg-red-500"
                                            style={{ width: `${stats.hard_pct}%` }}
                                            title={`Hard: ${stats.hard_pct}%`}
                                        ></div>
                                    </div>
                                    <div className="flex justify-between text-[10px] text-gray-500 mt-1">
                                        <span>Easy {stats.easy_pct}%</span>
                                        <span>Med {stats.medium_pct}%</span>
                                        <span>Hard {stats.hard_pct}%</span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Comparison Metrics */}
            <div className="bg-gray-900/50 rounded-lg p-3">
                <h4 className="text-sm font-medium text-gray-300 mb-2">System Performance</h4>
                <div className="grid grid-cols-3 gap-3 text-center">
                    <div>
                        <div className="text-2xl font-bold text-purple-400">
                            {comparison_metrics.total_sessions}
                        </div>
                        <div className="text-xs text-gray-500">Sessions</div>
                    </div>
                    <div>
                        <div className="text-2xl font-bold text-green-400">
                            {comparison_metrics.completion_rate}%
                        </div>
                        <div className="text-xs text-gray-500">Completed</div>
                    </div>
                    <div>
                        <div className="text-2xl font-bold text-blue-400">
                            {comparison_metrics.avg_anxiety_reduction > 0 ? "+" : ""}
                            {(comparison_metrics.avg_anxiety_reduction * 100).toFixed(1)}%
                        </div>
                        <div className="text-xs text-gray-500">Anxiety Δ</div>
                    </div>
                </div>
            </div>
        </div>
    );
}
