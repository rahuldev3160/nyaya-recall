"use client";

import { useEffect, useState } from "react";

interface DailyChallenge {
  challenge_date: string;
  question_ids: number[];
}

interface Entry {
  rank: number;
  username: string;
  score: number;
  total: number;
  accuracy: number;
  time_sec: number;
}

export default function LeaderboardPage() {
  const [challenge, setChallenge] = useState<DailyChallenge | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/backend/questions/daily-challenge")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (d?.challenge_date) setChallenge(d);
      })
      .catch(() => null)
      .finally(() => setLoading(false));

    // Leaderboard endpoint — returns [] until multi-user auth ships
    fetch("/api/backend/leaderboard/daily")
      .then((r) => r.ok ? r.json() : [])
      .then((d) => Array.isArray(d) ? setEntries(d) : null)
      .catch(() => null);
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-white">Leaderboard</h1>
        <p className="text-sm text-gray-400 mt-0.5">Daily challenge — same 10 questions for everyone</p>
      </div>

      {/* Daily challenge info */}
      {challenge && (
        <div className="rounded-xl border border-amber-700/50 bg-amber-950/20 p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-500">Today&apos;s challenge</p>
            <p className="text-sm font-semibold text-amber-300">{challenge.challenge_date}</p>
            <p className="text-xs text-gray-500 mt-0.5">{challenge.question_ids?.length ?? 10} questions</p>
          </div>
          <a
            href="/practice?mode=daily"
            className="rounded-lg border border-amber-600 bg-amber-900/30 px-4 py-2 text-sm text-amber-300 hover:bg-amber-800/40 transition-colors"
          >
            Take challenge →
          </a>
        </div>
      )}

      {loading && (
        <div className="text-sm text-gray-500">Loading…</div>
      )}

      {/* Leaderboard table */}
      {entries.length > 0 ? (
        <div className="rounded-xl border border-gray-700 bg-gray-900 overflow-hidden">
          <div className="grid grid-cols-4 gap-2 px-4 py-2 border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wide">
            <div>#</div>
            <div>Aspirant</div>
            <div className="text-right">Score</div>
            <div className="text-right">Time</div>
          </div>
          {entries.map((e) => (
            <div
              key={e.rank}
              className={`grid grid-cols-4 gap-2 px-4 py-3 border-b border-gray-800/50 last:border-0 ${
                e.rank <= 3 ? "bg-amber-900/10" : ""
              }`}
            >
              <div className={`font-bold text-sm ${e.rank === 1 ? "text-amber-400" : e.rank === 2 ? "text-gray-300" : e.rank === 3 ? "text-amber-700" : "text-gray-500"}`}>
                {e.rank === 1 ? "🥇" : e.rank === 2 ? "🥈" : e.rank === 3 ? "🥉" : e.rank}
              </div>
              <div className="text-sm text-white font-medium truncate">{e.username}</div>
              <div className="text-right text-sm text-gray-300">{e.score}/{e.total}</div>
              <div className="text-right text-sm text-gray-500">{Math.round(e.time_sec / 60)}m {e.time_sec % 60}s</div>
            </div>
          ))}
        </div>
      ) : !loading && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-8 text-center space-y-3">
          <p className="text-3xl">🏆</p>
          <p className="text-sm font-medium text-white">No results yet today</p>
          <p className="text-sm text-gray-500">Be the first to complete today&apos;s challenge.</p>
          <p className="text-xs text-gray-600 mt-2">
            Leaderboard rankings go live when multi-user accounts launch.
          </p>
          {challenge && (
            <a
              href="/practice?mode=daily"
              className="inline-block mt-2 rounded-lg border border-amber-600 px-4 py-2 text-sm text-amber-300 hover:bg-amber-900/20"
            >
              Take the challenge →
            </a>
          )}
        </div>
      )}
    </div>
  );
}
