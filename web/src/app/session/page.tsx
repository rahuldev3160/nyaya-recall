"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { api } from "@/lib/api";

const notesMarkdownComponents: Partial<Components> = {
  h2: ({ children, ...props }) => (
    <h2 className="text-lg font-semibold text-blue-200 mt-4 first:mt-0 mb-2" {...props}>{children}</h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="text-base font-semibold text-blue-100 mt-4 mb-2" {...props}>{children}</h3>
  ),
  h4: ({ children, ...props }) => (
    <h4 className="text-sm font-medium text-gray-200 mt-3 mb-1.5" {...props}>{children}</h4>
  ),
  p: ({ children, ...props }) => (
    <p className="text-gray-200 text-sm leading-relaxed mb-2 last:mb-0" {...props}>{children}</p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="list-disc pl-5 text-gray-200 text-sm space-y-1 mb-3" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="list-decimal pl-5 text-gray-200 text-sm space-y-1 mb-3" {...props}>{children}</ol>
  ),
  li: ({ children, ...props }) => (
    <li className="leading-relaxed" {...props}>{children}</li>
  ),
  a: ({ children, ...props }) => (
    <a className="text-blue-400 hover:text-blue-300 underline underline-offset-2" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
  ),
  strong: ({ children, ...props }) => (
    <strong className="font-semibold text-gray-100" {...props}>{children}</strong>
  ),
  em: ({ children, ...props }) => (
    <em className="italic text-gray-300" {...props}>{children}</em>
  ),
  code: ({ children, ...props }) => (
    <code className="rounded bg-gray-900/80 px-1.5 py-0.5 text-xs text-amber-100/90" {...props}>{children}</code>
  ),
  hr: () => <hr className="border-gray-700 my-4" />,
  blockquote: ({ children, ...props }) => (
    <blockquote className="border-l-2 border-blue-600 pl-3 text-gray-400 text-sm italic my-2" {...props}>{children}</blockquote>
  ),
};

type UserNotesState = { confusion: string; mnemonic: string; still_weak: boolean };

const ACTIVE_QUIZ_KEY = "upsc_active_quiz";

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
  const [revisionNotes, setRevisionNotes] = useState<any[] | null>(null);
  const [revisionLoading, setRevisionLoading] = useState(false);

  const [pendingAnswer, setPendingAnswer] = useState<string | null>(null);
  const [completedSessions, setCompletedSessions] = useState<Set<string>>(new Set());
  const [notesPanelOpen, setNotesPanelOpen] = useState(false);
  const [userNotes, setUserNotes] = useState<UserNotesState>({
    confusion: "",
    mnemonic: "",
    still_weak: false,
  });
  // Per-question note text keyed by question index
  const [perQuestionNotes, setPerQuestionNotes] = useState<Record<number, string>>({});
  const notesDirty = useRef(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const perQuestionSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const restoredRef = useRef(false);

  const [notesExplainLoading, setNotesExplainLoading] = useState(false);
  const [notesExplainText, setNotesExplainText] = useState<string | null>(null);
  const [notesExplainErr, setNotesExplainErr] = useState<string | null>(null);

  useEffect(() => {
    api.getPlan().then(setPlan).catch(() => {});
    api.getPlanStatus()
      .then((s: { completed_subtopics: string[] }) => {
        if (s?.completed_subtopics?.length) {
          setCompletedSessions(new Set(s.completed_subtopics));
        }
      })
      .catch(() => {});
  }, []);

  // Restore completed session indices from localStorage on mount (keyed by date so it resets each day)
  useEffect(() => {
    try {
      const key = `upsc_completed_${new Date().toISOString().split("T")[0]}`;
      const raw = localStorage.getItem(key);
      if (raw) setCompletedSessions(new Set(JSON.parse(raw) as number[]));
    } catch {}
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Save completed session indices to localStorage whenever they change
  useEffect(() => {
    if (completedSessions.size === 0) return;
    try {
      const key = `upsc_completed_${new Date().toISOString().split("T")[0]}`;
      localStorage.setItem(key, JSON.stringify([...completedSessions]));
    } catch {}
  }, [completedSessions]);

  // Restore active in-progress quiz from localStorage once plan loads (runs once per page load)
  useEffect(() => {
    if (!plan || restoredRef.current || quiz) return;
    restoredRef.current = true;
    try {
      const raw = localStorage.getItem(ACTIVE_QUIZ_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw) as {
        session_id: string;
        questions: any[];
        notes_summary: string | null;
        currentQ: number;
        answers: Record<number, string>;
        revealed: Record<number, boolean>;
        activeSession: number;
      };
      if (!saved.session_id || !Array.isArray(saved.questions) || !saved.questions.length) {
        localStorage.removeItem(ACTIVE_QUIZ_KEY);
        return;
      }
      api.getSession(saved.session_id)
        .then((data) => {
          if (data?.session && !data.session.end_time) {
            setQuiz({ session_id: saved.session_id, questions: saved.questions, notes_summary: saved.notes_summary });
            setCurrentQ(saved.currentQ ?? 0);
            setAnswers(saved.answers ?? {});
            setRevealed(saved.revealed ?? {});
            setActiveSession(saved.activeSession ?? null);
          } else {
            localStorage.removeItem(ACTIVE_QUIZ_KEY);
          }
        })
        .catch(() => localStorage.removeItem(ACTIVE_QUIZ_KEY));
    } catch {
      localStorage.removeItem(ACTIVE_QUIZ_KEY);
    }
  }, [plan]); // eslint-disable-line react-hooks/exhaustive-deps

  // Persist active quiz state to localStorage after every meaningful state change
  useEffect(() => {
    if (!quiz?.session_id || finished) return;
    try {
      localStorage.setItem(
        ACTIVE_QUIZ_KEY,
        JSON.stringify({
          session_id: quiz.session_id,
          questions: quiz.questions,
          notes_summary: quiz.notes_summary ?? null,
          currentQ,
          answers,
          revealed,
          activeSession,
        })
      );
    } catch {}
  }, [quiz, currentQ, answers, revealed, activeSession, finished]);

  const sessionMeta = plan?.sessions?.[activeSession ?? -1];

  const flushUserNotes = useCallback(async () => {
    if (!quiz?.session_id || activeSession === null) return;
    const s = plan?.sessions?.[activeSession];
    if (!s?.subtopic_id) return;
    try {
      // Flush session-level flags + current per-question note in one call
      const noteText = perQuestionNotes[currentQ] ?? "";
      await api.putUserNotes(quiz.session_id, {
        subtopic_id: s.subtopic_id,
        subject_id: s.subject_id ?? "",
        confusion: userNotes.confusion,
        mnemonic: userNotes.mnemonic,
        still_weak: userNotes.still_weak,
        question_context_index: currentQ,
        note_text: noteText,
      });
      notesDirty.current = false;
    } catch {
      /* ignore */
    }
  }, [quiz?.session_id, activeSession, plan, userNotes, currentQ, perQuestionNotes]);

  useEffect(() => {
    setPendingAnswer(null);
    // Per-question note: flush any pending save for the previous question before switching
    if (perQuestionSaveTimer.current) clearTimeout(perQuestionSaveTimer.current);
  }, [currentQ]);

  useEffect(() => {
    if (!quiz?.session_id) return;
    setNotesPanelOpen(false);
    notesDirty.current = false;
    setNotesExplainText(null);
    setNotesExplainErr(null);
    setPerQuestionNotes({});
    api
      .getUserNotes(quiz.session_id)
      .then((d) => {
        setUserNotes({
          confusion: d.confusion || "",
          mnemonic: d.mnemonic || "",
          still_weak: !!d.still_weak,
        });
        // Load per-question notes returned by the backend (keyed by string index)
        if (d.per_question_notes && typeof d.per_question_notes === "object") {
          const loaded: Record<number, string> = {};
          for (const [k, v] of Object.entries(d.per_question_notes)) {
            loaded[parseInt(k)] = (v as string) || "";
          }
          setPerQuestionNotes(loaded);
        }
      })
      .catch(() => {});
  }, [quiz?.session_id]);

  useEffect(() => {
    if (!quiz?.session_id || activeSession === null || !notesDirty.current) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      const s = plan?.sessions?.[activeSession];
      if (!s?.subtopic_id) return;
      const noteText = perQuestionNotes[currentQ] ?? "";
      api
        .putUserNotes(quiz.session_id, {
          subtopic_id: s.subtopic_id,
          subject_id: s.subject_id ?? "",
          confusion: userNotes.confusion,
          mnemonic: userNotes.mnemonic,
          still_weak: userNotes.still_weak,
          question_context_index: currentQ,
          note_text: noteText,
        })
        .then(() => {
          notesDirty.current = false;
        })
        .catch(() => {});
    }, 700);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [userNotes, perQuestionNotes, quiz?.session_id, currentQ, activeSession, plan]);

  const patchUserNotes = (patch: Partial<UserNotesState>) => {
    notesDirty.current = true;
    setUserNotes((n) => ({ ...n, ...patch }));
  };

  const startSession = async (session: any, index: number) => {
    setLoading(true);
    setError(null);
    setPendingAnswer(null);
    setActiveSession(index);
    setRevisionNotes(null);
    setRevisionLoading(false);
    setPerQuestionNotes({});
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
    try { localStorage.removeItem(ACTIVE_QUIZ_KEY); } catch {}
    await flushUserNotes();
    try {
      await api.closeSession(quiz.session_id);
    } catch {
      /* ignore */
    }
    if (activeSession !== null) {
      const subtopicId = plan?.sessions?.[activeSession]?.subtopic_id;
      if (subtopicId) {
        setCompletedSessions((prev) => { const next = new Set(prev); next.add(subtopicId); return next; });
      }
    }
    setFinished(true);
    setRevisionLoading(true);
    try {
      const data = await api.getRevisionNotes(quiz.session_id);
      setRevisionNotes(data.notes ?? []);
    } catch {
      setRevisionNotes([]);
    } finally {
      setRevisionLoading(false);
    }
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

  const explainNotesSelection = async () => {
    const sel = typeof window !== "undefined" ? window.getSelection()?.toString().trim() ?? "" : "";
    if (!quiz || !sessionMeta?.subtopic_id) return;
    if (sel.length < 12) {
      setNotesExplainErr("Select a phrase in Key Concepts (at least ~12 characters), then try again.");
      setNotesExplainText(null);
      return;
    }
    setNotesExplainErr(null);
    setNotesExplainLoading(true);
    try {
      const data = await api.expandNotesSelection({
        selected_excerpt: sel,
        subtopic_id: sessionMeta.subtopic_id,
        subject_id: sessionMeta.subject_id ?? "",
      });
      setNotesExplainText(data.explanation);
    } catch {
      setNotesExplainErr("Could not load explanation. Try a shorter selection.");
      setNotesExplainText(null);
    } finally {
      setNotesExplainLoading(false);
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
    const total = quiz?.questions?.length ?? 0;
    const correct = Object.entries(answers).filter(([idx, opt]) =>
      quiz?.questions?.[parseInt(idx)]?.correct_answer === opt
    ).length;
    return (
      <div className="max-w-xl space-y-6">
        <h1 className="text-2xl font-bold">Session Complete</h1>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center space-y-2">
          <p className="text-green-400 text-lg font-semibold">Saved!</p>
          <div className="text-4xl font-bold text-amber-400">
            {total > 0 ? Math.round((correct / total) * 100) : 0}%
          </div>
          <div className="text-gray-400">{correct} / {total} correct</div>
        </div>
        <p className="text-gray-400 text-sm">Session saved. Run Sync &amp; Plan on the dashboard to update your profile.</p>

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
          <button
            onClick={() => {
              setQuiz(null);
              setFinished(false);
              setActiveSession(null);
              setRevisionNotes(null);
              setPerQuestionNotes({});
            }}
            className="flex-1 bg-green-600 hover:bg-green-500 text-white py-2 rounded-lg text-sm"
          >
            Next Session
          </button>
          <a
            href="/"
            className="flex-1 text-center border border-gray-700 text-gray-300 hover:text-white py-2 rounded-lg text-sm"
          >
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

        {!plan.sessions || plan.sessions.length === 0 ? (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-gray-400">
            <p>No sessions in today&apos;s plan.</p>
            <a href="/planner" className="text-amber-400 text-sm hover:underline mt-2 block">
              Regenerate plan →
            </a>
          </div>
        ) : (
          <div className="space-y-3">
            {plan.sessions.map((s: any, i: number) => {
              const done = completedSessions.has(s.subtopic_id);
              return (
                <div key={i} className={`flex items-center gap-4 p-4 rounded-xl border ${done ? "bg-green-950/30 border-green-900/50" : "bg-gray-900 border-gray-800"}`}>
                  <div className="flex-1">
                    <div className={`font-medium ${done ? "text-green-300" : "text-white"}`}>
                      {done && <span className="mr-2">✓</span>}
                      {s.subject_id?.replace(/_/g, " ")} → {s.subtopic_id?.replace(/_/g, " ")}
                    </div>
                    <div className="text-sm text-gray-500 mt-1">
                      {s.format?.replace(/_/g, " ")} · {s.estimated_minutes} min
                      {s.difficulty && s.difficulty !== "mixed" && (
                        <span className="ml-2 text-amber-400">· {
                          s.difficulty === "easy" ? "Easy difficulty" :
                          s.difficulty === "medium" ? "Medium difficulty" :
                          s.difficulty === "hard" ? "Hard difficulty" :
                          s.difficulty
                        }</span>
                      )}
                    </div>
                  </div>
                  {done ? (
                    <span className="text-green-400 text-sm font-medium px-4 py-2">Completed</span>
                  ) : (
                    <button
                      onClick={() => startSession(s, i)}
                      disabled={loading}
                      className="bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm"
                    >
                      {loading && activeSession === i ? "Generating..." : "Start"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  const q = quiz.questions[currentQ];
  const options = [
    { key: "a", text: q.option_a ?? "" },
    { key: "b", text: q.option_b ?? "" },
    { key: "c", text: q.option_c ?? "" },
    { key: "d", text: q.option_d ?? "" },
  ];
  const isLast = currentQ === quiz.questions.length - 1;

  return (
    <div className="relative min-h-[60vh]">
      <div className="max-w-2xl space-y-6 pb-24">
        {quiz.notes_summary && !answers[0] && (
          <div className="bg-blue-950 border border-blue-800 rounded-xl p-5">
            <h3 className="text-blue-300 font-semibold mb-3">Key Concepts — Read Before Quiz</h3>
            <div className="max-h-[50vh] overflow-y-auto pr-1 text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={notesMarkdownComponents}>
                {quiz.notes_summary}
              </ReactMarkdown>
            </div>
            <div className="mt-4 pt-3 border-t border-blue-800/60 space-y-2">
              <p className="text-xs text-blue-200/80">
                Select text above, then run an on-demand deep dive (uses a fast model call only when you click).
              </p>
              <button
                type="button"
                onClick={explainNotesSelection}
                disabled={notesExplainLoading}
                className="text-sm bg-blue-800 hover:bg-blue-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg"
              >
                {notesExplainLoading ? "Explaining…" : "Explain selected text"}
              </button>
              {notesExplainErr && <p className="text-xs text-red-400">{notesExplainErr}</p>}
              {notesExplainText && (
                <div className="mt-2 rounded-lg bg-gray-950/80 border border-blue-900/50 p-3 text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">
                  {notesExplainText}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="flex justify-between items-center">
          <h2 className="font-semibold">Q {currentQ + 1} / {quiz.questions.length}</h2>
          <span className="text-gray-400 text-sm">
            {plan.sessions?.[activeSession!]?.subject_id?.replace(/_/g, " ")}
          </span>
        </div>

        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
          <p className="text-white leading-relaxed whitespace-pre-wrap">{q.question_text}</p>
        </div>

        <div className="space-y-3">
          {options.map((opt) => {
            const chosen = answers[currentQ] === opt.key;
            const correct = q.correct_answer === opt.key;
            const show = revealed[currentQ];
            return (
              <button
                key={opt.key}
                onClick={() => {
                  if (!answers[currentQ]) setPendingAnswer(pendingAnswer === opt.key ? null : opt.key);
                }}
                disabled={!!answers[currentQ]}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                  show && correct
                    ? "border-green-500 bg-green-500/10 text-green-300"
                    : show && chosen
                      ? "border-red-500 bg-red-500/10 text-red-300"
                      : !show && pendingAnswer === opt.key
                        ? "border-blue-500 bg-blue-500/10 text-blue-200"
                        : "border-gray-700 hover:border-gray-500 text-gray-200"
                }`}
              >
                <span className="font-medium mr-3 text-gray-500">({opt.key})</span>
                {opt.text}
              </button>
            );
          })}
        </div>

        {pendingAnswer && !answers[currentQ] && (
          <button
            onClick={() => { submitAnswer(pendingAnswer); setPendingAnswer(null); }}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-3 rounded-lg transition-colors"
          >
            Submit Answer
          </button>
        )}

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
          {currentQ > 0 && (
            <button onClick={() => setCurrentQ(currentQ - 1)}
              className="border border-gray-700 hover:border-gray-500 text-gray-300 hover:text-white px-4 py-2 rounded-lg transition-colors">
              ← Previous
            </button>
          )}
          {revealed[currentQ] && !isLast && (
            <button
              onClick={() => setCurrentQ(currentQ + 1)}
              className="bg-green-600 hover:bg-green-500 text-white px-6 py-2 rounded-lg"
            >
              Next →
            </button>
          )}
          {revealed[currentQ] && isLast && (
            <button onClick={finishSession} className="bg-amber-600 hover:bg-amber-500 text-white px-6 py-2 rounded-lg">
              Finish Session
            </button>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={() => setNotesPanelOpen((o) => !o)}
        className="fixed bottom-6 right-5 z-40 rounded-full border border-amber-700/80 bg-amber-950/95 px-4 py-2.5 text-sm font-medium text-amber-100 shadow-lg hover:bg-amber-900"
      >
        {notesPanelOpen ? "Close notes" : "My notes"}
      </button>

      {notesPanelOpen && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/55"
            aria-label="Close notes panel"
            onClick={() => setNotesPanelOpen(false)}
          />
          <aside className="fixed bottom-0 right-0 top-0 z-50 flex w-full max-w-md flex-col border-l border-gray-800 bg-gray-950 shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
              <h2 className="text-sm font-semibold text-white">Parallel notes</h2>
              <button type="button" className="text-gray-400 hover:text-white text-sm" onClick={() => setNotesPanelOpen(false)}>
                ✕
              </button>
            </div>
            <p className="px-4 pt-2 text-xs text-gray-500">
              Auto-saves. Tied to session: {sessionMeta?.subtopic_id?.replace(/_/g, " ") ?? "—"} · Q{currentQ + 1}
            </p>
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
              <label className="block space-y-1">
                <span className="text-xs font-medium text-amber-400">Note for Q{currentQ + 1}</span>
                <textarea
                  value={perQuestionNotes[currentQ] ?? ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    setPerQuestionNotes((prev) => ({ ...prev, [currentQ]: val }));
                    notesDirty.current = true;
                    // Debounced autosave for per-question note
                    if (perQuestionSaveTimer.current) clearTimeout(perQuestionSaveTimer.current);
                    perQuestionSaveTimer.current = setTimeout(() => {
                      if (!quiz?.session_id || activeSession === null) return;
                      const s = plan?.sessions?.[activeSession];
                      if (!s?.subtopic_id) return;
                      api.putUserNotes(quiz.session_id, {
                        subtopic_id: s.subtopic_id,
                        subject_id: s.subject_id ?? "",
                        confusion: userNotes.confusion,
                        mnemonic: userNotes.mnemonic,
                        still_weak: userNotes.still_weak,
                        question_context_index: currentQ,
                        note_text: val,
                      }).then(() => { notesDirty.current = false; }).catch(() => {});
                    }, 700);
                  }}
                  rows={4}
                  className="w-full rounded-lg border border-amber-800/60 bg-gray-900 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600"
                  placeholder="Note for this question — clears when you move to the next one, reloads when you come back…"
                />
              </label>
              <label className="block space-y-1">
                <span className="text-xs font-medium text-gray-400">What feels unclear? (session-level)</span>
                <textarea
                  value={userNotes.confusion}
                  onChange={(e) => patchUserNotes({ confusion: e.target.value })}
                  rows={4}
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600"
                  placeholder="Concepts, facts, or question logic you want to revisit…"
                />
              </label>
              <label className="block space-y-1">
                <span className="text-xs font-medium text-gray-400">Mnemonic / one-liner</span>
                <input
                  value={userNotes.mnemonic}
                  onChange={(e) => patchUserNotes({ mnemonic: e.target.value })}
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600"
                  placeholder="Your own hook to remember this block…"
                />
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={userNotes.still_weak}
                  onChange={(e) => patchUserNotes({ still_weak: e.target.checked })}
                  className="rounded border-gray-600 bg-gray-900"
                />
                <span className="text-sm text-gray-300">Still weak — prioritise this subtopic in the next plan</span>
              </label>
            </div>
          </aside>
        </>
      )}
    </div>
  );
}
