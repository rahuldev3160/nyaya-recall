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

// AI-generated quiz question shape — same wire shape as the existing UPSC Prelims
// /quiz/generate response (option_a..d + letter correct_answer), so the answer-check
// logic below matches web/src/app/diagnostic/page.tsx's existing convention rather than
// inventing a new one.
interface AiQuizQuestion {
  question_text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_answer: string;
  explanation: string;
  topic_id: string;
  dimension_id: string | null;
  difficulty: string;
}

type View = "pick_exam" | "pick_topic" | "quiz" | "done" | "ai_quiz" | "ai_done";

export default function NyayaPage() {
  const [view, setView] = useState<View>("pick_exam");
  const [examId, setExamId] = useState<string | null>(null);
  const [topics, setTopics] = useState<NyayaTopic[]>([]);
  const [topicId, setTopicId] = useState<string | null>(null);

  const [questions, setQuestions] = useState<NyayaQuestion[]>([]);
  const [idx, setIdx] = useState(0);
  const [chosen, setChosen] = useState<string | null>(null);
  const [result, setResult] = useState<NyayaAttemptResult | null>(null);
  const [score, setScore] = useState({ correct: 0, total: 0 });

  // Mode 2 — AI-generated quiz state (kept separate from Mode 1's state above so neither
  // flow's logic has to branch on the other).
  const [aiQuestions, setAiQuestions] = useState<AiQuizQuestion[]>([]);
  const [aiIdx, setAiIdx] = useState(0);
  const [aiChosen, setAiChosen] = useState<string | null>(null);
  const [aiScore, setAiScore] = useState({ correct: 0, total: 0 });
  const [aiInsufficientGrounding, setAiInsufficientGrounding] = useState(false);

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
        setChosen(null);
        setResult(null);
        setScore({ correct: 0, total: 0 });
        setView("quiz");
      } catch {
        setError("No quizzable real PYQs found for this selection.");
      } finally {
        setLoading(false);
      }
    },
    [examId]
  );

  // Mode 2 — AI-generated quiz, grounded in nyaya-core's real content (real PYQs +
  // whatever indexed explanation chunks exist) via POST /quiz/generate with exam_id set.
  // Unlike Mode 1, this always needs a specific topic (grounding is per-topic), so there
  // is no "mixed" option here.
  const startAiQuiz = useCallback(
    async (topic: string) => {
      if (!examId) return;
      setTopicId(topic);
      setError(null);
      setLoading(true);
      try {
        const data = await api.generateQuiz({
          exam_id: examId,
          subject_id: examId,
          topic_id: topic,
          num_questions: 10,
        });
        setAiQuestions(data.questions ?? []);
        setAiInsufficientGrounding(!!data.insufficient_grounding);
        setAiIdx(0);
        setAiChosen(null);
        setAiScore({ correct: 0, total: 0 });
        setView("ai_quiz");
      } catch (e) {
        const msg = e instanceof Error ? e.message : "";
        setError(
          msg.includes("422") || msg.toLowerCase().includes("insufficient")
            ? "Insufficient grounding for this topic — nyaya-core has no indexed content or real PYQs to generate from. Try a different topic."
            : "Could not generate an AI quiz — nyaya-core may be unreachable, or generation failed."
        );
      } finally {
        setLoading(false);
      }
    },
    [examId]
  );

  const answer = useCallback(
    async (option: string) => {
      if (chosen || !questions[idx]) return;
      setChosen(option);
      try {
        const r: NyayaAttemptResult = await api.recordNyayaAttempt(questions[idx].question_id, option);
        setResult(r);
        setScore((s) => ({ correct: s.correct + (r.is_correct ? 1 : 0), total: s.total + 1 }));
      } catch {
        setError("Could not record that attempt — nyaya-core may be unreachable.");
      }
    },
    [chosen, idx, questions]
  );

  function next() {
    if (idx + 1 < questions.length) {
      setIdx(idx + 1);
      setChosen(null);
      setResult(null);
    } else {
      setView("done");
    }
  }

  // Mode 2 answers are checked client-side (correct_answer ships with the question) —
  // same convention as diagnostic/page.tsx, safe here because a freshly AI-generated
  // question carries no memorization risk the way a real, reusable PYQ would.
  function answerAi(option: string) {
    if (aiChosen || !aiQuestions[aiIdx]) return;
    setAiChosen(option);
    const isCorrect = aiQuestions[aiIdx].correct_answer === option;
    setAiScore((s) => ({ correct: s.correct + (isCorrect ? 1 : 0), total: s.total + 1 }));
  }

  function nextAi() {
    if (aiIdx + 1 < aiQuestions.length) {
      setAiIdx(aiIdx + 1);
      setAiChosen(null);
    } else {
      setView("ai_done");
    }
  }

  const current = questions[idx];
  const aiCurrent = aiQuestions[aiIdx];

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-white">PFRDA / EPFO Practice</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          Drill real, previously-asked questions, or generate a fresh AI quiz grounded in
          nyaya-core&apos;s real content for a topic.
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
            Practice mixed — real PYQs, priority order across all topics
          </button>
          <div className="text-xs text-gray-500 uppercase tracking-wider mt-2">
            Or pick one topic — real PYQ drill or AI-generated quiz
          </div>
          <div className="flex flex-col gap-1.5 max-h-96 overflow-y-auto">
            {topics.map((t) => (
              <div
                key={t.topic_id}
                className="flex items-center gap-2 rounded-lg border border-gray-800 bg-gray-900 px-3 py-2"
              >
                <span className="flex-1 text-sm text-gray-200">{t.name}</span>
                <button
                  onClick={() => startQuiz(t.topic_id)}
                  className="text-xs px-2.5 py-1.5 rounded-md border border-gray-700 text-gray-300 hover:bg-gray-800"
                  title="Drill real, previously-asked questions on this topic"
                >
                  Real PYQs
                </button>
                <button
                  onClick={() => startAiQuiz(t.topic_id)}
                  className="text-xs px-2.5 py-1.5 rounded-md border border-purple-700 bg-purple-900/20 text-purple-300 hover:bg-purple-900/30"
                  title="Generate a fresh AI quiz grounded in nyaya-core's real content for this topic"
                >
                  AI Quiz
                </button>
              </div>
            ))}
          </div>
          <button onClick={() => setView("pick_exam")} className="text-sm text-gray-500 hover:text-gray-300 mt-2">
            ← Back to exam list
          </button>
        </div>
      )}

      {!loading && view === "quiz" && current && (
        <div className="flex flex-col gap-4">
          <div className="text-xs text-gray-500">
            Question {idx + 1} / {questions.length} · {score.correct}/{score.total} correct so far
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-white">{current.question_text}</div>
          <div className="flex flex-col gap-2">
            {current.options &&
              Object.entries(current.options).map(([letter, text]) => {
                const isChosen = chosen === letter;
                const isCorrect = result && result.correct_option === letter;
                const isWrongChoice = result && isChosen && !result.is_correct;
                return (
                  <button
                    key={letter}
                    disabled={!!chosen}
                    onClick={() => answer(letter)}
                    className={`text-left px-4 py-2.5 rounded-lg border text-sm ${
                      isCorrect
                        ? "border-green-600 bg-green-900/30 text-green-300"
                        : isWrongChoice
                        ? "border-red-600 bg-red-900/30 text-red-300"
                        : "border-gray-800 bg-gray-900 text-gray-200 hover:bg-gray-800"
                    } ${chosen ? "cursor-default" : "cursor-pointer"}`}
                  >
                    <span className="font-semibold">{letter})</span> {text}
                  </button>
                );
              })}
          </div>
          {result && (
            <div className="flex items-center justify-between">
              <span className={`text-sm font-medium ${result.is_correct ? "text-green-400" : "text-red-400"}`}>
                {result.is_correct ? "Correct!" : `Wrong — correct answer was ${result.correct_option}.`}
              </span>
              <button
                onClick={next}
                className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium"
              >
                {idx + 1 < questions.length ? "Next →" : "Finish"}
              </button>
            </div>
          )}
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

      {!loading && view === "ai_quiz" && aiCurrent && (
        <div className="flex flex-col gap-4">
          <div className="text-xs text-gray-500 flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300 border border-purple-700">
              AI-generated
            </span>
            Question {aiIdx + 1} / {aiQuestions.length} · {aiScore.correct}/{aiScore.total} correct so far
          </div>
          {aiInsufficientGrounding && (
            <div className="rounded-lg border border-yellow-700 bg-yellow-900/10 px-3 py-2 text-xs text-yellow-300">
              No indexed explanation content for this topic yet — these questions are grounded
              in real past questions only.
            </div>
          )}
          <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-white whitespace-pre-line">
            {aiCurrent.question_text}
          </div>
          <div className="flex flex-col gap-2">
            {([
              { key: "a", text: aiCurrent.option_a },
              { key: "b", text: aiCurrent.option_b },
              { key: "c", text: aiCurrent.option_c },
              { key: "d", text: aiCurrent.option_d },
            ] as const).map((opt) => {
              const isChosen = aiChosen === opt.key;
              const isCorrect = aiChosen && aiCurrent.correct_answer === opt.key;
              const isWrongChoice = aiChosen && isChosen && !isCorrect;
              return (
                <button
                  key={opt.key}
                  disabled={!!aiChosen}
                  onClick={() => answerAi(opt.key)}
                  className={`text-left px-4 py-2.5 rounded-lg border text-sm ${
                    isCorrect
                      ? "border-green-600 bg-green-900/30 text-green-300"
                      : isWrongChoice
                      ? "border-red-600 bg-red-900/30 text-red-300"
                      : "border-gray-800 bg-gray-900 text-gray-200 hover:bg-gray-800"
                  } ${aiChosen ? "cursor-default" : "cursor-pointer"}`}
                >
                  <span className="font-semibold">{opt.key})</span> {opt.text}
                </button>
              );
            })}
          </div>
          {aiChosen && (
            <div className="flex flex-col gap-3">
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 text-xs text-gray-300">
                {aiCurrent.explanation}
              </div>
              <div className="flex items-center justify-between">
                <span
                  className={`text-sm font-medium ${
                    aiCurrent.correct_answer === aiChosen ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {aiCurrent.correct_answer === aiChosen
                    ? "Correct!"
                    : `Wrong — correct answer was ${aiCurrent.correct_answer}.`}
                </span>
                <button
                  onClick={nextAi}
                  className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium"
                >
                  {aiIdx + 1 < aiQuestions.length ? "Next →" : "Finish"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {!loading && view === "ai_done" && (
        <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-gray-800 bg-gray-900 p-6 text-center">
            <div className="text-3xl font-bold text-purple-400">
              {aiScore.correct}/{aiScore.total}
            </div>
            <div className="text-sm text-gray-400 mt-1">
              {aiScore.total > 0 ? `${Math.round((aiScore.correct / aiScore.total) * 100)}% correct` : ""}
              {" "}· AI-generated quiz
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => topicId && startAiQuiz(topicId)}
              className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium"
            >
              Generate again
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
