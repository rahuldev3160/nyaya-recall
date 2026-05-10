"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function TrackerPage() {
  const [subjects, setSubjects] = useState<any[]>([]);
  const [gaps, setGaps] = useState<any[]>([]);
  const [sar, setSar] = useState<any>(null);

  useEffect(() => {
    api.getSubjects().then(setSubjects).catch(() => {});
    api.getGaps().then(setGaps).catch(() => {});
    api.getSar().then(setSar).catch(() => {});
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
