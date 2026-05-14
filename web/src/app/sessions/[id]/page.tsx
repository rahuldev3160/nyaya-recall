"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

export default function SessionReviewPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<number, string>>({});
  const [expandLoading, setExpandLoading] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (!id) return;
    api.getSession(id)
      .then(setData)
      .catch(() => setError("Session not found."))
      .finally(() => setLoading(false));
  }, [id]);

  const diveDeeperInto = async (idx: number, answer: any) => {
    if (expanded[idx] || expandLoading[idx]) return;
    setExpandLoading((l) => ({ ...l, [idx]: true }));
    try {
      const result = await api.expandConcept({
        session_id: id,
        question_hash: answer.question_hash,
        question_text: answer.question_text,
        subtopic_id: answer.subtopic_id ?? "",
        subject_id: data?.session?.subject_id ?? "",
      });
      setExpanded((e) => ({ ...e, [idx]: result.explanation }));
    } catch {
      setExpanded((e) => ({ ...e, [idx]: "Unable to load deep dive. Try again." }));
    } finally {
      setExpandLoading((l) => ({ ...l, [idx]: false }));
    }
  };

  if (loading) return <p className="text-gray-500 text-sm p-6">Loading session...</p>;
  if (error) return (
    <div className="space-y-4">
      <a href="/sessions" className="text-gray-500 hover:text-gray-300 text-sm">← History</a>
      <p className="text-red-400">{error}</p>
    </div>
  );

  const session = data?.session;
  const answers: any[] = data?.answers ?? [];
  const correct = answers.filter((a) => a.is_correct).length;
  const skipped = answers.filter((a) => a.skipped).length;
  const attempted = answers.length - skipped;
  const score = attempted > 0 ? Math.round((correct / attempted) * 100) : 0;

  const fmt = (iso: string) => new Date(iso).toLocaleString("en-IN", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
  });

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-4">
        <a href="/sessions" className="text-gray-500 hover:text-gray-300 text-sm">← History</a>
        <h1 className="text-xl font-bold capitalize">
          {session?.subject_id?.replace(/_/g, " ")} Review
        </h1>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex gap-6">
        <div className="text-center">
          <div className={`text-3xl font-bold ${score >= 70 ? "text-green-400" : score >= 50 ? "text-amber-400" : "text-red-400"}`}>
            {score}%
          </div>
          <div className="text-xs text-gray-500 mt-1">score</div>
        </div>
        <div className="text-center">
          <div className="text-xl font-semibold text-white">{correct}/{attempted}</div>
          <div className="text-xs text-gray-500 mt-1">correct</div>
        </div>
        {skipped > 0 && (
          <div className="text-center">
            <div className="text-xl font-semibold text-gray-400">{skipped}</div>
            <div className="text-xs text-gray-500 mt-1">skipped</div>
          </div>
        )}
        <div className="ml-auto text-right text-sm text-gray-500">
          {session?.start_time ? fmt(session.start_time) : ""}
        </div>
      </div>

      <div className="space-y-4">
        {answers.map((a, idx) => {
          const isCorrect = a.is_correct;
          const isSkipped = a.skipped;
          const options = a.options ? (typeof a.options === "string" ? JSON.parse(a.options) : a.options) : {};

          return (
            <div key={idx} className={`rounded-xl border p-5 space-y-3 ${
              isSkipped ? "border-gray-700 bg-gray-900/50" :
              isCorrect ? "border-green-800 bg-green-950/20" :
              "border-red-800 bg-red-950/20"
            }`}>
              <div className="flex items-start gap-3">
                <span className={`mt-0.5 text-sm font-bold shrink-0 ${
                  isSkipped ? "text-gray-500" : isCorrect ? "text-green-400" : "text-red-400"
                }`}>
                  Q{idx + 1} {isSkipped ? "—" : isCorrect ? "✓" : "✗"}
                </span>
                <p className="text-white text-sm leading-relaxed whitespace-pre-wrap">{a.question_text}</p>
              </div>

              {!isSkipped && (
                <div className="space-y-1.5 pl-8">
                  {Object.entries(options).map(([key, text]) => {
                    const isUserChoice = a.user_answer === key;
                    const isCorrectOpt = a.correct_answer === key;
                    return (
                      <div key={key} className={`text-sm px-3 py-1.5 rounded-lg ${
                        isCorrectOpt ? "bg-green-500/10 text-green-300 border border-green-700" :
                        isUserChoice && !isCorrectOpt ? "bg-red-500/10 text-red-300 border border-red-800" :
                        "text-gray-500"
                      }`}>
                        <span className="font-medium mr-2">({key})</span>{text as string}
                        {isCorrectOpt && <span className="ml-2 text-xs text-green-500">✓ correct</span>}
                        {isUserChoice && !isCorrectOpt && <span className="ml-2 text-xs text-red-500">your answer</span>}
                      </div>
                    );
                  })}
                </div>
              )}

              {isSkipped && (
                <p className="pl-8 text-sm text-gray-600">Skipped — correct answer: ({a.correct_answer})</p>
              )}

              {a.explanation && (
                <div className="pl-8 space-y-2">
                  <p className="text-amber-300 text-xs font-medium">Explanation</p>
                  <p className="text-gray-300 text-sm leading-relaxed">{a.explanation}</p>

                  {!expanded[idx] && (
                    <button
                      onClick={() => diveDeeperInto(idx, a)}
                      disabled={expandLoading[idx]}
                      className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
                    >
                      {expandLoading[idx] ? "Loading..." : "Dive deeper →"}
                    </button>
                  )}
                  {expanded[idx] && (
                    <div className="border-t border-gray-700 pt-2 mt-2">
                      <p className="text-blue-300 text-xs font-medium mb-1">Deep Dive</p>
                      <p className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">{expanded[idx]}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex gap-4 pt-2">
        <a href="/sessions" className="border border-gray-700 text-gray-300 hover:text-white px-4 py-2 rounded-lg text-sm">
          ← All Sessions
        </a>
        <a href="/session" className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg text-sm">
          Today&apos;s Sessions
        </a>
      </div>
    </div>
  );
}
