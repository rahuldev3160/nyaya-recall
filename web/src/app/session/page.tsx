"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { api } from "@/lib/api";
import ContentFeedback from "@/components/ContentFeedback";
import ConfidenceSelector from "@/components/ConfidenceSelector";
import AmbientTimer from "@/components/AmbientTimer";
import SessionPauseScreen from "@/components/SessionPauseScreen";

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

// ── Notes section parser (ISSUE-017 Phase 2) ──────────────────────────────────
const NOTES_SECTION_SLUGS: Record<string, string> = {
  "Core Concept": "core_concept",
  "PYQ Angles": "pyq_angles",
  "Current Affairs Linkages": "current_affairs",
  "Broader Linkages": "broader_linkages",
};

/**
 * Split a notes_summary markdown string into { heading, slug, body }[] so each
 * section can be rendered individually with a ContentFeedback row appended.
 * Falls back to a single "unsectioned" block if no known headings are found.
 */
function parseNotesSections(markdown: string): { heading: string; slug: string; body: string }[] {
  const parts: { heading: string; slug: string; body: string }[] = [];
  const lines = markdown.split("\n");
  let currentHeading = "";
  let currentSlug = "";
  let bodyLines: string[] = [];

  for (const line of lines) {
    const match = line.match(/^## (.+)$/);
    if (match) {
      if (currentHeading) {
        parts.push({ heading: currentHeading, slug: currentSlug, body: bodyLines.join("\n").trim() });
      }
      currentHeading = match[1].trim();
      currentSlug = NOTES_SECTION_SLUGS[currentHeading] ?? currentHeading.toLowerCase().replace(/\s+/g, "_");
      bodyLines = [];
    } else {
      bodyLines.push(line);
    }
  }
  if (currentHeading) {
    parts.push({ heading: currentHeading, slug: currentSlug, body: bodyLines.join("\n").trim() });
  }

  // If no headings found, return the whole markdown as one block without feedback
  if (parts.length === 0) {
    return [{ heading: "", slug: "", body: markdown }];
  }

  return parts;
}

type UserNotesState = { confusion: string; mnemonic: string; still_weak: boolean };
// Per-question note map keyed by question_hash → {note_text, still_weak}
type QuestionNote = { note_text: string; still_weak: boolean };
type SyllabusSubject = { id: string; name: string; topics: SyllabusTopic[] };
type SyllabusTopic   = { id: string; name: string; subtopics: SyllabusSubtopic[] };
type SyllabusSubtopic = { id: string; name: string; dimensions: string[] };

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
  // Per-question note text keyed by question index (legacy — kept for backward compat)
  const [perQuestionNotes, setPerQuestionNotes] = useState<Record<number, string>>({});
  // Per-question notes keyed by question_hash (ISSUE-017: new question_notes table)
  const [questionNotesMap, setQuestionNotesMap] = useState<Record<string, QuestionNote>>({});
  const notesDirty = useRef(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const perQuestionSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const qnSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const restoredRef = useRef(false);

  const [notesExplainLoading, setNotesExplainLoading] = useState(false);
  const [notesExplainText, setNotesExplainText] = useState<string | null>(null);
  const [notesExplainErr, setNotesExplainErr] = useState<string | null>(null);

  // Confidence selector (per question, resets on question change)
  const [confidence, setConfidence] = useState<"sure" | "unsure" | "guess" | null>(null);
  // Ambient timer reset key — increments on each new question
  const [resetTimerKey, setResetTimerKey] = useState(0);
  // 10-question pause screen
  const [questionsAnsweredThisChunk, setQuestionsAnsweredThisChunk] = useState(0);
  const [showPauseScreen, setShowPauseScreen] = useState(false);

  // Plan-edit modal state
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [syllabusTree, setSyllabusTree] = useState<SyllabusSubject[]>([]);
  const [editDraft, setEditDraft] = useState<{ subject_id: string; topic_id: string; subtopic_id: string; format: string; difficulty: string; num_questions: number; estimated_minutes: number }>({ subject_id: "", topic_id: "", subtopic_id: "", format: "quiz_only", difficulty: "mixed", num_questions: 10, estimated_minutes: 30 });
  const [editSaving, setEditSaving] = useState(false);

  useEffect(() => {
    api.getSyllabusTree().then((t: SyllabusSubject[]) => setSyllabusTree(t)).catch(() => {});
  }, []);

  useEffect(() => {
    api.getPlan().then((data: any) => {
      // Strip any CSAT sessions — CSAT has its own separate flow at /csat
      if (data?.sessions) {
        data = { ...data, sessions: data.sessions.filter((s: any) => s.subject_id !== "csat") };
      }
      setPlan(data);
    }).catch(() => {});
    // API is authoritative — always overwrite with server state so stale localStorage never wins
    api.getPlanStatus()
      .then((s: { completed_subtopics: string[] }) => {
        setCompletedSessions(new Set(s?.completed_subtopics ?? []));
      })
      .catch(() => {});
  }, []);

  // Restore from localStorage on mount for instant UI (API result overwrites this once resolved)
  useEffect(() => {
    try {
      const key = `upsc_completed_${new Date().toISOString().split("T")[0]}`;
      const raw = localStorage.getItem(key);
      if (raw) setCompletedSessions(prev => new Set([...prev, ...(JSON.parse(raw) as string[])]));
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
    setConfidence(null);
    setResetTimerKey((k) => k + 1);
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
    setQuestionNotesMap({});

    // Load session-level notes (backward compat)
    api
      .getUserNotes(quiz.session_id)
      .then((d) => {
        setUserNotes({
          confusion: d.confusion || "",
          mnemonic: d.mnemonic || "",
          still_weak: !!d.still_weak,
        });
        if (d.per_question_notes && typeof d.per_question_notes === "object") {
          const loaded: Record<number, string> = {};
          for (const [k, v] of Object.entries(d.per_question_notes)) {
            loaded[parseInt(k)] = (v as string) || "";
          }
          setPerQuestionNotes(loaded);
        }
      })
      .catch(() => {});

    // Load per-question notes from new question_notes table (ISSUE-017)
    api
      .getQuestionNotes(quiz.session_id)
      .then((d: { notes: Array<{ question_hash: string; question_index: number; note_text: string; still_weak: boolean }> }) => {
        if (Array.isArray(d.notes)) {
          const map: Record<string, QuestionNote> = {};
          for (const n of d.notes) {
            map[n.question_hash] = { note_text: n.note_text || "", still_weak: !!n.still_weak };
          }
          setQuestionNotesMap(map);
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

  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      if (perQuestionSaveTimer.current) clearTimeout(perQuestionSaveTimer.current);
      if (qnSaveTimer.current) clearTimeout(qnSaveTimer.current);
    };
  }, []);

  const patchUserNotes = (patch: Partial<UserNotesState>) => {
    notesDirty.current = true;
    setUserNotes((n) => ({ ...n, ...patch }));
  };

  const openEdit = (session: any, idx: number) => {
    setEditDraft({
      subject_id: session.subject_id ?? "",
      topic_id: session.topic_id ?? "",
      subtopic_id: session.subtopic_id ?? "",
      format: session.format ?? "quiz_only",
      difficulty: session.difficulty ?? "mixed",
      num_questions: session.num_questions ?? 10,
      estimated_minutes: session.estimated_minutes ?? 30,
    });
    setEditingIdx(idx);
  };

  const saveEdit = async () => {
    if (editingIdx === null || !plan?.sessions) return;
    setEditSaving(true);
    try {
      const updated = plan.sessions.map((s: any, i: number) =>
        i === editingIdx ? { ...s, ...editDraft, user_edited: true } : s
      );
      await api.patchUserPlan(updated);
      setPlan((p: any) => ({ ...p, sessions: updated, is_user_edited: true }));
      setEditingIdx(null);
    } catch {
      /* ignore — session card remains unchanged */
    } finally {
      setEditSaving(false);
    }
  };

  const editTopics = syllabusTree.find((s) => s.id === editDraft.subject_id)?.topics ?? [];
  const editSubtopics = editTopics.find((t) => t.id === editDraft.topic_id)?.subtopics ?? [];

  const startSession = async (session: any, index: number) => {
    setLoading(true);
    setError(null);
    setPendingAnswer(null);
    setActiveSession(index);
    setRevisionNotes(null);
    setRevisionLoading(false);
    setPerQuestionNotes({});
    setQuestionNotesMap({});
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

    // Track 10-question chunk for pause screen
    const newChunk = questionsAnsweredThisChunk + 1;
    setQuestionsAnsweredThisChunk(newChunk);
    if (newChunk >= 10) {
      setShowPauseScreen(true);
    }

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
      dimension_id: q.dimension_id ?? null,
      confidence: confidence ?? "guess",
    }).catch(() => {});
  };

  const flushCurrentQuestionNote = async () => {
    if (!quiz?.session_id || activeSession === null) return;
    const s = plan?.sessions?.[activeSession];
    if (!s?.subtopic_id) return;
    const q = quiz.questions[currentQ];
    if (!q) return;
    const qHash = q.question_hash ?? `${quiz.session_id}_${currentQ}`;
    const qNote = questionNotesMap[qHash];
    if (!qNote && !perQuestionNotes[currentQ]) return;
    const noteText = qNote?.note_text ?? perQuestionNotes[currentQ] ?? "";
    const stillWeak = qNote?.still_weak ?? false;
    if (qnSaveTimer.current) clearTimeout(qnSaveTimer.current);
    try {
      await api.putQuestionNote(quiz.session_id, qHash, {
        question_index: currentQ,
        subtopic_id: s.subtopic_id,
        subject_id: s.subject_id ?? "",
        note_text: noteText,
        still_weak: stillWeak,
      });
    } catch {
      /* ignore */
    }
  };

  const finishSession = async () => {
    if (!quiz) return;
    try { localStorage.removeItem(ACTIVE_QUIZ_KEY); } catch {}
    await flushCurrentQuestionNote();
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
              setQuestionNotesMap({});
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
            {plan.is_user_edited && (
              <div className="flex items-center justify-between px-1 pb-1">
                <span className="text-xs text-amber-400">✏️ You&apos;ve edited this plan</span>
                <button onClick={async () => { await api.resetUserPlan(); const p = await api.getPlan(); setPlan(p); }} className="text-xs text-gray-500 hover:text-gray-300 underline">Reset to AI plan</button>
              </div>
            )}
            {plan.sessions.map((s: any, i: number) => {
              const done = completedSessions.has(s.subtopic_id);
              return (
                <div key={i} className={`p-4 rounded-xl border ${done ? "bg-green-950/30 border-green-900/50" : "bg-gray-900 border-gray-800"}`}>
                  <div className="flex items-center gap-4">
                    <div className="flex-1 min-w-0">
                      <div className={`font-medium flex items-center gap-2 ${done ? "text-green-300" : "text-white"}`}>
                        {done && <span>✓</span>}
                        <span className="truncate">{s.subject_id?.replace(/_/g, " ")} → {s.subtopic_id?.replace(/_/g, " ")}</span>
                        {s.user_edited && <span className="text-xs bg-amber-900/50 text-amber-300 px-1.5 py-0.5 rounded shrink-0">Edited</span>}
                      </div>
                      <div className="text-sm text-gray-500 mt-1">
                        {s.format?.replace(/_/g, " ")} · {s.estimated_minutes} min · {s.num_questions ?? 10}Q
                        {s.difficulty && s.difficulty !== "mixed" && (
                          <span className="ml-2 text-amber-400">· {s.difficulty === "easy" ? "Easy" : s.difficulty === "medium" ? "Medium" : s.difficulty === "hard" ? "Hard" : s.difficulty}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {!done && (
                        <button onClick={() => openEdit(s, i)} title="Edit session" className="text-gray-500 hover:text-amber-400 px-2 py-2 rounded-lg text-sm transition-colors">✏️</button>
                      )}
                      {done ? (
                        <span className="text-green-400 text-sm font-medium px-4 py-2">Completed</span>
                      ) : (
                        <button onClick={() => startSession(s, i)} disabled={loading} className="bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">
                          {loading && activeSession === i ? "Generating..." : "Start"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Edit session modal */}
        {editingIdx !== null && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
              <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md space-y-4">
                <h2 className="text-lg font-semibold">Edit Session {editingIdx + 1}</h2>

                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">Subject</label>
                    <select value={editDraft.subject_id} onChange={(e) => setEditDraft((d) => ({ ...d, subject_id: e.target.value, topic_id: "", subtopic_id: "" }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                      <option value="">— select subject —</option>
                      {syllabusTree.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                  </div>

                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">Topic</label>
                    <select value={editDraft.topic_id} onChange={(e) => setEditDraft((d) => ({ ...d, topic_id: e.target.value, subtopic_id: "" }))} disabled={!editDraft.subject_id} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white disabled:opacity-40">
                      <option value="">— select topic —</option>
                      {editTopics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  </div>

                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">Subtopic</label>
                    <select value={editDraft.subtopic_id} onChange={(e) => setEditDraft((d) => ({ ...d, subtopic_id: e.target.value }))} disabled={!editDraft.topic_id} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white disabled:opacity-40">
                      <option value="">— select subtopic —</option>
                      {editSubtopics.map((st) => <option key={st.id} value={st.id}>{st.name}</option>)}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-gray-400 mb-1 block">Format</label>
                      <select value={editDraft.format} onChange={(e) => setEditDraft((d) => ({ ...d, format: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                        <option value="quiz_only">Quiz only</option>
                        <option value="notes_then_quiz">Notes then quiz</option>
                        <option value="open_practice">Open practice</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 mb-1 block">Difficulty</label>
                      <select value={editDraft.difficulty} onChange={(e) => setEditDraft((d) => ({ ...d, difficulty: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white">
                        <option value="mixed">Mixed</option>
                        <option value="easy">Easy</option>
                        <option value="medium">Medium</option>
                        <option value="hard">Hard</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-gray-400 mb-1 block">Questions</label>
                      <input type="number" min={5} max={30} value={editDraft.num_questions} onChange={(e) => setEditDraft((d) => ({ ...d, num_questions: parseInt(e.target.value) || 10 }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white" />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 mb-1 block">Duration (min)</label>
                      <input type="number" min={10} max={180} value={editDraft.estimated_minutes} onChange={(e) => setEditDraft((d) => ({ ...d, estimated_minutes: parseInt(e.target.value) || 30 }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white" />
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 pt-1">
                  <button onClick={() => setEditingIdx(null)} className="flex-1 border border-gray-700 text-gray-300 hover:text-white py-2 rounded-lg text-sm">Cancel</button>
                  <button onClick={saveEdit} disabled={editSaving || !editDraft.subject_id || !editDraft.subtopic_id} className="flex-1 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white py-2 rounded-lg text-sm font-medium">
                    {editSaving ? "Saving..." : "Save edit"}
                  </button>
                </div>
              </div>
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

  // Compute pause screen stats
  const answeredIndexes = Object.keys(answers).map(Number);
  const correctInChunk = answeredIndexes.filter(
    (i) => quiz?.questions?.[i]?.correct_answer === answers[i]
  ).length;
  const chunkTotal = answeredIndexes.length;

  return (
    <div className="relative min-h-[60vh]">
      {/* 10-question pause screen */}
      {showPauseScreen && (
        <SessionPauseScreen
          correct={correctInChunk}
          total={chunkTotal}
          avgTimeSec={0}
          streak={0}
          weakTopics={[]}
          strongTopics={[]}
          onContinue={() => {
            setShowPauseScreen(false);
            setQuestionsAnsweredThisChunk(0);
          }}
          onExit={() => {
            setShowPauseScreen(false);
            finishSession();
          }}
        />
      )}
      <div className="max-w-2xl space-y-6 pb-24">
        {quiz.notes_summary && !answers[0] && (
          <div className="bg-blue-950 border border-blue-800 rounded-xl p-5">
            <h3 className="text-blue-300 font-semibold mb-3">Key Concepts — Read Before Quiz</h3>
            {/* ISSUE-017 Phase 2: render each notes section individually so ContentFeedback
                can be placed after each heading block */}
            <div className="max-h-[50vh] overflow-y-auto pr-1 text-sm space-y-4">
              {parseNotesSections(quiz.notes_summary).map((section, idx) => (
                <div key={idx}>
                  {section.heading && (
                    <h2 className="text-lg font-semibold text-blue-200 mt-4 first:mt-0 mb-2">
                      {section.heading}
                    </h2>
                  )}
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={notesMarkdownComponents}>
                    {section.body}
                  </ReactMarkdown>
                  {/* Feedback row — only for the 4 known sections */}
                  {section.slug && NOTES_SECTION_SLUGS[section.heading] && (
                    <ContentFeedback
                      sessionId={quiz.session_id}
                      contentType="notes_section"
                      subtopicId={sessionMeta?.subtopic_id ?? ""}
                      subjectId={sessionMeta?.subject_id ?? ""}
                      notesSection={section.slug}
                    />
                  )}
                </div>
              ))}
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

        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800 space-y-4">
          {/* Ambient timer — sits above question text */}
          <AmbientTimer active={!revealed[currentQ]} resetKey={resetTimerKey} />
          <p className="text-white leading-relaxed whitespace-pre-wrap">{q.question_text}</p>
        </div>

        {/* Confidence selector — shown before the answer options */}
        <ConfidenceSelector
          value={confidence}
          onChange={setConfidence}
          disabled={!!revealed[currentQ]}
        />

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

            {/* ISSUE-017 Phase 2: content feedback */}
            <ContentFeedback
              key={`sess-feedback-${quiz?.session_id}-${currentQ}`}
              sessionId={quiz?.session_id ?? ""}
              contentType="explanation"
              questionHash={q.question_hash ?? `${quiz?.session_id}_${currentQ}`}
              subtopicId={q.subtopic_id ?? plan?.sessions?.[activeSession!]?.subtopic_id ?? ""}
              subjectId={plan?.sessions?.[activeSession!]?.subject_id ?? ""}
            />
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
                <span className="text-xs font-medium text-amber-400">Note for Q{currentQ + 1} — {sessionMeta?.subtopic_id?.replace(/_/g, " ") ?? ""}</span>
                <textarea
                  value={(() => {
                    const qHash = quiz?.questions?.[currentQ]?.question_hash ?? `${quiz?.session_id}_${currentQ}`;
                    return questionNotesMap[qHash]?.note_text ?? perQuestionNotes[currentQ] ?? "";
                  })()}
                  onChange={(e) => {
                    const val = e.target.value;
                    const qHash = quiz?.questions?.[currentQ]?.question_hash ?? `${quiz?.session_id}_${currentQ}`;
                    setQuestionNotesMap((prev) => ({
                      ...prev,
                      [qHash]: { note_text: val, still_weak: prev[qHash]?.still_weak ?? false },
                    }));
                    // Keep legacy perQuestionNotes in sync for backward compat
                    setPerQuestionNotes((prev) => ({ ...prev, [currentQ]: val }));
                    // Debounced autosave via new question_notes endpoint (ISSUE-017)
                    if (qnSaveTimer.current) clearTimeout(qnSaveTimer.current);
                    qnSaveTimer.current = setTimeout(() => {
                      if (!quiz?.session_id || activeSession === null) return;
                      const s = plan?.sessions?.[activeSession];
                      if (!s?.subtopic_id) return;
                      const stillWeak = questionNotesMap[qHash]?.still_weak ?? false;
                      api.putQuestionNote(quiz.session_id, qHash, {
                        question_index: currentQ,
                        subtopic_id: s.subtopic_id,
                        subject_id: s.subject_id ?? "",
                        note_text: val,
                        still_weak: stillWeak,
                      }).catch(() => {});
                    }, 700);
                  }}
                  rows={4}
                  className="w-full rounded-lg border border-amber-800/60 bg-gray-900 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600"
                  placeholder="Note for this question — autosaves. Reloads when you come back to this question."
                />
              </label>
              <label className="flex items-center gap-2 cursor-pointer mt-1">
                <input
                  type="checkbox"
                  checked={(() => {
                    const qHash = quiz?.questions?.[currentQ]?.question_hash ?? `${quiz?.session_id}_${currentQ}`;
                    return questionNotesMap[qHash]?.still_weak ?? false;
                  })()}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    const qHash = quiz?.questions?.[currentQ]?.question_hash ?? `${quiz?.session_id}_${currentQ}`;
                    setQuestionNotesMap((prev) => ({
                      ...prev,
                      [qHash]: { note_text: prev[qHash]?.note_text ?? "", still_weak: checked },
                    }));
                    // Debounced save for still_weak flag
                    if (qnSaveTimer.current) clearTimeout(qnSaveTimer.current);
                    qnSaveTimer.current = setTimeout(() => {
                      if (!quiz?.session_id || activeSession === null) return;
                      const s = plan?.sessions?.[activeSession];
                      if (!s?.subtopic_id) return;
                      const noteText = questionNotesMap[qHash]?.note_text ?? perQuestionNotes[currentQ] ?? "";
                      api.putQuestionNote(quiz.session_id, qHash, {
                        question_index: currentQ,
                        subtopic_id: s.subtopic_id,
                        subject_id: s.subject_id ?? "",
                        note_text: noteText,
                        still_weak: checked,
                      }).catch(() => {});
                    }, 700);
                  }}
                  className="rounded border-gray-600 bg-gray-900"
                />
                <span className="text-xs text-amber-300">Still weak on this question — flag for next plan</span>
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
