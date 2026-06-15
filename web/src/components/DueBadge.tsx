"use client";
import Link from "next/link";

interface DueBadgeProps {
  count: number;
}

export default function DueBadge({ count }: DueBadgeProps) {
  const display = count >= 99 ? "99+" : String(count);
  return (
    <Link
      href="/practice?mode=due"
      className="inline-flex items-center gap-1 px-3 py-1 rounded-full border border-red-800 bg-red-950 text-red-400 text-sm font-medium hover:bg-red-900 transition-colors"
    >
      {display} due
    </Link>
  );
}
