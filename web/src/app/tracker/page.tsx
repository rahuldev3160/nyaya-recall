"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface SubjectTime {
  subject_id: string;
  total_min: number;
  sessions: number;
}

interface TimeStats {
  total_today_min: number;
  total_all_time_min: number;
  by_subject: SubjectTime[];
  avg_time_per_question_sec: number;
  daily_breakdown: { date: string; total_min: number }[];
}

export default function TrackerPage() {
  const [subjects, setSubjects] = useState<any[]>([]);
  const [gaps, setGaps] = useState<any[]>([]);
  const [sar, setSar] = useState<any>(null);
  const [timeStats, setTimeStats] = useState<TimeStats | null>(null);

  useEffect(() => {
    api.getSubjects().then(setSubjects).catch(() => {});
    api.getGaps().then(setGaps).catch(() => {});
    api.getSar().then(setSar).catch(() => {});
    api.getTimeStats().then(setTimeStats).catch(() => {});
  }, []);

  const sarValue = typeof sar?.sar === "number" ? sar.sar : null;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Preparation Tracker</h1>

      {sarValue !== null && (
        <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 flex items-center gap-6">
          <div>
            <div className="text-xs text-gray-400 mb-1">Self-Assessment Reliability</div>
            <div className="text-2xl font-bold text-amber-400">{(sarValue * 100).toFixed(0)}%</div>
          </div>
          <p className="text-sm text-gray-400">
            Based on {sar.total_claims ?? 0} attestation(s). Higher = your self-assessments are accurate.
          </p>
        </div>
      )}

      {/* Study Time Section */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-4">Study Time</h2>
        {timeStats === null ? (
          <p className="text-gray-500">Loading time data…</p>
        ) : (
          <div className="space-y-6">
            {/* Today + All-time summary */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="text-xs text-gray-400 mb-1">Today</div>
                <div className="text-3xl font-bold text-cyan-400">
                  {timeStats.total_today_min >= 60
                    ? `${(timeStats.total_today_min / 60).toFixed(1)}h`
                    : `${Math.round(timeStats.total_today_min)}m`}
                </div>
              </div>
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="text-xs text-gray-400 mb-1">All-time</div>
                <div className="text-3xl font-bold text-purple-400">
                  {(timeStats.total_all_time_min / 60).toFixed(1)}h
                </div>
              </div>
            </div>

            {/* Avg time per question */}
            {timeStats.avg_time_per_question_sec > 0 && (
              <div className="text-sm text-gray-400">
                Avg time per question:{" "}
                <span className="text-gray-200 font-medium">
                  {Math.round(timeStats.avg_time_per_question_sec)}s
                </span>
              </div>
            )}

            {/* Per-subject time bars */}
            {timeStats.by_subject.length > 0 && (
              <div>
                <div className="text-sm text-gray-400 mb-3">Time by subject</div>
                <div className="space-y-3">
                  {timeStats.by_subject.map((s) => {
                    const maxMin = timeStats.by_subject[0]?.total_min || 1;
                    const pct = Math.min(100, (s.total_min / maxMin) * 100);
                    return (
                      <div key={s.subject_id}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-gray-300">
                            {s.subject_id.replace(/_/g, " ")}
                          </span>
                          <span className="text-gray-400">
                            {s.total_min >= 60
                              ? `${(s.total_min / 60).toFixed(1)}h`
                              : `${Math.round(s.total_min)}m`}{" "}
                            · {s.sessions} session{s.sessions !== 1 ? "s" : ""}
                          </span>
                        </div>
                        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-cyan-600"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 10-day sparkline-style breakdown */}
            {timeStats.daily_breakdown.length > 0 && (
              <div>
                <div className="text-sm text-gray-400 mb-3">Last 10 days</div>
                <div className="flex items-end gap-1 h-12">
                  {timeStats.daily_breakdown.map((d) => {
                    const maxMin =
                      Math.max(...timeStats.daily_breakdown.map((x) => x.total_min)) || 1;
                    const heightPct = Math.max(4, (d.total_min / maxMin) * 100);
                    return (
                      <div
                        key={d.date}
                        className="flex-1 flex flex-col items-center gap-1"
                        title={`${d.date}: ${Math.round(d.total_min)}m`}
                      >
                        <div
                          className="w-full rounded-sm bg-cyan-700 opacity-80"
                          style={{ height: `${heightPct}%` }}
                        />
                        <div className="text-[10px] text-gray-600 leading-none">
                          {d.date.slice(5)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {timeStats.by_subject.length === 0 && (
              <p className="text-gray-500 text-sm">
                No sessions recorded yet — complete a quiz to see time data.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-4">Subject Scores</h2>
        {subjects.length === 0 ? (
          <p className="text-gray-500">No data yet — complete some quiz sessions first.</p>
        ) : (
          <div className="space-y-4">
            {subjects.map((s) => (
              <div key={s.subject_id}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-300">{s.subject_id.replace(/_/g, " ")}</span>
                  <span className="text-gray-400">
                    {Math.round(s.avg_score ?? 0)}% · {s.subtopics_assessed ?? 0} subtopics
                  </span>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      (s.avg_score ?? 0) >= 75 ? "bg-green-500" :
                      (s.avg_score ?? 0) >= 50 ? "bg-amber-500" : "bg-red-500"
                    }`}
                    style={{ width: `${s.avg_score ?? 0}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-4">Gaps Below 75% Threshold</h2>
        {gaps.length === 0 ? (
          <p className="text-gray-500">No gaps found — either all strong or not yet assessed.</p>
        ) : (
          <div className="space-y-2">
            {gaps.slice(0, 20).map((g, i) => (
              <div key={i} className="flex items-center gap-4 text-sm">
                <div className="w-2 h-2 rounded-full bg-red-500 shrink-0" />
                <span className="flex-1 text-gray-300">{g.subtopic_id?.replace(/_/g, " ")}</span>
                <span className="text-gray-500">{g.subject_id}</span>
                <span className="text-amber-400 w-12 text-right">{Math.round(g.score ?? 0)}%</span>
                <span className="text-gray-500 w-20 text-right">~{g.estimated_hours_to_75}h</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
