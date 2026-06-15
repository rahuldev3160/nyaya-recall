"use client";

interface StreakBadgeProps {
  streak: number;
  atRisk?: boolean;
}

export default function StreakBadge({ streak, atRisk = false }: StreakBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-3 py-1 rounded-full border border-orange-800 bg-orange-950 text-orange-400 text-sm font-medium${
        atRisk ? " animate-pulse" : ""
      }`}
    >
      🔥 {streak}
    </span>
  );
}
