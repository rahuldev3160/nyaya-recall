"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function PlannerPage() {
  const [plan, setPlan] = useState<any>(null);
  const [hours, setHours] = useState(8);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.getPlan().then(setPlan).catch(() => {}); }, []);

  const generatePlan = async () => {
    setLoading(true);
    try {
      const p = await api.generatePlan(hours);
      setPlan(p);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Study Planner</h1>

      <div className="flex items-end gap-4">
        <div>
          <label className="block text-sm text-gray-400 mb-2">Available hours today</label>
          <input type="number" min={2} max={14} value={hours} onChange={(e) => setHours(+e.target.value)}
            className="w-28 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white" />
        </div>
        <button onClick={generatePlan} disabled={loading}
          className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-medium">
          {loading ? "Generating..." : "Plan Today"}
        </button>
      </div>

      {plan?.sessions && (
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-4">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-lg font-semibold">Day {plan.day} Plan</h2>
              <p className="text-amber-300 text-sm mt-1">{plan.daily_goal}</p>
            </div>
            <span className="text-gray-500 text-sm">{plan.sessions.length} sessions</span>
          </div>

          <div className="space-y-3">
            {plan.sessions.map((s: any, i: number) => (
              <div key={i} className="flex items-start gap-4 p-4 bg-gray-800 rounded-lg">
                <span className="text-gray-500 text-sm mt-0.5 w-5 shrink-0">{i + 1}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-white font-medium text-sm">{s.subject_id?.replace(/_/g, " ")}</span>
                    <span className="text-gray-500 text-xs">→</span>
                    <span className="text-gray-300 text-sm">{s.subtopic_id?.replace(/_/g, " ")}</span>
                  </div>
                  <p className="text-gray-500 text-xs">{s.rationale}</p>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm text-gray-400">{s.estimated_minutes} min</div>
                  <div className={`text-xs mt-1 px-2 py-0.5 rounded ${
                    s.format === "notes_then_quiz" ? "bg-blue-900 text-blue-300" : "bg-gray-700 text-gray-300"
                  }`}>
                    {s.format?.replace(/_/g, " ")}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {plan.sync_reminder && (
            <div className="border-t border-gray-800 pt-4">
              <p className="text-sm text-gray-400">
                <span className="text-amber-400 font-medium">Evening reminder: </span>
                {plan.sync_reminder}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
