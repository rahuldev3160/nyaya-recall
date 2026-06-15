"use client";

interface TodaysFocusProps {
  subtopic_name: string;
  subject_name: string;
  estimated_questions: number;
  estimated_minutes: number;
  onStart: () => void;
}

export default function TodaysFocus({
  subtopic_name,
  subject_name,
  estimated_questions,
  estimated_minutes,
  onStart,
}: TodaysFocusProps) {
  return (
    <div className="w-full rounded-xl border border-blue-700/60 bg-gray-900 p-5 shadow-[0_0_0_1px_rgba(59,130,246,0.15)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-blue-400 font-semibold mb-1">
            Today&apos;s Focus
          </p>
          <h2 className="text-lg font-bold text-white leading-tight">{subtopic_name}</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            {subject_name} · {estimated_questions} questions · ~{estimated_minutes} min
          </p>
        </div>
        <button
          onClick={onStart}
          className="shrink-0 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-5 py-2.5 rounded-lg transition-colors text-sm whitespace-nowrap"
        >
          Start Today&apos;s Drill →
        </button>
      </div>
    </div>
  );
}
