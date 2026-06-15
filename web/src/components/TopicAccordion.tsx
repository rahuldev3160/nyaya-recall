"use client";

export interface TopicEntry {
  topic_id: string;
  label: string;
  total: number;
  attempted: number;
  correct: number;
}

interface Props {
  topics: TopicEntry[];
  selected: string | null;
  onSelect: (topicId: string) => void;
}

export default function TopicAccordion({ topics, selected, onSelect }: Props) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
        Select Topic
      </h2>
      <div className="flex flex-col gap-1.5">
        {topics.map((t) => {
          const pct = t.total > 0 ? Math.round((t.attempted / t.total) * 100) : 0;
          const acc = t.attempted > 0 ? Math.round((t.correct / t.attempted) * 100) : null;
          const isSelected = selected === t.topic_id;
          return (
            <button
              key={t.topic_id}
              onClick={() => onSelect(t.topic_id)}
              className={`flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-all ${
                isSelected
                  ? "border-amber-400 bg-amber-400/10"
                  : "border-gray-700 bg-gray-900 hover:border-gray-600"
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className={`text-sm font-medium truncate ${isSelected ? "text-amber-300" : "text-gray-200"}`}>
                  {t.label}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">{t.total} questions</div>
              </div>

              {pct > 0 ? (
                <div className="flex items-center gap-2 flex-shrink-0">
                  <div className="w-16 h-1.5 rounded-full bg-gray-700 overflow-hidden">
                    <div className="h-full rounded-full bg-amber-500" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-gray-400 w-10 text-right">
                    {acc !== null ? `${acc}%` : `${pct}%`}
                  </span>
                </div>
              ) : (
                <span className="text-xs text-gray-600 flex-shrink-0">Not started</span>
              )}

              <svg
                className={`w-4 h-4 flex-shrink-0 transition-transform ${isSelected ? "rotate-90 text-amber-400" : "text-gray-600"}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          );
        })}
      </div>
    </div>
  );
}
