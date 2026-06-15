"use client";
import Link from "next/link";

interface GateCtaProps {
  title: string;
  features: string[];
  triggerMoment: string;
}

export default function GateCta({ title, features }: GateCtaProps) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-5 space-y-4">
      <div className="flex items-start gap-3">
        <span className="text-xl">🔒</span>
        <div>
          <p className="text-white font-semibold">{title}</p>
        </div>
      </div>

      <ul className="space-y-1.5">
        {features.map((f, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
            <span className="text-blue-400 mt-0.5 shrink-0">•</span>
            {f}
          </li>
        ))}
      </ul>

      <div>
        <Link
          href="/pricing"
          className="block w-full text-center bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-xl transition-colors"
        >
          Unlock Recall Pro →
        </Link>
        <p className="text-center text-xs text-gray-500 mt-2">₹3,999/year</p>
        <p className="text-center text-xs text-gray-500">
          or share with 3 friends for 7 days free
        </p>
      </div>
    </div>
  );
}
