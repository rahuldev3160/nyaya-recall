"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";

export interface PYQQuestion {
  id: number;
  question_text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_answer: string;
  subtopic_id: string | null;
  answer_source: string;
  answer_disputed: boolean;
  user_answer: string | null;
  user_correct: boolean | null;
}

interface Props {
  questions: PYQQuestion[];
  year: number;
  onDone: () => void;
}

const OPTIONS: Array<{ key: "a" | "b" | "c" | "d"; label: string }> = [
  { key: "a", label: "A" },
  { key: "b", label: "B" },
  { key: "c", label: "C" },
  { key: "d", label: "D" },
];

type RevealState = { revealed: true; correct: boolean; correctAnswer: string } | { revealed: false };

export default function PYQQuizRunner({ questions, year, onDone }: Props) {
  const [idx, setIdx] = useState(() => {
    // Start at first unattempted question
    const first = questions.findIndex((q) => q.user_answer === null);
    return first === -1 ? 0 : first;
  });
  const [reveal, setReveal] = useState<RevealState>({ revealed: false });
  const [submitting, setSubmitting] = useState(false);
  const [sessionCorrect, setSessionCorrect] = useState(0);
  const [sessionAttempted, setSessionAttempted] = useState(0);
  const startRef = useRef<number>(Date.now());

  const q = questions[idx];

  useEffect(() => {
    // When navigating to a question that's already answered, show reveal
    if (q?.user_answer !== null && q?.user_answer !== undefined) {
      setReveal({
        revealed: true,
        correct: !!q.user_correct,
        correctAnswer: q.correct_answer,
      });
    } else {
      setReveal({ revealed: false });
    }
    startRef.current = Date.now();
  }, [idx, q]);

  async function handleAnswer(option: string) {
    if (reveal.revealed || submitting) return;
    setSubmitting(true);
    const timeSec = Math.round((Date.now() - startRef.current) / 1000);
    try {
      const result = await api.recordPYQAttempt({
        question_id: q.id,
        answer: option,
        time_taken_sec: timeSec,
      });
      setReveal({ revealed: true, correct: result.correct, correctAnswer: result.correct_answer });
      setSessionAttempted((n) => n + 1);
      if (result.correct) setSessionCorrect((n) => n + 1);
      // Update local state so navigating back shows result
      q.user_answer = option;
      q.user_correct = result.correct;
    } catch {
      // Silent fail — don't block the user
    } finally {
      setSubmitting(false);
    }
  }

  function optionText(key: "a" | "b" | "c" | "d") {
    return q[`option_${key}`];
  }

  function optionClass(key: string) {
    const base = "w-full text-left rounded-lg border px-4 py-3 text-sm transition-all ";
    if (!reveal.revealed) {
      return base + "border-gray-700 bg-gray-900 text-gray-200 hover:border-amber-500 hover:bg-amber-500/5 cursor-pointer";
    }
    const correctKey = reveal.revealed ? reveal.correctAnswer.toLowerCase() : "";
    if (key === correctKey) {
      return base + "border-green-500 bg-green-900/30 text-green-200";
    }
    if (reveal.revealed && q.user_answer?.toLowerCase() === key && key !== correctKey) {
      return base + "border-red-500 bg-red-900/20 text-red-300";
    }
    return base + "border-gray-800 bg-gray-900/50 text-gray-500 cursor-default";
  }

  const progress = Math.round(
    (questions.filter((q) => q.user_answer !== null).length / questions.length) * 100
  );

  return (
    <div className="flex flex-col gap-4">
      {/* Progress bar + session stats */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-1.5 rounded-full bg-gray-800 overflow-hidden">
          <div className="h-full rounded-full bg-amber-500 transition-all" style={{ width: `${progress}%` }} />
        </div>
        <span className="text-xs text-gray-500 whitespace-nowrap">
          {idx + 1}/{questions.length}
        </span>
        {sessionAttempted > 0 && (
          <span className="text-xs text-amber-400 whitespace-nowrap">
            {sessionCorrect}/{sessionAttempted} this session
          </span>
        )}
      </div>

      {/* Question card */}
      <div className="rounded-xl border border-gray-700 bg-gray-900 p-5">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-mono text-gray-500">
            {year} · Q{idx + 1}
          </span>
          {q.answer_disputed && (
            <span className="text-xs bg-yellow-900/50 text-yellow-400 border border-yellow-700 rounded px-1.5 py-0.5">
              Disputed
            </span>
          )}
          {q.answer_source === "official_key" && (
            <span className="text-xs bg-green-900/30 text-green-400 border border-green-800 rounded px-1.5 py-0.5">
              Official Key
            </span>
          )}
          {q.user_answer !== null && (
            <span className={`text-xs rounded px-1.5 py-0.5 border ${
              q.user_correct
                ? "bg-green-900/30 text-green-400 border-green-800"
                : "bg-red-900/20 text-red-400 border-red-800"
            }`}>
              {q.user_correct ? "Correct" : "Incorrect"}
            </span>
          )}
        </div>

        <p className="text-gray-100 text-sm leading-relaxed mb-5 whitespace-pre-wrap">{q.question_text}</p>

        <div className="flex flex-col gap-2">
          {OPTIONS.map(({ key, label }) => (
            <button
              key={key}
              className={optionClass(key)}
              onClick={() => handleAnswer(key)}
              disabled={reveal.revealed || submitting}
            >
              <span className="font-semibold text-gray-500 mr-2">{label}.</span>
              {optionText(key)}
            </button>
          ))}
        </div>

        {reveal.revealed && (
          <div className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
            reveal.correct
              ? "border-green-700 bg-green-900/20 text-green-300"
              : "border-red-700 bg-red-900/20 text-red-300"
          }`}>
            {reveal.correct ? "Correct!" : `Incorrect. Correct answer: ${reveal.correctAnswer.toUpperCase()}`}
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between gap-3">
        <button
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
          disabled={idx === 0}
          className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-400 hover:text-white hover:border-gray-500 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ← Prev
        </button>

        <div className="flex gap-1 flex-wrap justify-center">
          {questions.map((qItem, i) => (
            <button
              key={qItem.id}
              onClick={() => setIdx(i)}
              className={`w-7 h-7 rounded text-xs font-mono transition-all ${
                i === idx
                  ? "bg-amber-500 text-black"
                  : qItem.user_answer !== null
                  ? qItem.user_correct
                    ? "bg-green-700 text-green-100"
                    : "bg-red-700 text-red-100"
                  : "bg-gray-800 text-gray-500 hover:bg-gray-700"
              }`}
            >
              {i + 1}
            </button>
          ))}
        </div>

        {idx < questions.length - 1 ? (
          <button
            onClick={() => setIdx((i) => Math.min(questions.length - 1, i + 1))}
            className="rounded-lg border border-amber-700 bg-amber-900/20 px-4 py-2 text-sm text-amber-300 hover:bg-amber-800/30"
          >
            Next →
          </button>
        ) : (
          <button
            onClick={onDone}
            className="rounded-lg border border-amber-500 bg-amber-500/20 px-4 py-2 text-sm text-amber-300 hover:bg-amber-500/30"
          >
            Done
          </button>
        )}
      </div>
    </div>
  );
}
