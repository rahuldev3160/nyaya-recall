"use client";
import Link from "next/link";

export interface SubjectReadiness {
  subject_id: string;
  subject_name: string;
  readiness: number;
  subtopics_total: number;
  subtopics_tested: number;
  subtopics_weak: number;
  subtopics_partial: number;
  subtopics_strong: number;
}

interface HeatmapGridProps {
  subjects: SubjectReadiness[];
}

function buildSquares(subject: SubjectReadiness): ("untested" | "weak" | "partial" | "strong")[] {
  const total = subject.subtopics_total;
  if (total === 0) return [];

  const strong = subject.subtopics_strong;
  const partial = subject.subtopics_partial;
  const weak = subject.subtopics_weak;
  const untested = Math.max(0, total - strong - partial - weak);

  const squares: ("untested" | "weak" | "partial" | "strong")[] = [];
  for (let i = 0; i < strong; i++) squares.push("strong");
  for (let i = 0; i < partial; i++) squares.push("partial");
  for (let i = 0; i < weak; i++) squares.push("weak");
  for (let i = 0; i < untested; i++) squares.push("untested");
  return squares;
}

const SQUARE_COLOR: Record<"untested" | "weak" | "partial" | "strong", string> = {
  untested: "bg-gray-700",
  weak: "bg-red-500",
  partial: "bg-amber-500",
  strong: "bg-green-500",
};

export default function HeatmapGrid({ subjects }: HeatmapGridProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {subjects.map((subject) => {
        const squares = buildSquares(subject);
        const pct = Math.round(subject.readiness * 100);
        return (
          <Link
            key={subject.subject_id}
            href={`/progress?subject=${subject.subject_id}`}
            className="flex items-start gap-4 p-4 rounded-xl border border-gray-800 bg-gray-900 hover:border-gray-600 transition-colors"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-100 truncate">{subject.subject_name}</span>
                <span className="text-xs text-gray-400 ml-2 shrink-0">{pct}%</span>
              </div>
              <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500"
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-0.5 max-w-[80px] shrink-0">
              {squares.slice(0, 24).map((state, i) => (
                <div
                  key={i}
                  className={`w-2.5 h-2.5 rounded-sm ${SQUARE_COLOR[state]}`}
                />
              ))}
              {squares.length > 24 && (
                <div className="w-2.5 h-2.5 rounded-sm bg-gray-600 flex items-center justify-center">
                  <span className="text-[6px] text-gray-400">+</span>
                </div>
              )}
            </div>
          </Link>
        );
      })}
    </div>
  );
}
