"use client";
import { useState, useEffect } from "react";
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

export default function DiagnosticPage() {
  const [selected, setSelected] = useState<string>("");
  const [mode, setMode] = useState<"fixed_set" | "time_boxed">("fixed_set");
  const [numQ, setNumQ] = useState(10);
  const [minutes, setMinutes] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<any>(null);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});
  const [finished, setFinished] = useState(false);
  const [score, setScore] = useState<any>(null);
  const [skipped, setSkipped] = useState<Record<number, boolean>>({});
  const [expanded, setExpanded] = useState<Record<number, string>>({});
  const [expandLoading, setExpandLoading] = useState<Record<number, boolean>>({});
  const [questionStartTime, setQuestionStartTime] = useState<number>(Date.now());
  const [pendingAnswer, setPendingAnswer] = useState<string | null>(null);
  const [revisionNotes, setRevisionNotes] = useState<any[] | null>(null);
  const [revisionLoading, setRevisionLoading] = useState(false);

  useEffect(() => {
    setQuestionStartTime(Date.now());
    setPendingAnswer(null);
  }, [currentQ]);

  const startSession = async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.generateQuiz({
        subject_id: selected,
        session_type: "diagnostic",
        mode,
        num_questions: numQ,
        time_minutes: minutes,
        difficulty: "mixed",
      });
      setSession(data);
      setCurrentQ(0);
      setAnswers({});
      setRevealed({});
      setSkipped({});
      setFinished(false);
      setScore(null);
      setQuestionStartTime(Date.now());
      setPendingAnswer(null);
      setRevisionNotes(null);
      setRevisionLoading(false);
    } catch (e: any) {
      setError("Failed to generate questions. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async (opt: string) => {
    if (!session || answers[currentQ]) return;
    const q = session.questions[currentQ];
    const correct = q.correct_answer === opt;
    const timeSec = Math.round((Date.now() - questionStartTime) / 1000);
    setAnswers((a) => ({ ...a, [currentQ]: opt }));
    setRevealed((r) => ({ ...r, [currentQ]: true }));
    await api.submitAnswer({
      session_id: session.session_id,
      question_hash: q.question_hash ?? `${session.session_id}_${currentQ}`,
      question_text: q.question_text,
      options: { a: q.option_a ?? "", b: q.option_b ?? "", c: q.option_c ?? "", d: q.option_d ?? "" },
      correct_answer: q.correct_answer,
      user_answer: opt,
      is_correct: correct,
      time_taken_sec: timeSec,
      subject_id: selected,
      subtopic_id: q.subtopic_id ?? selected,
    }).catch(() => {});
  };

  const skipQuestion = async () => {
    if (!session || answers[currentQ] !== undefined || skipped[currentQ]) return;
    const q = session.questions[currentQ];
    const timeSec = Math.round((Date.now() - questionStartTime) / 1000);
    setSkipped((s) => ({ ...s, [currentQ]: true }));
    setRevealed((r) => ({ ...r, [currentQ]: true }));
    await api.submitAnswer({
      session_id: session.session_id,
      question_hash: q.question_hash ?? `${session.session_id}_${currentQ}`,
      question_text: q.question_text,
      options: { a: q.option_a ?? "", b: q.option_b ?? "", c: q.option_c ?? "", d: q.option_d ?? "" },
      correct_answer: q.correct_answer,
      user_answer: null,
      is_correct: false,
      skipped: true,
      time_taken_sec: timeSec,
      subject_id: selected,
      subtopic_id: q.subtopic_id ?? selected,
    }).catch(() => {});
  };

  const finishSession = async () => {
    if (!session) return;
    try {
      const result = await api.closeSession(session.session_id);
      setScore(result);
    } catch (e) {}
    setFinished(true);
    setRevisionLoading(true);
    try {
      const data = await api.getRevisionNotes(session.session_id);
      setRevisionNotes(data.notes ?? []);
    } catch {
      setRevisionNotes([]);
    } finally {
      setRevisionLoading(false);
    }
  };

  const diveDeeperInto = async (idx: number) => {
    if (!session || expanded[idx] || expandLoading[idx]) return;
    const q = session.questions[idx];
    setExpandLoading((l) => ({ ...l, [idx]: true }));
    try {
      const data = await api.expandConcept({
        session_id: session.session_id,
        question_hash: q.question_hash ?? `${session.session_id}_${idx}`,
        question_text: q.question_text,
        subtopic_id: q.subtopic_id ?? selected,
        subject_id: selected,
      });
      setExpanded((e) => ({ ...e, [idx]: data.explanation }));
    } catch {
      setExpanded((e) => ({ ...e, [idx]: "Unable to load deep dive. Please try again." }));
    } finally {
      setExpandLoading((l) => ({ ...l, [idx]: false }));
    }
  };

  if (!session) {
    return (
      <div className="max-w-xl space-y-6">
        <h1 className="text-2xl font-bold">Diagnostic Session</h1>
        <p className="text-gray-400">Configure your diagnostic quiz. Questions are generated from your study material.</p>

        {error && (
          <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-red-300 text-sm">{error}</div>
        )}

        <div>
          <label className="block text-sm text-gray-400 mb-2">Subject</label>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white"
          >
            <option value="">Select subject...</option>
            {SUBJECTS.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>

        <div className="flex gap-4">
          {(["fixed_set", "time_boxed"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
                mode === m ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-gray-700 text-gray-400"
              }`}
            >
              {m === "fixed_set" ? "Fixed Questions" : "Time-boxed"}
            </button>
          ))}
        </div>

        <div className="flex gap-4">
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-2">Questions</label>
            <input type="number" min={5} max={30} value={numQ} onChange={(e) => setNumQ(+e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white" />
          </div>
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-2">Minutes</label>
            <input type="number" min={5} max={90} value={minutes} onChange={(e) => setMinutes(+e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white" />
          </div>
        </div>

        <button
          onClick={startSession}
          disabled={!selected || loading}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium py-3 rounded-lg transition-colors"
        >
          {loading ? "Generating questions... (15–30s)" : "Start Diagnostic"}
        </button>
      </div>
    );
  }

  if (finished) {
    const total = session.questions.length;
    const skippedCount = Object.keys(skipped).length;
    const correct = Object.entries(answers).filter(([idx, opt]) =>
      session.questions[parseInt(idx)]?.correct_answer === opt
    ).length;
    const attempted = total - skippedCount;
    return (
      <div className="max-w-xl space-y-6">
        <h1 className="text-2xl font-bold">Session Complete</h1>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center space-y-2">
          <div className="text-5xl font-bold text-amber-400">
            {attempted > 0 ? Math.round((correct / attempted) * 100) : 0}%
          </div>
          <div className="text-gray-400">{correct} / {attempted} correct</div>
          {skippedCount > 0 && (
            <div className="text-gray-500 text-sm">{skippedCount} skipped</div>
          )}
        </div>
        <p className="text-gray-400 text-sm">Session saved. Run Sync & Plan on the dashboard to update your profile.</p>

        {revisionLoading && (
          <div className="text-gray-500 text-sm text-center animate-pulse">Generating revision notes for wrong answers...</div>
        )}

        {!revisionLoading && revisionNotes && revisionNotes.length === 0 && (
          <div className="bg-green-950/30 border border-green-900/50 rounded-xl p-4 text-center">
            <p className="text-green-400 font-medium">Clean sweep — nothing to review!</p>
          </div>
        )}

        {!revisionLoading && revisionNotes && revisionNotes.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-base font-semibold text-red-300">Concepts to Review ({revisionNotes.length})</h2>
            {revisionNotes.map((n, i) => (
              <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
                <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{n.question_text}</p>
                <div className="flex gap-4 text-xs font-medium">
                  <span className="text-red-400">You chose: ({n.user_answer})</span>
                  <span className="text-green-400">Correct: ({n.correct_answer})</span>
                </div>
                <p className="text-sm text-amber-200 leading-relaxed border-t border-gray-700 pt-2">{n.explanation}</p>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-4">
          <button onClick={() => { setSession(null); setFinished(false); }}
            className="flex-1 bg-blue-600 hover:bg-blue-500 text-white py-2 rounded-lg text-sm">
            Start Another
          </button>
          <a href="/" className="flex-1 text-center border border-gray-700 hover:border-gray-500 text-gray-300 py-2 rounded-lg text-sm">
            Dashboard
          </a>
        </div>
      </div>
    );
  }

  const q = session.questions[currentQ];
  const options = [
    { key: "a", text: q.option_a ?? "" },
    { key: "b", text: q.option_b ?? "" },
    { key: "c", text: q.option_c ?? "" },
    { key: "d", text: q.option_d ?? "" },
  ];
  const isLast = currentQ === session.questions.length - 1;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Q {currentQ + 1} / {session.questions.length}</h2>
        <span className="text-sm text-gray-400">{SUBJECTS.find(s => s.id === selected)?.name}</span>
      </div>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <p className="text-white leading-relaxed whitespace-pre-wrap">{q.question_text}</p>
      </div>

      <div className="space-y-3">
        {options.map((opt) => {
          const chosen = answers[currentQ] === opt.key;
          const isCorrect = q.correct_answer === opt.key;
          const show = revealed[currentQ];
          return (
            <button
              key={opt.key}
              onClick={() => {
                if (!answers[currentQ] && !skipped[currentQ])
                  setPendingAnswer(pendingAnswer === opt.key ? null : opt.key);
              }}
              disabled={!!answers[currentQ] || !!skipped[currentQ]}
              className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                show && isCorrect ? "border-green-500 bg-green-500/10 text-green-300" :
                show && chosen && !isCorrect ? "border-red-500 bg-red-500/10 text-red-300" :
                !show && pendingAnswer === opt.key ? "border-blue-500 bg-blue-500/10 text-blue-200" :
                "border-gray-700 hover:border-gray-500 text-gray-200"
              }`}
            >
              <span className="font-medium mr-3 text-gray-500">({opt.key})</span>{opt.text}
            </button>
          );
        })}
      </div>

      {!answers[currentQ] && !skipped[currentQ] && !pendingAnswer && (
        <button
          onClick={skipQuestion}
          className="text-sm text-gray-500 hover:text-gray-300 border border-gray-700 hover:border-gray-500 px-4 py-2 rounded-lg transition-colors"
        >
          Skip →
        </button>
      )}

      {pendingAnswer && !answers[currentQ] && !skipped[currentQ] && (
        <button
          onClick={() => { submitAnswer(pendingAnswer); setPendingAnswer(null); }}
          className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-3 rounded-lg transition-colors"
        >
          Submit Answer
        </button>
      )}

      {skipped[currentQ] && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
          <p className="text-gray-500 text-sm">Skipped — correct answer was <span className="text-green-400 font-medium">({q.correct_answer})</span></p>
        </div>
      )}

      {revealed[currentQ] && !skipped[currentQ] && q.explanation && (
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
            className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg">
            Next Question →
          </button>
        )}
        {revealed[currentQ] && isLast && (
          <button onClick={finishSession}
            className="bg-green-600 hover:bg-green-500 text-white px-6 py-2 rounded-lg">
            Finish & Save Session
          </button>
        )}
      </div>
    </div>
  );
}
