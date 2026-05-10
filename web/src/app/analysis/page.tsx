"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function AnalysisPage() {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runSync = async () => {
    setLoading(true);
    setResult(null);
    setMessage(null);
    setError(null);
    try {
      const data = await api.syncAnalysis();
      if (data?.message && !data?.summary) {
        setMessage(data.message);
      } else {
        setResult(data);
      }
    } catch (e: any) {
      setError("Analysis failed. Make sure you have completed quiz sessions since your last sync.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">Session Analysis</h1>
      <p className="text-gray-400">
        Analyses all completed sessions since your last sync and updates your preparation profile.
      </p>

      <button
        onClick={runSync}
        disabled={loading}
        className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium px-6 py-3 rounded-lg"
      >
        {loading ? "Analysing..." : "Run Batch Analysis"}
      </button>

      {message && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl px-5 py-4 text-gray-400 text-sm">
          {message}
        </div>
      )}

      {error && (
        <div className="bg-red-950 border border-red-800 rounded-xl px-5 py-4 text-red-300 text-sm">
          {error}
        </div>
      )}

      {result?.summary && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          <p className="text-white">{result.summary}</p>
          <p className="text-amber-400 font-semibold">
            Overall Readiness: {result.overall_readiness}%
          </p>
          {result.subject_updates?.map((s: any) => (
            <div key={s.subject_id} className="border-t border-gray-800 pt-4">
              <div className="flex justify-between mb-1">
                <span className="text-gray-300 font-medium">{s.subject_id.replace(/_/g, " ")}</span>
                <span className={s.avg_score >= 75 ? "text-green-400" : s.avg_score >= 50 ? "text-amber-400" : "text-red-400"}>
                  {s.avg_score}%
                </span>
              </div>
              <p className="text-gray-400 text-sm">{s.insight}</p>
              {s.weak_question_types?.length > 0 && (
                <p className="text-amber-500 text-xs mt-1">
                  Weak formats: {s.weak_question_types.join(", ")}
                </p>
              )}
            </div>
          ))}
          {result.deep_drill_observations?.length > 0 && (
            <div className="border-t border-gray-800 pt-4">
              <p className="text-amber-300 text-sm font-medium mb-2">Deep Drill Observations</p>
              {result.deep_drill_observations.map((obs: any, i: number) => (
                <div key={i} className="mb-3">
                  <p className="text-gray-300 text-sm font-medium">{obs.subtopic_id?.replace(/_/g, " ")}</p>
                  <p className="text-gray-400 text-xs mt-0.5">{obs.pattern}</p>
                  <p className="text-green-400 text-xs mt-0.5">→ {obs.recommendation}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
