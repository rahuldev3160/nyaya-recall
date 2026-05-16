"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface SubjectTrajectory {
  id: string;
  name: string;
  readiness_pct: number;
  coverage_pct: number;
  subtopics_total: number;
  subtopics_tested: number;
  subtopics_remaining: number;
  daily_target: number;
  risk_level: "high" | "medium" | "low";
  top_priority_untested: string[];
  topics_total: number;
  uncovered_topics_count: number;
  at_risk_topics_count: number;
}

interface TrajectoryData {
  exam_date: string;
  days_remaining: number;
  overall_readiness: number;
  subjects: SubjectTrajectory[];
  at_risk_subjects: string[];
  trajectory_note: string;
  today_sessions_count: number;
}

const riskClasses: Record<string, string> = {
  high: "text-red-400 bg-red-950 border-red-800",
  medium: "text-yellow-400 bg-yellow-950 border-yellow-800",
  low: "text-green-400 bg-green-950 border-green-800",
};

function readinessBarColor(pct: number) {
  if (pct >= 70) return "bg-green-500";
  if (pct >= 40) return "bg-yellow-500";
  return "bg-red-500";
}

export default function StrategyPage() {
  const [trajectory, setTrajectory] = useState<TrajectoryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/backend/plan/trajectory")
      .then((r) => r.json())
      .then((data: TrajectoryData) => {
        setTrajectory(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-2xl space-y-8">
      {/* ── SUPERPLAN DASHBOARD ── */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Exam Readiness</h1>
          {trajectory && (
            <span className="text-sm bg-red-950 text-red-300 border border-red-800 rounded-full px-3 py-1 font-semibold">
              {trajectory.days_remaining}d to exam
            </span>
          )}
        </div>

        {loading && (
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 text-gray-500 text-sm">
            Loading trajectory…
          </div>
        )}

        {!loading && !trajectory && (
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 text-gray-500 text-sm">
            No prep profile yet. Run batch_analyse.py to generate one.
          </div>
        )}

        {trajectory && (
          <>
            {/* Overall readiness bar */}
            <div className="bg-gray-900 rounded-xl p-5 border border-gray-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Overall Readiness</span>
                <span className="text-lg font-bold text-white">
                  {trajectory.overall_readiness.toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-800 rounded-full h-2.5">
                <div
                  className={`${readinessBarColor(trajectory.overall_readiness)} h-2.5 rounded-full transition-all`}
                  style={{ width: `${Math.min(trajectory.overall_readiness, 100)}%` }}
                />
              </div>
              <p className="text-xs text-gray-500 italic">{trajectory.trajectory_note}</p>
            </div>

            {/* At-risk alert */}
            {trajectory.at_risk_subjects.length > 0 && (
              <div className="bg-red-950 border border-red-800 rounded-xl p-4 space-y-1">
                <p className="text-sm font-semibold text-red-400">
                  At risk of not covering by exam:
                </p>
                <p className="text-sm text-red-300">
                  {trajectory.at_risk_subjects.join(" · ")}
                </p>
              </div>
            )}

            {/* Today's plan quick-start */}
            {trajectory.today_sessions_count > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-white">Today&apos;s Plan</p>
                  <p className="text-xs text-gray-500">
                    {trajectory.today_sessions_count} session
                    {trajectory.today_sessions_count !== 1 ? "s" : ""} scheduled
                  </p>
                </div>
                <Link
                  href="/session"
                  className="text-sm bg-amber-500 hover:bg-amber-400 text-black font-semibold px-4 py-2 rounded-lg transition-colors"
                >
                  Start →
                </Link>
              </div>
            )}

            {/* Subject grid */}
            <div className="space-y-3">
              {trajectory.subjects.map((s) => (
                <div
                  key={s.id}
                  className="bg-gray-900 rounded-xl p-4 border border-gray-800 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-white">{s.name}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${riskClasses[s.risk_level]}`}
                    >
                      {s.risk_level.toUpperCase()}
                    </span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-1.5">
                    <div
                      className={`${readinessBarColor(s.readiness_pct)} h-1.5 rounded-full`}
                      style={{ width: `${Math.min(s.readiness_pct, 100)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>
                      {s.subtopics_tested}/{s.subtopics_total} tested · {s.coverage_pct}%
                      covered
                    </span>
                    <span>{s.readiness_pct}% ready</span>
                  </div>
                  {s.topics_total > 0 && (
                    <div className="text-xs text-gray-600">
                      {s.uncovered_topics_count > 0 ? (
                        <span className="text-orange-700">
                          {s.uncovered_topics_count}/{s.topics_total} topics not started
                          {s.at_risk_topics_count > 0 && ` · ${s.at_risk_topics_count} at risk`}
                        </span>
                      ) : (
                        <span className="text-green-800">
                          All {s.topics_total} topics started
                          {s.at_risk_topics_count > 0 && (
                            <span className="text-orange-700"> · {s.at_risk_topics_count} at risk</span>
                          )}
                        </span>
                      )}
                    </div>
                  )}
                  {s.subtopics_remaining > 0 && (
                    <p className="text-xs text-gray-600">
                      {s.subtopics_remaining} remaining · need {s.daily_target}/day
                    </p>
                  )}
                  {s.top_priority_untested.length > 0 && (
                    <p className="text-xs text-amber-700 truncate">
                      Focus: {s.top_priority_untested.slice(0, 3).join(", ")}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* ── EXAM DAY STRATEGY (existing content) ── */}
      <h1 className="text-2xl font-bold">Exam Day Strategy</h1>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-4">
        <h2 className="text-lg font-semibold text-amber-400">Attempt Order (GS Paper 1)</h2>
        {[
          ["1", "Polity & Governance", "15-22 Qs", "25 min"],
          ["2", "Environment & Ecology", "10-15 Qs", "18 min"],
          ["3", "History (Ancient + Modern)", "12-18 Qs", "18 min"],
          ["4", "Economy", "10-14 Qs", "15 min"],
          ["5", "Geography + Mapping", "10-14 Qs", "15 min"],
          ["6", "Science & Technology", "6-10 Qs", "12 min"],
          ["7", "Current Affairs + IR", "15-22 Qs", "17 min"],
        ].map(([n, subj, qs, time]) => (
          <div key={n} className="flex items-center gap-4 text-sm">
            <span className="text-amber-400 font-bold w-4">{n}</span>
            <span className="flex-1 text-gray-200">{subj}</span>
            <span className="text-gray-500">{qs}</span>
            <span className="text-gray-400 w-14 text-right">{time}</span>
          </div>
        ))}
      </div>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-3">
        <h2 className="text-lg font-semibold text-amber-400">Guessing Rules</h2>
        {[
          "Never guess if you cannot confirm even 1 statement.",
          "Guess if you can eliminate 2 options — expected value is positive at –1/3.",
          "'Both A and B' answers: correct ~40% in recent PYQs.",
          "'None of the above': rare in recent years — treat with suspicion.",
          "Statements with absolute words (always, never, only) are often wrong.",
        ].map((rule, i) => (
          <div key={i} className="flex gap-3 text-sm">
            <span className="text-amber-500 mt-0.5">•</span>
            <span className="text-gray-300">{rule}</span>
          </div>
        ))}
      </div>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-3">
        <h2 className="text-lg font-semibold text-amber-400">
          PYQ Patterns — High-Frequency Topics
        </h2>
        {[
          ["Polity", "Schedule 7, Fundamental Rights (Art 14-32), Parliamentary procedures"],
          ["Environment", "Ramsar sites, Biodiversity hotspots, COP updates, Species in news"],
          ["Economy", "Budget terms, RBI tools, WTO, Economic Survey themes"],
          ["History", "Bhakti-Sufi movements, INC phases, Art forms"],
          ["Geography", "Rivers, Monsoon mechanism, Straits, Protected areas"],
          ["Science", "ISRO missions, Diseases, AI applications"],
        ].map(([subj, topics]) => (
          <div key={subj} className="text-sm">
            <span className="text-white font-medium">{subj}: </span>
            <span className="text-gray-400">{topics}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
