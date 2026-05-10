"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

function getPhases(totalDays: number) {
  if (totalDays <= 14) {
    return [
      { name: "Diagnostic", days: Math.max(1, Math.round(totalDays * 0.15)), color: "bg-blue-500" },
      { name: "Intensive Revision", days: Math.round(totalDays * 0.55), color: "bg-amber-500" },
      { name: "Mock & Strategy", days: Math.max(1, Math.round(totalDays * 0.30)), color: "bg-green-500" },
    ];
  }
  if (totalDays <= 45) {
    return [
      { name: "Diagnostic", days: Math.max(1, Math.round(totalDays * 0.10)), color: "bg-blue-500" },
      { name: "Learning", days: Math.round(totalDays * 0.45), color: "bg-purple-500" },
      { name: "Revision", days: Math.round(totalDays * 0.30), color: "bg-amber-500" },
      { name: "Mock & Strategy", days: Math.max(2, Math.round(totalDays * 0.15)), color: "bg-green-500" },
    ];
  }
  return [
    { name: "Diagnostic", days: Math.max(2, Math.round(totalDays * 0.08)), color: "bg-blue-500" },
    { name: "Deep Learning", days: Math.round(totalDays * 0.50), color: "bg-purple-500" },
    { name: "Revision", days: Math.round(totalDays * 0.27), color: "bg-amber-500" },
    { name: "Mock & Strategy", days: Math.max(5, Math.round(totalDays * 0.15)), color: "bg-green-500" },
  ];
}

const PRESETS = [
  { label: "5-day sprint", days: 5, hours: 8 },
  { label: "10-day sprint", days: 10, hours: 6 },
  { label: "1 month", days: 30, hours: 5 },
  { label: "3 months", days: 90, hours: 4 },
];

export default function SetupPage() {
  const router = useRouter();
  const [totalDays, setTotalDays] = useState(10);
  const [dailyHours, setDailyHours] = useState(6);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.getConfig().then((cfg) => {
      if (cfg?.total_days) setTotalDays(cfg.total_days);
      if (cfg?.daily_hours) setDailyHours(cfg.daily_hours);
      setLoaded(true);
    }).catch(() => setLoaded(true));
  }, []);

  const phases = getPhases(totalDays);
  const totalStudyHours = totalDays * dailyHours;

  const save = async () => {
    setSaving(true);
    try {
      await api.saveConfig({ total_days: totalDays, daily_hours: dailyHours });
      router.push("/");
    } catch (e) {
      setSaving(false);
    }
  };

  if (!loaded) return <div className="text-gray-400">Loading...</div>;

  return (
    <div className="max-w-xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Set Up Your Prep Plan</h1>
        <p className="text-gray-400 text-sm mt-2">
          Tell the system how long you have and how many hours you can study per day.
          Everything — plan generation, phase transitions, adaptive difficulty — adapts automatically.
        </p>
      </div>

      {/* Presets */}
      <div>
        <label className="block text-sm text-gray-400 mb-3">Quick presets</label>
        <div className="grid grid-cols-2 gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => { setTotalDays(p.days); setDailyHours(p.hours); }}
              className={`py-2 px-4 rounded-lg border text-sm transition-colors ${
                totalDays === p.days && dailyHours === p.hours
                  ? "border-amber-500 bg-amber-500/10 text-amber-400"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Total days slider */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <label className="text-sm text-gray-400">Total prep days</label>
          <span className="text-amber-400 font-bold text-lg">{totalDays} days</span>
        </div>
        <input
          type="range" min={5} max={90} value={totalDays}
          onChange={(e) => setTotalDays(+e.target.value)}
          className="w-full accent-amber-500"
        />
        <div className="flex justify-between text-xs text-gray-600 mt-1">
          <span>5 (sprint)</span><span>30 (1 month)</span><span>90 (3 months)</span>
        </div>
      </div>

      {/* Daily hours slider */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <label className="text-sm text-gray-400">Study hours per day</label>
          <span className="text-amber-400 font-bold text-lg">{dailyHours}h</span>
        </div>
        <input
          type="range" min={2} max={12} value={dailyHours}
          onChange={(e) => setDailyHours(+e.target.value)}
          className="w-full accent-amber-500"
        />
        <div className="flex justify-between text-xs text-gray-600 mt-1">
          <span>2h</span><span>6h</span><span>12h</span>
        </div>
      </div>

      {/* Phase breakdown */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
        <div className="flex justify-between items-center mb-1">
          <h3 className="text-sm font-medium text-gray-300">Phase breakdown</h3>
          <span className="text-xs text-gray-500">{totalStudyHours}h total study time</span>
        </div>
        <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
          {phases.map((ph) => (
            <div
              key={ph.name}
              className={`${ph.color} opacity-80`}
              style={{ width: `${(ph.days / totalDays) * 100}%` }}
            />
          ))}
        </div>
        <div className="space-y-1.5">
          {phases.map((ph) => (
            <div key={ph.name} className="flex items-center gap-3 text-sm">
              <div className={`w-2.5 h-2.5 rounded-full ${ph.color} shrink-0`} />
              <span className="text-gray-300 flex-1">{ph.name}</span>
              <span className="text-gray-500">{ph.days} days · {ph.days * dailyHours}h</span>
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={save}
        disabled={saving}
        className="w-full bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium py-3 rounded-lg transition-colors"
      >
        {saving ? "Saving..." : "Save & Start Prep →"}
      </button>
    </div>
  );
}
