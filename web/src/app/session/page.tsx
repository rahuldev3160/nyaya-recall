"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function SessionPage() {
  const [plan, setPlan] = useState<any>(null);
  const [activeSession, setActiveSession] = useState<number | null>(null);
  const [quiz, setQuiz] = useState<any>(null);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finished, setFinished] = useState(false);
  const [expanded, setExpanded] = useState<Record<number, string>>({});
  const [expandLoading, setExpandLoading] = useState<Record<number, boolean>>({});

  useEffect(() => { api.getPlan().then(setPlan).catch(() => {}); }, []);

  const startSession = async (session: any, index: number) => {
    setLoading(true);
    setError(null);
    setActiveSession(index);
    try {
      const data = await api.generateQuiz({
        subject_id: session.subject_id,
        topic_id: session.topic_id,
        subtopic_id: session.subtopic_id,
        session_type: "adaptive",
        mode: "fixed_set",
        num_questions: session.num_questions ?? 10,
        difficulty: session.difficulty ?? "mixed",
        format: session.format,
        show_notes: session.format === "notes_then_quiz",
      });
      setQuiz(data);
      setCurrentQ(0);
      setAnswers({});
      setRevealed({});
      setFinished(false);
    } catch (e: any) {
      setError("Failed to generate session questions. Please try again.");
      setActiveSession(null);
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async (opt: string) => {
    if (!quiz || answers[currentQ]) return;
    const q = quiz.questions[currentQ];
    setAnswers((a) => ({ ...a, [currentQ]: opt }));
    setRevealed((r) => ({ ...r, [currentQ]: true }));
    await api.submitAnswer({
      session_id: quiz.session_id,
      question_hash: `${quiz.session_id}_${currentQ}`,
      question_text: q.question_text,
      options: { a: q.option_a ?? "", b: q.option_b ?? "", c: q.option_c ?? "", d: q.option_d ?? "" },
      correct_answer: q.correct_answer,
      user_answer: opt,
      is_correct: q.correct_answer === opt,
      time_taken_sec: 0,
      subject_id: plan?.sessions?.[activeSession!]?.subject_id,
      subtopic_id: q.subtopic_id ?? plan?.sessions?.[activeSession!]?.subtopic_id,
    }).catch(() => {});
  };

  const finishSession = async () => {
    if (!quiz) return;
    try { await api.closeSession(quiz.session_id); } catch {}
    setFinished(true);
  };

  const diveDeeperInto = async (idx: number) => {
    if (!quiz || expanded[idx] || expandLoading[idx]) return;
    const q = quiz.questions[idx];
    const sessionInfo = plan?.sessions?.[activeSession!];
    setExpandLoading((l) => ({ ...l, [idx]: true }));
    try {
      const data = await api.expandConcept({
        session_id: quiz.session_id,
        question_hash: q.question_hash ?? `${quiz.session_id}_${idx}`,
        question_text: q.question_text,
        subtopic_id: q.subtopic_id ?? sessionInfo?.subtopic_id ?? "",
        subject_id: sessionInfo?.subject_id ?? "",
      });
      setExpanded((e) => ({ ...e, [idx]: data.explanation }));
    } catch {
      setExpanded((e) => ({ ...e, [idx]: "Unable to load deep dive. Please try again." }));
    } finally {
      setExpandLoading((l) => ({ ...l, [idx]: false }));
    }
  };

  if (!plan || plan.message) {
    return (
      <div className="max-w-xl space-y-4">
        <h1 className="text-2xl font-bold">Today&apos;s Sessions</h1>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-gray-400">
          <p className="mb-3">{plan?.message ?? "No plan for today."}</p>
          <p className="text-sm">Go to the <a href="/planner" className="text-amber-400 hover:underline">Planner</a> to generate today&apos;s study sessions, or complete a diagnostic first and run Sync & Plan from the dashboard.</p>
        </div>
      </div>
    );
  }

  if (finished) {
    return (
      <div className="max-w-xl space-y-6">
        <h1 className="text-2xl font-bold">Session Complete</h1>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center">
          <p className="text-green-400 text-lg font-semibold mb-2">Saved!</p>
          <p className="text-gray-400 text-sm">Session recorded. Keep going with the next session or sync your progress.</p>
        </div>
        <div className="flex gap-4">
          <button onClick={() => { setQuiz(null); setFinished(false); setActiveSession(null); }}
            className="flex-1 bg-green-600 hover:bg-green-500 text-white py-2 rounded-lg text-sm">
            Next Session
          </button>
          <a href="/" className="flex-1 text-center border border-gray-700 text-gray-300 hover:text-white py-2 rounded-lg text-sm">
            Dashboard
          </a>
        </div>
      </div>
    );
  }

  if (!quiz) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Today&apos;s Sessions</h1>

        {error && (
          <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-red-300 text-sm">{error}</div>
        )}

        {(!plan.sessions || plan.sessions.length === 0) ? (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-gray-400">
            <p>No sessions in today&apos;s plan.</p>
            <a href="/planner" className="text-amber-400 text-sm hover:underline mt-2 block">Regenerate plan →</a>
          </div>
        ) : (
          <div className="space-y-3">
            {plan.sessions.map((s: any, i: number) => (
              <div key={i} className="flex items-center gap-4 p-4 bg-gray-900 rounded-xl border border-gray-800">
                <div className="flex-1">
                  <div className="font-medium text-white">
                    {s.subject_id?.replace(/_/g, " ")} → {s.subtopic_id?.replace(/_/g, " ")}
                  </div>
                  <div className="text-sm text-gray-500 mt-1">
                    {s.format?.replace(/_/g, " ")} · {s.estimated_minutes} min
                    {s.difficulty && s.difficulty !== "mixed" && (
                      <span className="ml-2 text-amber-400">· {s.difficulty}</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => startSession(s, i)}
                  disabled={loading}
                  className="bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm"
                >
                  {loading && activeSession === i ? "Generating..." : "Start"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  const q = quiz.questions[currentQ];
  const options = [
    { key: "a", text: q.option_a ?? "" }, { key: "b", text: q.option_b ?? "" },
    { key: "c", text: q.option_c ?? "" }, { key: "d", text: q.option_d ?? "" },
  ];
  const isLast = currentQ === quiz.questions.length - 1;

  return (
    <div className="max-w-2xl space-y-6">
      {quiz.notes_summary && !answers[0] && (
        <div className="bg-blue-950 border border-blue-800 rounded-xl p-5">
          <h3 className="text-blue-300 font-semibold mb-3">Key Concepts — Read Before Quiz</h3>
          <p className="text-gray-200 text-sm whitespace-pre-wrap">{quiz.notes_summary}</p>
        </div>
      )}

      <div className="flex justify-between items-center">
        <h2 className="font-semibold">Q {currentQ + 1} / {quiz.questions.length}</h2>
        <span className="text-gray-400 text-sm">{plan.sessions?.[activeSession!]?.subject_id?.replace(/_/g, " ")}</span>
      </div>

      <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
        <p className="text-white leading-relaxed">{q.question_text}</p>
      </div>

      <div className="space-y-3">
        {options.map((opt) => {
          const chosen = answers[currentQ] === opt.key;
          const correct = q.correct_answer === opt.key;
          const show = revealed[currentQ];
          return (
            <button key={opt.key} onClick={() => submitAnswer(opt.key)} disabled={!!answers[currentQ]}
              className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                show && correct ? "border-green-500 bg-green-500/10 text-green-300" :
                show && chosen ? "border-red-500 bg-red-500/10 text-red-300" :
                "border-gray-700 hover:border-gray-500 text-gray-200"
              }`}>
              <span className="font-medium mr-3 text-gray-500">({opt.key})</span>{opt.text}
            </button>
          );
        })}
      </div>

      {revealed[currentQ] && q.explanation && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-3">
          <p className="text-amber-300 text-sm font-medium mb-1">Explanation</p>
          <p className="text-gray-300 text-sm">{q.explanation}</p>

          {!expanded[currentQ] && (
            <button
              onClick={() => diveDeeperInto(currentQ)}
              disabled={expandLoading[currentQ]}
              className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50 flex items-center gap-1 transition-colors"
            >
              {expandLoading[currentQ] ? "Loading deep dive..." : "Dive deeper →"}
            </button>
          )}

          {expanded[currentQ] && (
            <div className="border-t border-gray-700 pt-3 mt-2">
              <p className="text-blue-300 text-xs font-medium mb-2">Deep Dive</p>
              <div className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">
                {expanded[currentQ]}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-4">
        {revealed[currentQ] && !isLast && (
          <button onClick={() => setCurrentQ(currentQ + 1)}
            className="bg-green-600 hover:bg-green-500 text-white px-6 py-2 rounded-lg">
            Next →
          </button>
        )}
        {revealed[currentQ] && isLast && (
          <button onClick={finishSession}
            className="bg-amber-600 hover:bg-amber-500 text-white px-6 py-2 rounded-lg">
            Finish Session
          </button>
        )}
      </div>
    </div>
  );
}
