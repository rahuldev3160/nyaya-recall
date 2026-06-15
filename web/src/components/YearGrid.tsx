"use client";

export interface YearEntry {
  year: number;
  total: number;
  attempted: number;
  correct: number;
}

interface Props {
  years: YearEntry[];
  selected: number | null;
  onSelect: (year: number) => void;
}

export default function YearGrid({ years, selected, onSelect }: Props) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
        Select Year
      </h2>
      <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
        {years.map((y) => {
          const pct = y.total > 0 ? Math.round((y.attempted / y.total) * 100) : 0;
          const acc = y.attempted > 0 ? Math.round((y.correct / y.attempted) * 100) : null;
          const isSelected = selected === y.year;
          return (
            <button
              key={y.year}
              onClick={() => onSelect(y.year)}
              className={`relative rounded-lg border p-2 text-center transition-all ${
                isSelected
                  ? "border-amber-400 bg-amber-400/10 text-amber-300"
                  : "border-gray-700 bg-gray-900 text-gray-300 hover:border-gray-500"
              }`}
            >
              <div className="text-base font-bold">{y.year}</div>
              <div className="text-xs text-gray-500 mt-0.5">{y.total}Q</div>
              {pct > 0 && (
                <div className="mt-1">
                  <div className="h-1 w-full rounded-full bg-gray-700 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-amber-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  {acc !== null && (
                    <div className="text-xs text-gray-500 mt-0.5">{acc}%</div>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
