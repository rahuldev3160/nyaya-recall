"use client";

import Link from "next/link";

const FREE_FEATURES = [
  "Full adaptive quiz engine (unlimited sessions)",
  "PYQ Browser — all 1,985 Civil Services Prelims questions",
  "Subject heatmap + readiness tracker",
  "Streak tracking + daily challenge",
  "Spaced repetition (SRS) engine",
  "Session notes + concept deep-dives",
  "Community answer consensus badges",
];

const PRO_FEATURES = [
  "Everything in Free",
  "Full concept explanation cards on every PYQ",
  "Subtopic heatmap drill-down (blurred on Free)",
  "Overconfidence report — where you're dangerously wrong",
  "Cross-exam question discovery (CDS/NDA/CAPF PYQs)",
  "Weekly performance PDF export",
  "Priority support",
];

export default function PricingPage() {
  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-8 py-4">
      <div>
        <h1 className="text-2xl font-bold text-white">Plans</h1>
        <p className="text-sm text-gray-400 mt-1">
          Most features are free. Pro unlocks the content that turns your weak spots into locked-in concepts.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Free */}
        <div className="rounded-xl border border-gray-700 bg-gray-900 p-5 flex flex-col gap-4">
          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Free</div>
            <div className="text-3xl font-bold text-white">₹0</div>
            <div className="text-sm text-gray-500">forever</div>
          </div>
          <ul className="space-y-2 flex-1">
            {FREE_FEATURES.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-gray-300">
                <span className="text-green-500 shrink-0 mt-0.5">✓</span>
                {f}
              </li>
            ))}
          </ul>
          <Link
            href="/"
            className="block text-center rounded-lg border border-gray-700 px-4 py-2.5 text-sm text-gray-300 hover:border-gray-500 hover:text-white transition-colors"
          >
            Current plan
          </Link>
        </div>

        {/* Pro */}
        <div className="rounded-xl border border-amber-600 bg-amber-950/20 p-5 flex flex-col gap-4 relative overflow-hidden">
          {/* Coming soon ribbon */}
          <div className="absolute top-3 right-3 text-xs bg-amber-500/20 text-amber-400 border border-amber-700 rounded px-2 py-0.5 font-medium">
            Coming soon
          </div>

          <div>
            <div className="text-xs font-semibold text-amber-500 uppercase tracking-wide mb-1">Pro</div>
            <div className="text-3xl font-bold text-white">₹3,999</div>
            <div className="text-sm text-gray-500">per year · ~₹333/month</div>
          </div>
          <ul className="space-y-2 flex-1">
            {PRO_FEATURES.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-gray-200">
                <span className="text-amber-400 shrink-0 mt-0.5">✓</span>
                {f}
              </li>
            ))}
          </ul>
          <div className="rounded-lg border border-amber-700 bg-amber-500/10 px-4 py-3 text-xs text-amber-300">
            Pro is launching with the public platform. You&apos;ll be notified when it&apos;s available.
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
        <h2 className="text-sm font-semibold text-white mb-2">Why Pro?</h2>
        <p className="text-sm text-gray-400 leading-relaxed">
          The free tier gives you everything you need to prepare. Pro is for the extra 5% —
          the concept explanation cards that prevent you from making the same mistake twice,
          the overconfidence drill that surfaces the questions you <em>think</em> you know but don&apos;t,
          and the cross-exam bank that tests the same concept from 3 different angles.
        </p>
      </div>

      <div className="text-xs text-gray-600 text-center">
        Questions?{" "}
        <a href="mailto:dev.ucs0108@gmail.com" className="text-gray-500 hover:text-gray-300">
          dev.ucs0108@gmail.com
        </a>
      </div>
    </div>
  );
}
