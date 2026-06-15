"use client";

interface Explanation {
  concept_tested: string;
  correct_explanation: string;
  option_a_note: string | null;
  option_b_note: string | null;
  option_c_note: string | null;
  option_d_note: string | null;
  memory_hook: string | null;
}

interface Props {
  explanation: Explanation | null;
  correctAnswer: string; // "a" | "b" | "c" | "d"
  disputed?: boolean;
  disputeNote?: string | null;
  isPro?: boolean; // future gate; defaults to true (open until multi-user)
}

const OPTION_LABELS: Record<string, string> = { a: "A", b: "B", c: "C", d: "D" };

export default function ExplanationCard({
  explanation,
  correctAnswer,
  disputed = false,
  disputeNote,
  isPro = true,
}: Props) {
  if (!explanation) return null;

  if (!isPro) {
    return (
      <div className="mt-4 rounded-xl border border-amber-800/50 bg-amber-950/20 p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-amber-400">📖</span>
          <span className="text-sm font-semibold text-amber-300">Concept Explanation</span>
          <span className="ml-auto text-xs bg-amber-500/20 text-amber-400 border border-amber-700 rounded px-2 py-0.5">Pro</span>
        </div>
        <div className="blur-sm select-none text-xs text-gray-400 space-y-1">
          <p>Concept tested: [unlock to view]</p>
          <p>Why each option is wrong: [unlock to view]</p>
          <p>Memory hook: [unlock to view]</p>
        </div>
        <p className="mt-3 text-xs text-gray-500">
          Unlock full explanations with{" "}
          <a href="/pricing" className="text-amber-400 hover:underline">Pro — ₹3,999/year</a>
        </p>
      </div>
    );
  }

  const optionNotes: Array<{ key: string; note: string | null }> = [
    { key: "a", note: explanation.option_a_note },
    { key: "b", note: explanation.option_b_note },
    { key: "c", note: explanation.option_c_note },
    { key: "d", note: explanation.option_d_note },
  ];

  return (
    <div className="mt-4 rounded-xl border border-indigo-800/50 bg-indigo-950/20 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-indigo-400">📖</span>
        <span className="text-sm font-semibold text-indigo-300">Concept Explanation</span>
      </div>

      {/* Disputed banner */}
      {disputed && (
        <div className="rounded-lg border border-yellow-700 bg-yellow-900/20 px-3 py-2 text-xs text-yellow-300">
          ⚠️ UPSC's answer for this question has been disputed.
          {disputeNote && <span className="ml-1">{disputeNote}</span>}
        </div>
      )}

      {/* Concept tested */}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Concept Tested</p>
        <p className="text-sm text-gray-200">{explanation.concept_tested}</p>
      </div>

      {/* Option-by-option breakdown */}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Why Each Option</p>
        <div className="space-y-1.5">
          {optionNotes.map(({ key, note }) => {
            if (!note) return null;
            const isCorrect = key === correctAnswer.toLowerCase();
            return (
              <div
                key={key}
                className={`flex gap-2 text-sm rounded-lg px-3 py-2 ${
                  isCorrect
                    ? "bg-green-900/20 border border-green-800/50"
                    : "bg-gray-900/50 border border-gray-800/30"
                }`}
              >
                <span className={`font-semibold shrink-0 ${isCorrect ? "text-green-400" : "text-gray-500"}`}>
                  {OPTION_LABELS[key]}.{isCorrect && " ✓"}
                </span>
                <span className={isCorrect ? "text-green-200" : "text-gray-400"}>{note}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Memory hook */}
      {explanation.memory_hook && (
        <div className="rounded-lg border border-indigo-700/40 bg-indigo-900/20 px-3 py-2">
          <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wide mb-1">Lock It</p>
          <p className="text-sm text-indigo-200 italic">"{explanation.memory_hook}"</p>
        </div>
      )}
    </div>
  );
}
