"use client";
import { useState } from "react";
import { api } from "@/lib/api";

const SUBJECTS = [
  { id: "polity", label: "Polity & Governance" },
  { id: "history_amac", label: "Ancient, Medieval & Art Culture" },
  { id: "modern_history", label: "Modern History" },
  { id: "geography", label: "Geography" },
  { id: "economy", label: "Economy" },
  { id: "environment", label: "Environment & Ecology" },
  { id: "science_tech", label: "Science & Technology" },
  { id: "current_affairs", label: "Current Affairs" },
  { id: "ir_governance", label: "IR & Governance" },
];

const LEVELS = [
  { key: "strong", label: "Strong", desc: "~70% accuracy in mock tests", color: "text-green-400" },
  { key: "very_strong", label: "Very Strong", desc: "~85% accuracy", color: "text-blue-400" },
  { key: "expert", label: "Expert", desc: "~95% accuracy, rarely miss", color: "text-purple-400" },
];

type Phase = "config" | "quiz" | "result";

export default function AttestationPage() {
  const [subject, setSubject] = useState("");
  const [level, setLevel] = useState("strong");
  const [phase, setPhase] = useState<Phase>("config");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [questions, setQuestions] = useState<any[]>([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<{ is_correct: boolean; option: string }[]>([]);
  const [revealed, setRevealed] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [claimedLabel, setClaimedLabel] = useState("");
  const [subjectId, setSubjectId] = useState("");

  const startAttestation = async () => {
    if (!subject) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.submitAttestation({ subject_id: subject, claimed_label: level });
      setQuestions(data.questions);
      setClaimedLabel(data.claimed_label);
      setSubjectId(data.subject_id);
      setCurrentQ(0);
      setAnswers([]);
      setRevealed(false);
      setPhase("quiz");
    } catch (e: any) {
      setError("Failed to generate validation quiz. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const selectAnswer = (opt: string) => {
    if (revealed) return;
    const q = questions[currentQ];
    setAnswers((prev) => [...prev, { is_correct: q.correct_answer === opt, option: opt }]);
    setRevealed(true);
  };

  const next = async () => {
    if (currentQ < questions.length - 1) {
      setCurrentQ((q) => q + 1);
      setRevealed(false);
    } else {
      setLoading(true);
      try {
        const res = await api.validateAttestation({
          subject_id: subjectId,
          claimed_label: claimedLabel,
          answers,
        });
        setResult(res);
        setPhase("result");
      } catch (e: any) {
        setError("Validation failed. Try again.");
      } finally {
        setLoading(false);
      }
    }
  };

  const reset = () => {
    setPhase("config");
    setSubject("");
    setLevel("strong");
    setQuestions([]);
    setAnswers([]);
    setResult(null);
    setError(null);
  };

  if (phase === "config") {
    return (
      <div className="max-w-xl space-y-8">
        <div>
          <h1 className="text-2xl font-bold">Self-Attestation</h1>
          <p className="text-gray-400 text-sm mt-2">
            Claim your preparation level for a subject. A 12-question validation quiz
            calibrates how much your claim is trusted vs actual performance.
          </p>
        </div>

        {error && (
          <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-red-300 text-sm">{error}</div>
        )}

        <div className="space-y-3">
          <label className="block text-sm text-gray-400 font-medium">Subject</label>
          <div className="grid grid-cols-1 gap-2">
            {SUBJECTS.map((s) => (
              <button key={s.id} onClick={() => setSubject(s.id)}
                className={`text-left px-4 py-3 rounded-lg border transition-colors text-sm ${
                  subject === s.id
                    ? "border-amber-500 bg-amber-500/10 text-amber-300"
                    : "border-gray-700 hover:border-gray-500 text-gray-300"
                }`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <label className="block text-sm text-gray-400 font-medium">Claimed Level</label>
          <div className="space-y-2">
            {LEVELS.map((l) => (
              <button key={l.key} onClick={() => setLevel(l.key)}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                  level === l.key
                    ? "border-amber-500 bg-amber-500/10"
                    : "border-gray-700 hover:border-gray-600"
                }`}>
                <div className={`font-medium text-sm ${l.color}`}>{l.label}</div>
                <div className="text-gray-500 text-xs mt-0.5">{l.desc}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-xs text-gray-500 space-y-1">
          <p className="text-gray-400 font-medium text-sm mb-2">How SAR works</p>
          <p>Your Self-Assessment Reliability (SAR) score starts at 0.50 and adjusts based on how closely your claim matches your quiz performance.</p>
          <p className="mt-1">effective_level = (quiz_score × (1 − SAR)) + (claimed × SAR)</p>
          <p className="mt-1">Consistent honest claims push SAR toward 0.90; large discrepancies pull it toward 0.20.</p>
        </div>

        <button onClick={startAttestation} disabled={!subject || loading}
          className="w-full bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white py-3 rounded-lg font-medium">
          {loading ? "Generating validation quiz..." : "Start Validation Quiz (12 Qs)"}
        </button>
      </div>
    );
  }

  if (phase === "quiz") {
    const q = questions[currentQ];
    const options = [
      { key: "a", text: q.option_a ?? "" }, { key: "b", text: q.option_b ?? "" },
      { key: "c", text: q.option_c ?? "" }, { key: "d", text: q.option_d ?? "" },
    ];
    const chosen = answers[currentQ]?.option;

    return (
      <div className="max-w-2xl space-y-6">
        <div className="flex justify-between items-center">
          <h2 className="font-semibold">Validation Q {currentQ + 1} / {questions.length}</h2>
          <span className="text-gray-500 text-sm">{SUBJECTS.find((s) => s.id === subjectId)?.label}</span>
        </div>

        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
          <p className="text-white leading-relaxed">{q.question_text}</p>
        </div>

        <div className="space-y-3">
          {options.map((opt) => {
            const isChosen = chosen === opt.key;
            const isCorrect = q.correct_answer === opt.key;
            return (
              <button key={opt.key} onClick={() => selectAnswer(opt.key)} disabled={revealed}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                  revealed && isCorrect ? "border-green-500 bg-green-500/10 text-green-300" :
                  revealed && isChosen ? "border-red-500 bg-red-500/10 text-red-300" :
                  "border-gray-700 hover:border-gray-500 text-gray-200"
                }`}>
                <span className="font-medium mr-3 text-gray-500">({opt.key})</span>{opt.text}
              </button>
            );
          })}
        </div>

        {revealed && q.explanation && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
            <p className="text-amber-300 text-sm font-medium mb-1">Explanation</p>
            <p className="text-gray-300 text-sm">{q.explanation}</p>
          </div>
        )}

        {error && (
          <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-red-300 text-sm">{error}</div>
        )}

        {revealed && (
          <button onClick={next} disabled={loading}
            className="bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white px-6 py-2 rounded-lg">
            {loading ? "Calculating..." : currentQ < questions.length - 1 ? "Next →" : "Submit & See Result"}
          </button>
        )}
      </div>
    );
  }

  if (phase === "result" && result) {
    // Backend sends: sar_before, sar_after, validation_score, effective_level, claimed_level, discrepancy
    const sarBefore = result.sar_before ?? 0.5;
    const sarAfter = result.sar_after ?? sarBefore;
    const sarPct = Math.round(sarAfter * 100);
    const sarDelta = sarAfter - sarBefore;
    const effectivePct = Math.round(result.effective_level ?? 0);
    const validationPct = Math.round(result.validation_score ?? 0);

    return (
      <div className="max-w-xl space-y-6">
        <h1 className="text-2xl font-bold">Attestation Result</h1>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-sm">Validation score</span>
            <span className="text-white font-semibold">{validationPct}%</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-sm">Effective level (used by system)</span>
            <span className={`font-bold text-lg ${
              effectivePct >= 75 ? "text-green-400" : effectivePct >= 50 ? "text-amber-400" : "text-red-400"
            }`}>{effectivePct}%</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-sm">New SAR score</span>
            <span className="text-white font-medium">
              {sarPct}%{" "}
              <span className={`text-xs ml-1 ${sarDelta > 0 ? "text-green-400" : sarDelta < 0 ? "text-red-400" : "text-gray-500"}`}>
                {sarDelta > 0.001 ? `+${(sarDelta * 100).toFixed(0)}pts` : sarDelta < -0.001 ? `${(sarDelta * 100).toFixed(0)}pts` : "no change"}
              </span>
            </span>
          </div>

          <div className="w-full bg-gray-800 rounded-full h-2">
            <div className="h-2 rounded-full bg-amber-500 transition-all" style={{ width: `${effectivePct}%` }} />
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-sm text-gray-400">
          <p>
            Your claimed level was <span className="text-white">{claimedLabel}</span>.
            The system combined your quiz performance ({validationPct}%) with your claim
            using SAR ({sarPct}%) to set your effective level at{" "}
            <span className="text-amber-300 font-medium">{effectivePct}%</span>.
          </p>
          {(result.discrepancy ?? 0) > 15 && (
            <p className="mt-2 text-amber-400">
              Large gap detected between claim and quiz — SAR adjusted accordingly.
              Future plans will lean more on quiz data.
            </p>
          )}
        </div>

        <button onClick={reset} className="w-full border border-gray-700 hover:border-gray-500 text-gray-300 py-2 rounded-lg text-sm">
          Attest another subject
        </button>
      </div>
    );
  }

  return null;
}
