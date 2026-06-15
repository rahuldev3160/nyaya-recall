"use client";

interface SessionPauseScreenProps {
  correct: number;
  total: number;
  avgTimeSec: number;
  streak: number;
  weakTopics: string[];
  strongTopics: string[];
  onContinue: () => void;
  onExit: () => void;
}

export default function SessionPauseScreen({
  correct,
  total,
  avgTimeSec,
  streak,
  weakTopics,
  strongTopics,
  onContinue,
  onExit,
}: SessionPauseScreenProps) {
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
      <div className="w-full max-w-sm rounded-2xl border border-gray-700 bg-gray-900 p-6 space-y-5">
        <div className="text-center">
          <p className="text-green-400 text-base font-semibold">✓ 10 questions done</p>
        </div>

        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-gray-800 rounded-xl p-3">
            <div className="text-2xl font-bold text-white">{pct}%</div>
            <div className="text-xs text-gray-400 mt-0.5">Score</div>
          </div>
          <div className="bg-gray-800 rounded-xl p-3">
            <div className="text-2xl font-bold text-white">{avgTimeSec}s</div>
            <div className="text-xs text-gray-400 mt-0.5">Avg time</div>
          </div>
          <div className="bg-gray-800 rounded-xl p-3">
            <div className="text-2xl font-bold text-orange-400">{streak}</div>
            <div className="text-xs text-gray-400 mt-0.5">In a row</div>
          </div>
        </div>

        {weakTopics.length > 0 && (
          <div>
            <p className="text-xs text-red-400 font-medium mb-1">Weak spot</p>
            <ul className="space-y-0.5">
              {weakTopics.slice(0, 2).map((t, i) => (
                <li key={i} className="text-sm text-gray-300">🔴 {t}</li>
              ))}
            </ul>
          </div>
        )}

        {strongTopics.length > 0 && (
          <div>
            <p className="text-xs text-green-400 font-medium mb-1">Strong</p>
            <ul className="space-y-0.5">
              {strongTopics.slice(0, 2).map((t, i) => (
                <li key={i} className="text-sm text-gray-300">✓ {t}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-col gap-2 pt-1">
          <button
            onClick={onContinue}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-xl transition-colors"
          >
            Continue — 10 more →
          </button>
          <button
            onClick={onExit}
            className="w-full border border-gray-700 text-gray-300 hover:text-white py-3 rounded-xl transition-colors text-sm"
          >
            Save &amp; Exit
          </button>
        </div>
      </div>
    </div>
  );
}
