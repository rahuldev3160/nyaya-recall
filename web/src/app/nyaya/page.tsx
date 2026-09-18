"use client";

import { useCallback, useState } from "react";
import { api, NyayaAttemptResult, NyayaQuestion, NyayaTopic } from "@/lib/api";

// PFRDA/EPFO content lives in the sibling nyaya-core project, not this repo's own DB —
// see backend/nyaya_core_client.py. Hardcoded to these two exams (not a generic /exams
// browser) because that's the real, current scope — extend this list if/when more exams
// land in nyaya-core with a UI here to match.
const EXAMS = [
  { exam_id: "pfrda_gradea", label: "PFRDA Grade A" },
  { exam_id: "upsc_epfo_apfc_eo_ao", label: "UPSC EPFO — APFC / EO-AO" },
];

type View = "pick_exam" | "pick_topic" | "quiz" | "done";

export default function NyayaPage() {
  const [view, setView] = useState<View>("pick_exam");
  const [examId, setExamId] = useState<string | null>(null);
  const [topics, setTopics] = useState<NyayaTopic[]>([]);
  const [topicId, setTopicId] = useState<string | null>(null);

  const [questions, setQuestions] = useState<NyayaQuestion[]>([]);
  const [idx, setIdx] = useState(0);
  // Per-question answer state, keyed by index — lets the learner step back to a
  // previously-answered question and see their own choice + the result again, instead
  // of that state being wiped the moment they move on (the reported "no back button"
  // gap: there was nothing to go back TO before this, since only the current question's
  // answer was ever kept in memory).
  const [answers, setAnswers] = useState<Record<number, { chosen: string; result: NyayaAttemptResult }>>({});

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectExam = useCallback(async (id: string) => {
    setExamId(id);
    setError(null);
    setLoading(true);
    try {
      const t: NyayaTopic[] = await api.getNyayaTopics(id);
      // Highest-weight topics first — same real-frequency signal nyaya-core's own
      // ranking uses, so the "browse a topic" list isn't just alphabetical noise.
      t.sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0));
      setTopics(t);
      setView("pick_topic");
    } catch {
      setError(
        "Could not reach nyaya-core. Make sure it's running: " +
          "`.venv/bin/python -m src.api.main` from the nyaya-core repo."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const startQuiz = useCallback(
    async (topic: string | null) => {
      if (!examId) return;
      setTopicId(topic);
      setError(null);
      setLoading(true);
      try {
        const qs: NyayaQuestion[] = await api.getNyayaQuiz(examId, {
          topicId: topic ?? undefined,
          n: 10,
        });
        setQuestions(qs);
        setIdx(0);
        setAnswers({});
        setView("quiz");
      } catch {
        setError("No quizzable real PYQs found for this selection.");
      } finally {
        setLoading(false);
      }
    },
    [examId]
  );

  const currentAnswer = answers[idx];

  const answer = useCallback(
    async (option: string) => {
      if (answers[idx] || !questions[idx]) return;
      try {
        const r: NyayaAttemptResult = await api.recordNyayaAttempt(questions[idx].question_id, option);
        setAnswers((a) => ({ ...a, [idx]: { chosen: option, result: r } }));
      } catch {
        setError("Could not record that attempt — nyaya-core may be unreachable.");
      }
    },
    [answers, idx, questions]
  );

  function next() {
    if (idx + 1 < questions.length) {
      setIdx(idx + 1);
    } else {
      setView("done");
    }
  }

  function prev() {
    if (idx > 0) setIdx(idx - 1);
  }

  const score = Object.values(answers).reduce(
    (s, a) => ({ correct: s.correct + (a.result.is_correct ? 1 : 0), total: s.total + 1 }),
    { correct: 0, total: 0 }
  );

  const current = questions[idx];

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-white">PFRDA / EPFO — Practice</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          A mix of real, previously-asked questions and AI-generated practice questions
          grounded in them — every question is labeled, never blended silently.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-700 bg-red-900/20 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading && <div className="text-sm text-gray-400">Loading…</div>}

      {!loading && view === "pick_exam" && (
        <div className="flex flex-col gap-3">
          {EXAMS.map((e) => (
            <button
              key={e.exam_id}
              onClick={() => selectExam(e.exam_id)}
              className="text-left px-4 py-3 rounded-lg border border-gray-800 bg-gray-900 hover:bg-gray-800 text-white"
            >
              {e.label}
            </button>
          ))}
        </div>
      )}

      {!loading && view === "pick_topic" && (
        <div className="flex flex-col gap-3">
          <button
            onClick={() => startQuiz(null)}
            className="text-left px-4 py-3 rounded-lg border border-amber-700 bg-amber-900/20 hover:bg-amber-900/30 text-amber-300 font-medium"
          >
            Practice mixed — priority order across all topics
          </button>
          <div className="text-xs text-gray-500 uppercase tracking-wider mt-2">Or pick one topic</div>
          <div className="flex flex-col gap-1.5 max-h-96 overflow-y-auto">
            {topics.map((t) => (
              <button
                key={t.topic_id}
                onClick={() => startQuiz(t.topic_id)}
                className="text-left px-3 py-2 rounded-lg border border-gray-800 bg-gray-900 hover:bg-gray-800 text-sm text-gray-200"
              >
                {t.name}
              </button>
            ))}
          </div>
          <button onClick={() => setView("pick_exam")} className="text-sm text-gray-500 hover:text-gray-300 mt-2">
            ← Back to exam list
          </button>
        </div>
      )}

      {!loading && view === "quiz" && current && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="text-xs text-gray-500">
              Question {idx + 1} / {questions.length} · {score.correct}/{score.total} correct so far
            </div>
            <button
              onClick={() => setView("pick_topic")}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              ✕ Exit quiz
            </button>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-white">
            <span
              className={`inline-block mb-2 px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${
                current.source_type === "ai_generated"
                  ? "bg-purple-900/40 text-purple-300 border border-purple-700"
                  : "bg-emerald-900/40 text-emerald-300 border border-emerald-700"
              }`}
            >
              {current.source_type === "ai_generated" ? "AI-Generated" : "Real PYQ"}
            </span>
            <div>{current.question_text}</div>
          </div>
          <div className="flex flex-col gap-2">
            {current.options &&
              Object.entries(current.options).map(([letter, text]) => {
                const isChosen = currentAnswer?.chosen === letter;
                const isCorrect = currentAnswer && currentAnswer.result.correct_option === letter;
                const isWrongChoice = currentAnswer && isChosen && !currentAnswer.result.is_correct;
                return (
                  <button
                    key={letter}
                    disabled={!!currentAnswer}
                    onClick={() => answer(letter)}
                    className={`text-left px-4 py-2.5 rounded-lg border text-sm ${
                      isCorrect
                        ? "border-green-600 bg-green-900/30 text-green-300"
                        : isWrongChoice
                        ? "border-red-600 bg-red-900/30 text-red-300"
                        : "border-gray-800 bg-gray-900 text-gray-200 hover:bg-gray-800"
                    } ${currentAnswer ? "cursor-default" : "cursor-pointer"}`}
                  >
                    <span className="font-semibold">{letter})</span> {text}
                  </button>
                );
              })}
          </div>
          {currentAnswer && (
            <div
              className={`text-sm font-medium ${
                currentAnswer.result.is_correct ? "text-green-400" : "text-red-400"
              }`}
            >
              {currentAnswer.result.is_correct
                ? "Correct!"
                : `Wrong — correct answer was ${currentAnswer.result.correct_option}.`}
            </div>
          )}
          <div className="flex items-center justify-between">
            <button
              onClick={prev}
              disabled={idx === 0}
              className="px-4 py-2 rounded-lg border border-gray-800 text-gray-300 hover:bg-gray-800 text-sm disabled:opacity-30 disabled:pointer-events-none"
            >
              ← Previous
            </button>
            {currentAnswer && (
              <button
                onClick={next}
                className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium"
              >
                {idx + 1 < questions.length ? "Next →" : "Finish"}
              </button>
            )}
          </div>
        </div>
      )}

      {!loading && view === "done" && (
        <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-gray-800 bg-gray-900 p-6 text-center">
            <div className="text-3xl font-bold text-amber-400">
              {score.correct}/{score.total}
            </div>
            <div className="text-sm text-gray-400 mt-1">
              {score.total > 0 ? `${Math.round((score.correct / score.total) * 100)}% correct` : ""}
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => startQuiz(topicId)}
              className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium"
            >
              Practice again
            </button>
            <button
              onClick={() => setView("pick_topic")}
              className="px-4 py-2 rounded-lg border border-gray-800 text-gray-300 hover:bg-gray-800 text-sm"
            >
              Change topic
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
