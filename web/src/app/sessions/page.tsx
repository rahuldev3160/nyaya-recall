"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function SessionHistoryPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSessionHistory(50)
      .then(setSessions)
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, []);

  const fmt = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }) +
      " " + d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  };

  const scoreColor = (score: number | null) => {
    if (score === null) return "text-gray-500";
    if (score >= 70) return "text-green-400";
    if (score >= 50) return "text-amber-400";
    return "text-red-400";
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <a href="/session" className="text-gray-500 hover:text-gray-300 text-sm">← Today&apos;s Sessions</a>
        <h1 className="text-2xl font-bold">Session History</h1>
      </div>

      {loading && <p className="text-gray-500 text-sm">Loading...</p>}

      {!loading && sessions.length === 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-gray-400">
          No completed sessions yet. Start a session from the <a href="/session" className="text-amber-400 hover:underline">Sessions</a> page.
        </div>
      )}

      {!loading && sessions.length > 0 && (
        <div className="space-y-2">
          {sessions.map((s) => (
            <a
              key={s.id}
              href={`/sessions/${s.id}`}
              className="flex items-center gap-4 p-4 rounded-xl border border-gray-800 bg-gray-900 hover:border-gray-600 hover:bg-gray-800 transition-colors block"
            >
              <div className="flex-1 min-w-0">
                <div className="font-medium text-white capitalize">
                  {s.subject_id?.replace(/_/g, " ")}
                  {s.topic_id ? ` → ${s.topic_id.replace(/_/g, " ")}` : ""}
                </div>
                <div className="text-sm text-gray-500 mt-0.5">{fmt(s.start_time)}</div>
              </div>
              <div className="text-right shrink-0">
                <div className={`text-lg font-bold ${scoreColor(s.score)}`}>
                  {s.score !== null ? `${Math.round(s.score)}%` : "—"}
                </div>
                <div className="text-xs text-gray-600">
                  {s.answered}/{s.total_questions} answered
                  {s.skipped > 0 ? ` · ${s.skipped} skipped` : ""}
                </div>
              </div>
              <div className="text-gray-600 shrink-0">→</div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
