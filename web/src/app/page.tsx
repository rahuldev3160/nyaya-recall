"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const SUBJECTS = [
  { id: "polity", name: "Polity & Governance" },
  { id: "history_amac", name: "Ancient, Medieval & Culture" },
  { id: "modern_history", name: "Modern History" },
  { id: "geography", name: "Geography" },
  { id: "economy", name: "Economy" },
  { id: "environment", name: "Environment" },
  { id: "science_tech", name: "Science & Tech" },
  { id: "current_affairs", name: "Current Affairs" },
  { id: "ir_governance", name: "IR & Governance" },
];

function scoreColor(score: number) {
  if (score >= 75) return "bg-green-500";
  if (score >= 50) return "bg-amber-500";
  return "bg-red-500";
}

function planLabel(totalDays: number) {
  if (totalDays <= 14) return "Sprint";
  if (totalDays <= 45) return "Prep Plan";
  return "Long-term Plan";
}

export default function Dashboard() {
  const [profile, setProfile] = useState<any>(null);
  const [plan, setPlan] = useState<any>(null);
  const [config, setConfig] = useState<any>(null);
  const [syncing, setSyncing] = useState(false);

  /** Strip CSAT sessions from any plan response — CSAT has its own separate flow at /csat */
  const filterPlan = (data: any): any => {
    if (data?.sessions) {
      return { ...data, sessions: (data.sessions as any[]).filter((s) => s.subject_id !== "csat") };
    }
    return data;
  };

  useEffect(() => {
    (async () => {
      try { setProfile(await api.getProfile()); } catch {}
      try { setPlan(filterPlan(await api.getPlan())); } catch {}
      try { setConfig(await api.getConfig()); } catch {}
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.syncAnalysis();
      try { setProfile(await api.getProfile()); } catch {}
      try { setPlan(filterPlan(await api.getPlan())); } catch {}
      try { setConfig(await api.getConfig()); } catch {}
    } finally {
      setSyncing(false);
    }
  };

  const totalDays = config?.total_days ?? 10;
  const startDate = config?.start_date ? new Date(config.start_date) : null;
  const today = new Date();
  const elapsed = startDate
    ? Math.max(0, Math.floor((today.getTime() - startDate.getTime()) / 86400000))
    : 0;
  const dayNumber = elapsed + 1;
  const daysLeft = Math.max(0, totalDays - elapsed);
  const readiness = profile?.overall_readiness ?? 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">UPSC {planLabel(totalDays)}</h1>
          <p className="text-gray-400 mt-1">
            Day {dayNumber} of {totalDays} · {daysLeft} day{daysLeft !== 1 ? "s" : ""} remaining
          </p>
        </div>
        <div className="text-right">
          <div className="text-5xl font-bold text-amber-400">{readiness}%</div>
          <div className="text-gray-400 text-sm mt-1">Overall Readiness</div>
        </div>
      </div>

      {/* No config yet — prompt setup */}
      {!config && (
        <div className="bg-amber-950 border border-amber-800 rounded-xl p-5 flex items-center justify-between">
          <div>
            <p className="text-amber-300 font-medium">Set up your prep plan first</p>
            <p className="text-amber-500 text-sm mt-0.5">Choose your timeline and daily study hours to personalise everything.</p>
          </div>
          <a href="/setup" className="bg-amber-600 hover:bg-amber-500 text-white px-4 py-2 rounded-lg text-sm font-medium shrink-0 ml-4">
            Set Up →
          </a>
        </div>
      )}

      {/* Readiness bar */}
      <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-amber-400 rounded-full transition-all duration-500"
          style={{ width: `${readiness}%` }}
        />
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Start Diagnostic", href: "/diagnostic", color: "bg-blue-600 hover:bg-blue-500" },
          { label: "Today's Sessions", href: "/session", color: "bg-green-600 hover:bg-green-500" },
          { label: "View Tracker", href: "/tracker", color: "bg-purple-600 hover:bg-purple-500" },
          { label: "Exam Strategy", href: "/strategy", color: "bg-orange-600 hover:bg-orange-500" },
        ].map((btn) => (
          <a key={btn.label} href={btn.href}
            className={`${btn.color} text-white text-center py-3 px-4 rounded-lg font-medium transition-colors`}>
            {btn.label}
          </a>
        ))}
      </div>

      {/* Today's plan */}
      {plan?.sessions && plan.sessions.length > 0 && (
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <h2 className="text-lg font-semibold mb-4">
            Today&apos;s Plan — Day {plan.day_number ?? dayNumber}
          </h2>
          {plan.daily_goal && (
            <p className="text-amber-300 text-sm mb-4">{plan.daily_goal}</p>
          )}
          <div className="space-y-2">
            {plan.sessions.map((s: any, i: number) => (
              <div key={i} className="flex items-center gap-4 p-3 bg-gray-800 rounded-lg">
                <span className="text-gray-500 text-sm w-5">{i + 1}</span>
                <span className="flex-1 text-sm">
                  <span className="text-white font-medium">{s.subject_id?.replace(/_/g, " ")}</span>
                  <span className="text-gray-400"> → {s.subtopic_id?.replace(/_/g, " ")}</span>
                </span>
                <span className="text-gray-500 text-xs">{s.estimated_minutes} min</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  s.format === "notes_then_quiz" ? "bg-blue-900 text-blue-300" : "bg-gray-700 text-gray-300"
                }`}>
                  {s.format?.replace(/_/g, " ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Subject scores */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-4">Subject Readiness</h2>
        <div className="space-y-3">
          {SUBJECTS.map((s) => {
            const data = profile?.subjects?.[s.id];
            const score = data?.avg_score ?? 0;
            return (
              <div key={s.id} className="flex items-center gap-4">
                <span className="text-sm text-gray-300 w-44 shrink-0">{s.name}</span>
                <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div className={`h-full ${scoreColor(score)} rounded-full transition-all`}
                    style={{ width: `${score}%` }} />
                </div>
                <span className="text-sm text-gray-400 w-10 text-right">
                  {score > 0 ? `${Math.round(score)}%` : "—"}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Sync + analysis */}
      <div className="flex gap-4">
        <button onClick={handleSync} disabled={syncing}
          className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium px-6 py-3 rounded-lg transition-colors">
          {syncing ? "Syncing..." : "Sync & Plan Tomorrow"}
        </button>
        <a href="/analysis"
          className="border border-gray-700 text-gray-300 hover:text-white px-6 py-3 rounded-lg transition-colors">
          View Full Analysis
        </a>
      </div>

      {profile?.last_analysis && (
        <div className="bg-gray-900 border border-amber-900 rounded-xl p-4">
          <p className="text-amber-300 text-sm font-medium mb-1">Last Analysis</p>
          <p className="text-gray-300 text-sm">{profile.last_analysis}</p>
        </div>
      )}
    </div>
  );
}
