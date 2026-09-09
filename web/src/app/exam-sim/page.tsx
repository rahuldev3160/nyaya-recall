"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type SyllabusSubtopic = { id: string; name: string };
type SyllabusTopic = { id: string; name: string; subtopics: SyllabusSubtopic[] };
type SyllabusSubject = { id: string; name: string; topics: SyllabusTopic[] };

type Question = {
  question_text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_answer: string;
  explanation: string;
  difficulty: string;
  subject_id: string;
  subtopic_id: string;
  question_hash?: string;
};

type ExamResults = {
  total_correct: number;
  total_attempted: number;
  total_questions: number;
  accuracy_pct: number;
  is_full_mock?: boolean;
  pyq_pct?: number | null;
  by_subject: Array<{
    subject_id: string;
    subject_name: string;
    questions: number;
    correct: number;
    accuracy_pct: number;
    topics: Array<{
      topic_id: string;
      topic_name: string;
      questions: number;
      correct: number;
      accuracy_pct: number;
    }>;
  }>;
};

type View = "setup" | "running" | "results";

// ── Timer hook ────────────────────────────────────────────────────────────────

function useCountdown(seconds: number | null, onExpire: () => void) {
  const [remaining, setRemaining] = useState<number | null>(seconds);
  const expiredRef = useRef(false);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    if (seconds === null) return;
    setRemaining(seconds);
    expiredRef.current = false;
  }, [seconds]);

  useEffect(() => {
    if (remaining === null) return;
    if (remaining <= 0) {
      if (!expiredRef.current) {
        expiredRef.current = true;
        onExpireRef.current();
      }
      return;
    }
    const t = setTimeout(() => setRemaining((r) => (r !== null ? r - 1 : null)), 1000);
    return () => clearTimeout(t);
  }, [remaining]);

  return remaining;
}

function fmtTime(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// ── Syllabus tree selector component ─────────────────────────────────────────

type SelectionState = {
  subjects: Record<string, boolean | "partial">;
  topics: Record<string, boolean | "partial">;
  subtopics: Record<string, boolean>;
};

function SyllabusSelector({
  tree,
  selection,
  onChange,
}: {
  tree: SyllabusSubject[];
  selection: SelectionState;
  onChange: (next: SelectionState) => void;
}) {
  const [expandedSubjects, setExpandedSubjects] = useState<Record<string, boolean>>({});
  const [expandedTopics, setExpandedTopics] = useState<Record<string, boolean>>({});

  const toggleSubject = (subj: SyllabusSubject) => {
    const current = selection.subjects[subj.id];
    const checked = current !== true;
    const nextSubtopics = { ...selection.subtopics };
    const nextTopics = { ...selection.topics };
    for (const topic of subj.topics) {
      for (const st of topic.subtopics) {
        nextSubtopics[st.id] = checked;
      }
      nextTopics[topic.id] = checked;
    }
    const nextSubjects = { ...selection.subjects, [subj.id]: checked };
    onChange({ subjects: nextSubjects, topics: nextTopics, subtopics: nextSubtopics });
  };

  const toggleTopic = (subj: SyllabusSubject, topic: SyllabusTopic) => {
    const current = selection.topics[topic.id];
    const checked = current !== true;
    const nextSubtopics = { ...selection.subtopics };
    for (const st of topic.subtopics) {
      nextSubtopics[st.id] = checked;
    }
    const nextTopics = { ...selection.topics, [topic.id]: checked };
    // Recompute subject state
    const nextSubjects = { ...selection.subjects };
    const allSubtopicsInSubject = subj.topics.flatMap((t) => t.subtopics.map((s) => s.id));
    const numChecked = allSubtopicsInSubject.filter((id) => nextSubtopics[id]).length;
    nextSubjects[subj.id] =
      numChecked === 0 ? false : numChecked === allSubtopicsInSubject.length ? true : "partial";
    onChange({ subjects: nextSubjects, topics: nextTopics, subtopics: nextSubtopics });
  };

  const toggleSubtopic = (subj: SyllabusSubject, topic: SyllabusTopic, st: SyllabusSubtopic) => {
    const checked = !selection.subtopics[st.id];
    const nextSubtopics = { ...selection.subtopics, [st.id]: checked };
    // Recompute topic state
    const nextTopics = { ...selection.topics };
    const allInTopic = topic.subtopics.map((s) => s.id);
    const numCheckedInTopic = allInTopic.filter((id) => nextSubtopics[id]).length;
    nextTopics[topic.id] =
      numCheckedInTopic === 0
        ? false
        : numCheckedInTopic === allInTopic.length
        ? true
        : "partial";
    // Recompute subject state
    const nextSubjects = { ...selection.subjects };
    const allInSubject = subj.topics.flatMap((t) => t.subtopics.map((s) => s.id));
    const numCheckedInSubject = allInSubject.filter((id) => nextSubtopics[id]).length;
    nextSubjects[subj.id] =
      numCheckedInSubject === 0
        ? false
        : numCheckedInSubject === allInSubject.length
        ? true
        : "partial";
    onChange({ subjects: nextSubjects, topics: nextTopics, subtopics: nextSubtopics });
  };

  return (
    <div className="space-y-2">
      {tree.map((subj) => (
        <div key={subj.id} className="border border-gray-800 rounded-lg overflow-hidden">
          {/* Subject header */}
          <div className="flex items-center gap-3 px-4 py-3 bg-gray-900 hover:bg-gray-800 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={selection.subjects[subj.id] === true}
              ref={(el) => {
                if (el) el.indeterminate = selection.subjects[subj.id] === "partial";
              }}
              onChange={() => toggleSubject(subj)}
              onClick={(e) => e.stopPropagation()}
              className="rounded border-gray-600 bg-gray-800 accent-amber-500"
            />
            <button
              type="button"
              className="flex-1 text-left font-semibold text-white text-sm flex items-center gap-2"
              onClick={() =>
                setExpandedSubjects((p) => ({ ...p, [subj.id]: !p[subj.id] }))
              }
            >
              <span>{subj.name}</span>
              <span className="text-gray-500 font-normal text-xs">
                {subj.topics.flatMap((t) => t.subtopics).filter((s) => selection.subtopics[s.id]).length}
                {" / "}
                {subj.topics.flatMap((t) => t.subtopics).length} subtopics
              </span>
              <span className="ml-auto text-gray-500">{expandedSubjects[subj.id] ? "▲" : "▼"}</span>
            </button>
          </div>

          {/* Topics */}
          {expandedSubjects[subj.id] && (
            <div className="border-t border-gray-800 bg-gray-950">
              {subj.topics.map((topic) => (
                <div key={topic.id}>
                  {/* Topic row */}
                  <div className="flex items-center gap-3 px-6 py-2 hover:bg-gray-900 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={selection.topics[topic.id] === true}
                      ref={(el) => {
                        if (el) el.indeterminate = selection.topics[topic.id] === "partial";
                      }}
                      onChange={() => toggleTopic(subj, topic)}
                      onClick={(e) => e.stopPropagation()}
                      className="rounded border-gray-600 bg-gray-800 accent-amber-500"
                    />
                    <button
                      type="button"
                      className="flex-1 text-left text-sm text-gray-200 flex items-center gap-2"
                      onClick={() =>
                        setExpandedTopics((p) => ({ ...p, [topic.id]: !p[topic.id] }))
                      }
                    >
                      <span>{topic.name}</span>
                      <span className="text-gray-600 text-xs">
                        {topic.subtopics.filter((s) => selection.subtopics[s.id]).length}
                        /{topic.subtopics.length}
                      </span>
                      <span className="ml-auto text-gray-600 text-xs">
                        {expandedTopics[topic.id] ? "▲" : "▼"}
                      </span>
                    </button>
                  </div>

                  {/* Subtopics */}
                  {expandedTopics[topic.id] && (
                    <div className="pl-12 pr-4 pb-2 space-y-1">
                      {topic.subtopics.map((st) => (
                        <label
                          key={st.id}
                          className="flex items-center gap-3 py-1 px-2 rounded hover:bg-gray-900 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={!!selection.subtopics[st.id]}
                            onChange={() => toggleSubtopic(subj, topic, st)}
                            className="rounded border-gray-600 bg-gray-800 accent-amber-500"
                          />
                          <span className="text-xs text-gray-300">{st.name}</span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Types for exam sim history ────────────────────────────────────────────────

type ExamSimRecord = {
  session_id: string;
  session_date: string;
  total_questions: number;
  correct: number;
  skipped: number;
  accuracy_pct: number;
  timed_minutes: number | null;
  subjects_covered: string[];
  subject_breakdown: Record<string, { correct: number; total: number; skipped: number; accuracy_pct: number }>;
  created_at: string;
};

// ── History panel component ───────────────────────────────────────────────────

function ExamSimHistory({ records }: { records: ExamSimRecord[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (records.length === 0) {
    return (
      <div className="text-gray-600 text-sm text-center py-4">
        No past simulations yet. Complete one to see your history here.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {records.map((r) => {
        const isExpanded = expanded === r.session_id;
        const weak = r.accuracy_pct < 50;
        return (
          <div
            key={r.session_id}
            className={`border rounded-xl overflow-hidden ${weak ? "border-red-900/60" : "border-gray-800"}`}
          >
            <button
              type="button"
              onClick={() => setExpanded(isExpanded ? null : r.session_id)}
              className={`w-full flex items-center gap-4 px-4 py-3 text-left ${
                weak ? "bg-red-950/30 hover:bg-red-950/50" : "bg-gray-900 hover:bg-gray-800"
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-white">{r.session_date}</span>
                  <span className="text-xs text-gray-500">{r.total_questions}Q</span>
                  {r.timed_minutes && (
                    <span className="text-xs text-gray-600">{r.timed_minutes}min</span>
                  )}
                  <span className="text-xs text-gray-600">
                    {r.subjects_covered.map((s) => s.replace(/_/g, " ")).join(", ")}
                  </span>
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {r.correct}/{r.total_questions - r.skipped} correct · {r.skipped} skipped
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className={`text-lg font-bold ${
                    r.accuracy_pct >= 70
                      ? "text-green-400"
                      : r.accuracy_pct >= 50
                      ? "text-amber-400"
                      : "text-red-400"
                  }`}
                >
                  {r.accuracy_pct}%
                </span>
                <span className="text-gray-600 text-xs">{isExpanded ? "▲" : "▼"}</span>
              </div>
            </button>

            {isExpanded && Object.keys(r.subject_breakdown).length > 0 && (
              <div className="border-t border-gray-800 divide-y divide-gray-800/50 bg-gray-950">
                {Object.entries(r.subject_breakdown).map(([sid, stats]) => (
                  <div key={sid} className="flex items-center gap-3 px-6 py-2">
                    <span className="flex-1 text-xs text-gray-400 capitalize">
                      {sid.replace(/_/g, " ")}
                    </span>
                    <span className="text-xs text-gray-500">
                      {stats.correct}/{stats.total - stats.skipped} correct
                    </span>
                    <span
                      className={`text-xs font-semibold w-10 text-right ${
                        stats.accuracy_pct >= 70
                          ? "text-green-400"
                          : stats.accuracy_pct >= 50
                          ? "text-amber-400"
                          : "text-red-400"
                      }`}
                    >
                      {stats.accuracy_pct}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ExamSimPage() {
  const [view, setView] = useState<View>("setup");
  const [tree, setTree] = useState<SyllabusSubject[]>([]);
  const [treeLoading, setTreeLoading] = useState(true);
  const [history, setHistory] = useState<ExamSimRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Setup state
  const [selection, setSelection] = useState<SelectionState>({
    subjects: {},
    topics: {},
    subtopics: {},
  });
  const [numQuestions, setNumQuestions] = useState<string>("");
  const [duration, setDuration] = useState<string>("");
  const [startLoading, setStartLoading] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const [fullMockLoading, setFullMockLoading] = useState(false);
  const [fullMockError, setFullMockError] = useState<string | null>(null);

  // Running state
  const [quiz, setQuiz] = useState<{
    session_id: string;
    questions: Question[];
    timed_duration_minutes: number | null;
    pyq_pct?: number | null;
  } | null>(null);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});
  const [pendingAnswer, setPendingAnswer] = useState<string | null>(null);
  const [finishLoading, setFinishLoading] = useState(false);

  // Results state
  const [results, setResults] = useState<ExamResults | null>(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [expandedSubjects, setExpandedSubjects] = useState<Record<string, boolean>>({});

  const loadHistory = useCallback(() => {
    setHistoryLoading(true);
    api
      .getExamSimHistory()
      .then((h: ExamSimRecord[]) => setHistory(h))
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false));
  }, []);

  // Load syllabus tree + history on mount
  useEffect(() => {
    api
      .getSyllabusTree()
      .then((t: SyllabusSubject[]) => setTree(t))
      .catch(() => {})
      .finally(() => setTreeLoading(false));
    loadHistory();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedSubtopicIds = Object.entries(selection.subtopics)
    .filter(([, v]) => v)
    .map(([k]) => k);

  const numQ = parseInt(numQuestions) || 0;
  const dur = parseInt(duration) || 0;
  const canStart =
    selectedSubtopicIds.length > 0 &&
    numQ >= 1 &&
    numQ <= 100 &&
    dur >= 1 &&
    dur <= 180;

  // ── Timer expire → finish ──────────────────────────────────────────────────
  const timerSeconds =
    quiz?.timed_duration_minutes != null ? quiz.timed_duration_minutes * 60 : null;

  const handleTimerExpire = useCallback(() => {
    if (view !== "running" || !quiz) return;
    void finishExam(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, quiz]);

  const remaining = useCountdown(timerSeconds, handleTimerExpire);

  // ── Start exam ─────────────────────────────────────────────────────────────
  const startExam = async () => {
    setStartLoading(true);
    setStartError(null);
    try {
      const data = await api.startExamSimulation({
        session_type: "exam_simulation",
        subtopic_ids: selectedSubtopicIds,
        n_questions: numQ,
        timed_duration_minutes: dur,
      });
      setQuiz(data);
      setCurrentQ(0);
      setAnswers({});
      setRevealed({});
      setPendingAnswer(null);
      setView("running");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to generate questions. Please try again.";
      setStartError(msg);
    } finally {
      setStartLoading(false);
    }
  };

  // ── Start Full Mock (fixed 100Q/120min, PYQ-first, PLAN-011 Area 2) ─────────
  const startFullMock = async () => {
    setFullMockLoading(true);
    setFullMockError(null);
    try {
      const data = await api.startExamSimulation({ session_type: "full_mock" });
      setQuiz(data);
      setCurrentQ(0);
      setAnswers({});
      setRevealed({});
      setPendingAnswer(null);
      setView("running");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to generate the Full Mock. Please try again.";
      setFullMockError(msg);
    } finally {
      setFullMockLoading(false);
    }
  };

  // ── Submit answer ──────────────────────────────────────────────────────────
  const submitAnswer = async (opt: string) => {
    if (!quiz || answers[currentQ]) return;
    const q = quiz.questions[currentQ];
    setAnswers((a) => ({ ...a, [currentQ]: opt }));
    setRevealed((r) => ({ ...r, [currentQ]: true }));
    await api
      .submitAnswer({
        session_id: quiz.session_id,
        question_hash: q.question_hash ?? `${quiz.session_id}_${currentQ}`,
        question_text: q.question_text,
        options: {
          a: q.option_a ?? "",
          b: q.option_b ?? "",
          c: q.option_c ?? "",
          d: q.option_d ?? "",
        },
        correct_answer: q.correct_answer,
        user_answer: opt,
        is_correct: q.correct_answer === opt,
        time_taken_sec: 0,
        subject_id: q.subject_id ?? "",
        subtopic_id: q.subtopic_id ?? "",
        dimension_id: null,
      })
      .catch(() => {});
  };

  // ── Finish exam ────────────────────────────────────────────────────────────
  const finishExam = async (timerExpired = false) => {
    if (!quiz || finishLoading) return;
    setFinishLoading(true);

    // Mark all unreached questions as skipped (timer-expired behaviour)
    if (timerExpired) {
      const skipPromises: Promise<unknown>[] = [];
      for (let i = 0; i < quiz.questions.length; i++) {
        if (!answers[i]) {
          const q = quiz.questions[i];
          skipPromises.push(
            api
              .submitAnswer({
                session_id: quiz.session_id,
                question_hash: q.question_hash ?? `${quiz.session_id}_${i}`,
                question_text: q.question_text,
                options: {
                  a: q.option_a ?? "",
                  b: q.option_b ?? "",
                  c: q.option_c ?? "",
                  d: q.option_d ?? "",
                },
                correct_answer: q.correct_answer,
                user_answer: "",
                is_correct: false,
                time_taken_sec: 0,
                subject_id: q.subject_id ?? "",
                subtopic_id: q.subtopic_id ?? "",
                dimension_id: null,
                skipped: true,
              })
              .catch(() => {})
          );
        }
      }
      await Promise.all(skipPromises);
    }

    try {
      await api.closeSession(quiz.session_id);
    } catch {
      /* ignore */
    }

    // Fetch results and refresh history in parallel
    setResultsLoading(true);
    setView("results");
    try {
      const res = await api.getExamResults(quiz.session_id);
      setResults(res as ExamResults);
    } catch {
      setResults(null);
    } finally {
      setResultsLoading(false);
      setFinishLoading(false);
      loadHistory();
    }
  };

  // ── Setup view ─────────────────────────────────────────────────────────────
  if (view === "setup") {
    return (
      <div className="max-w-3xl space-y-8">
        <div>
          <h1 className="text-2xl font-bold">Exam Simulation</h1>
          <p className="text-gray-400 text-sm mt-1">
            Simulate a real exam by selecting topics, question count, and time limit.
            All questions are generated upfront before the timer starts.
          </p>
        </div>

        {/* ── Full Mock ── */}
        <div className="border border-amber-700/50 bg-amber-950/20 rounded-xl p-5 space-y-3">
          <div>
            <h2 className="text-base font-semibold text-amber-300">Full Mock — Real Prelims Structure</h2>
            <p className="text-gray-400 text-sm mt-1">
              Fixed 100 questions, 120 minutes, spans the full syllabus in the same proportions
              as the real UPSC Prelims paper. Sources real PYQs first (held back from regular
              practice so they aren&apos;t memorized in advance), with AI-generated questions
              filling only the gap. Results show what fraction was real PYQ vs AI-approximated.
            </p>
          </div>
          {fullMockError && (
            <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-red-300 text-sm">
              {fullMockError}
            </div>
          )}
          <button
            onClick={startFullMock}
            disabled={fullMockLoading || startLoading}
            className="w-full bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl text-sm transition-colors"
          >
            {fullMockLoading ? "Building your Full Mock — this may take 30–60 seconds..." : "Start Full Mock"}
          </button>
        </div>

        <div className="text-center text-xs text-gray-600">— or, for targeted drilling on specific topics —</div>

        {/* Config strip */}
        <div className="flex flex-wrap gap-6 items-end">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Questions (1–100)</label>
            <input
              type="number"
              min={1}
              max={100}
              value={numQuestions}
              onChange={(e) => setNumQuestions(e.target.value)}
              placeholder="e.g. 50"
              className="w-28 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-gray-600"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Duration (minutes, 1–180)</label>
            <input
              type="number"
              min={1}
              max={180}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="e.g. 120"
              className="w-32 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-gray-600"
            />
          </div>
          <div className="text-sm text-gray-500">
            {selectedSubtopicIds.length > 0 ? (
              <span className="text-amber-400 font-medium">{selectedSubtopicIds.length} subtopics selected</span>
            ) : (
              <span>No subtopics selected</span>
            )}
          </div>
        </div>

        {/* Syllabus tree */}
        {treeLoading ? (
          <div className="text-gray-500 text-sm animate-pulse">Loading syllabus...</div>
        ) : tree.length === 0 ? (
          <div className="text-red-400 text-sm">Could not load syllabus. Is the backend running?</div>
        ) : (
          <SyllabusSelector tree={tree} selection={selection} onChange={setSelection} />
        )}

        {startError && (
          <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-red-300 text-sm">
            {startError}
          </div>
        )}

        <button
          onClick={startExam}
          disabled={!canStart || startLoading}
          className="w-full bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl text-sm transition-colors"
        >
          {startLoading
            ? "Generating questions — this may take 20–40 seconds..."
            : "Start Simulation"}
        </button>
        {startLoading && (
          <p className="text-center text-xs text-gray-500">
            Generating all {numQ} questions upfront. Timer starts after questions load.
          </p>
        )}

        {/* ── Past Simulations ── */}
        <div>
          <h2 className="text-base font-semibold text-gray-200 mb-3">Past Simulations</h2>
          {historyLoading ? (
            <div className="text-gray-600 text-sm animate-pulse">Loading history...</div>
          ) : (
            <ExamSimHistory records={history} />
          )}
        </div>
      </div>
    );
  }

  // ── Results view ───────────────────────────────────────────────────────────
  if (view === "results") {
    const localCorrect = Object.entries(answers).filter(
      ([idx, opt]) => quiz?.questions?.[parseInt(idx)]?.correct_answer === opt
    ).length;
    const total = quiz?.questions?.length ?? 0;
    const localPct = total > 0 ? Math.round((localCorrect / total) * 100) : 0;

    return (
      <div className="max-w-3xl space-y-8">
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-2xl font-bold">Simulation Complete</h1>
          {quiz?.session_id && (
            <a
              href={`/sessions`}
              className="text-sm text-gray-400 hover:text-white underline underline-offset-2"
            >
              Session history →
            </a>
          )}
        </div>

        {/* Overall score card */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 text-center space-y-2">
          <div className="text-5xl font-bold text-amber-400">
            {resultsLoading ? "..." : `${results?.accuracy_pct ?? localPct}%`}
          </div>
          <div className="text-gray-400 text-sm">
            {resultsLoading
              ? "Calculating..."
              : `${results?.total_correct ?? localCorrect} / ${results?.total_questions ?? total} correct`}
          </div>
          {!resultsLoading && results && (
            <div className="text-gray-500 text-xs">
              {results.total_attempted} attempted · {results.total_questions - results.total_attempted} skipped
            </div>
          )}
          {!resultsLoading && results?.is_full_mock && results.pyq_pct != null && (
            <div className="text-amber-400/80 text-xs pt-1">
              {results.pyq_pct}% real UPSC PYQs · {(100 - results.pyq_pct).toFixed(1)}% AI-approximated
            </div>
          )}
        </div>

        {/* Subject breakdown */}
        {resultsLoading && (
          <div className="text-gray-500 text-sm animate-pulse text-center">
            Loading subject breakdown...
          </div>
        )}

        {!resultsLoading && results && results.by_subject.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-base font-semibold text-gray-200">Subject Breakdown</h2>
            {results.by_subject.map((subj) => {
              const weak = subj.accuracy_pct < 50;
              const expanded = expandedSubjects[subj.subject_id];
              return (
                <div
                  key={subj.subject_id}
                  className={`border rounded-xl overflow-hidden ${weak ? "border-red-800" : "border-gray-800"}`}
                >
                  {/* Subject row */}
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedSubjects((p) => ({
                        ...p,
                        [subj.subject_id]: !p[subj.subject_id],
                      }))
                    }
                    className={`w-full flex items-center gap-4 px-5 py-3 text-left ${
                      weak ? "bg-red-950/40 hover:bg-red-950/60" : "bg-gray-900 hover:bg-gray-800"
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-white">{subj.subject_name}</span>
                        {weak && (
                          <span className="text-xs bg-red-900/60 text-red-300 px-2 py-0.5 rounded-full">
                            Weak
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {subj.correct} / {subj.questions} correct
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div
                        className={`text-lg font-bold ${
                          subj.accuracy_pct >= 70
                            ? "text-green-400"
                            : subj.accuracy_pct >= 50
                            ? "text-amber-400"
                            : "text-red-400"
                        }`}
                      >
                        {subj.accuracy_pct}%
                      </div>
                      <span className="text-gray-600 text-xs">{expanded ? "▲" : "▼"}</span>
                    </div>
                  </button>

                  {/* Topic breakdown */}
                  {expanded && (
                    <div className="border-t border-gray-800 divide-y divide-gray-800/60">
                      {subj.topics.map((topic) => {
                        const topicWeak = topic.accuracy_pct < 50;
                        return (
                          <div key={topic.topic_id} className="flex items-center gap-4 px-8 py-2.5">
                            <div className="flex-1 min-w-0">
                              <span className="text-sm text-gray-300">{topic.topic_name}</span>
                              <span className="text-xs text-gray-600 ml-2">
                                {topic.correct}/{topic.questions}
                              </span>
                            </div>
                            <span
                              className={`text-sm font-semibold ${
                                topic.accuracy_pct >= 70
                                  ? "text-green-400"
                                  : topic.accuracy_pct >= 50
                                  ? "text-amber-400"
                                  : "text-red-400"
                              }`}
                            >
                              {topic.accuracy_pct}%
                              {topicWeak && (
                                <span className="ml-1.5 text-xs font-normal text-red-400">⚠</span>
                              )}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="flex gap-4">
          <button
            onClick={() => {
              setView("setup");
              setQuiz(null);
              setResults(null);
              setAnswers({});
              setRevealed({});
            }}
            className="flex-1 bg-amber-600 hover:bg-amber-500 text-white py-2.5 rounded-xl text-sm font-medium"
          >
            New Simulation
          </button>
          <a
            href="/"
            className="flex-1 text-center border border-gray-700 text-gray-300 hover:text-white py-2.5 rounded-xl text-sm"
          >
            Dashboard
          </a>
        </div>
      </div>
    );
  }

  // ── Running view ───────────────────────────────────────────────────────────
  if (!quiz) return null;

  const q = quiz.questions[currentQ];
  const options = [
    { key: "a", text: q.option_a ?? "" },
    { key: "b", text: q.option_b ?? "" },
    { key: "c", text: q.option_c ?? "" },
    { key: "d", text: q.option_d ?? "" },
  ];
  const isLast = currentQ === quiz.questions.length - 1;
  const answered = Object.keys(answers).length;
  const timerDanger = remaining !== null && remaining <= 120;

  return (
    <div className="max-w-2xl space-y-6 pb-24">
      {/* Header bar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="font-semibold text-sm">
            Q {currentQ + 1} / {quiz.questions.length}
          </span>
          <span className="text-xs text-gray-500">{answered} answered</span>
        </div>
        {remaining !== null && (
          <div
            className={`font-mono text-sm font-bold px-3 py-1 rounded-lg ${
              timerDanger
                ? "bg-red-900/60 text-red-300 animate-pulse"
                : "bg-gray-800 text-gray-200"
            }`}
          >
            {fmtTime(remaining)}
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-amber-500 transition-all"
          style={{ width: `${(answered / quiz.questions.length) * 100}%` }}
        />
      </div>

      {/* Subject tag */}
      {q.subject_id && (
        <div className="text-xs text-gray-500 uppercase tracking-wide">
          {q.subject_id.replace(/_/g, " ")} · {q.subtopic_id?.replace(/_/g, " ")}
        </div>
      )}

      {/* Question */}
      <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
        <p className="text-white leading-relaxed whitespace-pre-wrap">{q.question_text}</p>
      </div>

      {/* Options */}
      <div className="space-y-3">
        {options.map((opt) => {
          const chosen = answers[currentQ] === opt.key;
          const correct = q.correct_answer === opt.key;
          const show = revealed[currentQ];
          return (
            <button
              key={opt.key}
              onClick={() => {
                if (!answers[currentQ])
                  setPendingAnswer(pendingAnswer === opt.key ? null : opt.key);
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

      {/* Submit pending answer */}
      {pendingAnswer && !answers[currentQ] && (
        <button
          onClick={() => {
            void submitAnswer(pendingAnswer);
            setPendingAnswer(null);
          }}
          className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-3 rounded-lg transition-colors"
        >
          Submit Answer
        </button>
      )}

      {/* Explanation */}
      {revealed[currentQ] && q.explanation && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
          <p className="text-amber-300 text-xs font-medium mb-1.5">Explanation</p>
          <p className="text-gray-300 text-sm leading-relaxed">{q.explanation}</p>
        </div>
      )}

      {/* Navigation */}
      <div className="flex gap-4 flex-wrap">
        {currentQ > 0 && (
          <button
            onClick={() => { setCurrentQ(currentQ - 1); setPendingAnswer(null); }}
            className="border border-gray-700 hover:border-gray-500 text-gray-300 hover:text-white px-4 py-2 rounded-lg text-sm transition-colors"
          >
            Previous
          </button>
        )}
        {revealed[currentQ] && !isLast && (
          <button
            onClick={() => { setCurrentQ(currentQ + 1); setPendingAnswer(null); }}
            className="bg-green-600 hover:bg-green-500 text-white px-6 py-2 rounded-lg text-sm"
          >
            Next
          </button>
        )}
        {revealed[currentQ] && isLast && (
          <button
            onClick={() => void finishExam()}
            disabled={finishLoading}
            className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-6 py-2 rounded-lg text-sm"
          >
            {finishLoading ? "Finishing..." : "Finish & See Results"}
          </button>
        )}
        {/* Skip unanswered and go next */}
        {!revealed[currentQ] && !isLast && (
          <button
            onClick={() => { setCurrentQ(currentQ + 1); setPendingAnswer(null); }}
            className="border border-gray-700 text-gray-500 hover:text-gray-300 px-4 py-2 rounded-lg text-sm"
          >
            Skip
          </button>
        )}
        {/* End simulation early */}
        <button
          onClick={() => void finishExam()}
          disabled={finishLoading}
          className="ml-auto border border-gray-700 text-gray-500 hover:text-red-400 hover:border-red-800 px-4 py-2 rounded-lg text-sm transition-colors"
        >
          End Simulation
        </button>
      </div>
    </div>
  );
}
