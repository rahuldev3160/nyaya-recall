"use client";

export interface SubjectEntry {
  subject_id: string;
  label: string;
  total: number;
  attempted: number;
  correct: number;
}

interface Props {
  subjects: SubjectEntry[];
  selected: string | null;
  onSelect: (subjectId: string) => void;
}

const SUBJECT_COLOURS: Record<string, string> = {
  polity:          "border-blue-600 bg-blue-900/20",
  economy:         "border-green-600 bg-green-900/20",
  history_amac:    "border-yellow-600 bg-yellow-900/20",
  modern_history:  "border-orange-600 bg-orange-900/20",
  geography:       "border-teal-600 bg-teal-900/20",
  environment:     "border-emerald-600 bg-emerald-900/20",
  science_tech:    "border-purple-600 bg-purple-900/20",
  current_affairs: "border-rose-600 bg-rose-900/20",
  ir_governance:   "border-sky-600 bg-sky-900/20",
};

export default function SubjectCards({ subjects, selected, onSelect }: Props) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
        Select Subject
      </h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {subjects.map((s) => {
          const pct = s.total > 0 ? Math.round((s.attempted / s.total) * 100) : 0;
          const acc = s.attempted > 0 ? Math.round((s.correct / s.attempted) * 100) : null;
          const colourCls = SUBJECT_COLOURS[s.subject_id] ?? "border-gray-600 bg-gray-900/20";
          const isSelected = selected === s.subject_id;
          return (
            <button
              key={s.subject_id}
              onClick={() => onSelect(s.subject_id)}
              className={`rounded-xl border-2 p-3 text-left transition-all ${colourCls} ${
                isSelected ? "ring-2 ring-amber-400" : "hover:brightness-125"
              }`}
            >
              <div className="font-semibold text-sm text-gray-100 leading-tight">{s.label}</div>
              <div className="text-xs text-gray-400 mt-1">{s.total} questions</div>
              {pct > 0 && (
                <div className="mt-2">
                  <div className="h-1 w-full rounded-full bg-gray-700 overflow-hidden">
                    <div className="h-full rounded-full bg-amber-500" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="flex justify-between text-xs text-gray-500 mt-0.5">
                    <span>{pct}% done</span>
                    {acc !== null && <span>{acc}% acc</span>}
                  </div>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
