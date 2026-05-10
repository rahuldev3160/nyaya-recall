export default function StrategyPage() {
  return (
    <div className="max-w-2xl space-y-8">
      <h1 className="text-2xl font-bold">Exam Day Strategy</h1>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-4">
        <h2 className="text-lg font-semibold text-amber-400">Attempt Order (GS Paper 1)</h2>
        {[
          ["1", "Polity & Governance", "15-22 Qs", "25 min"],
          ["2", "Environment & Ecology", "10-15 Qs", "18 min"],
          ["3", "History (Ancient + Modern)", "12-18 Qs", "18 min"],
          ["4", "Economy", "10-14 Qs", "15 min"],
          ["5", "Geography + Mapping", "10-14 Qs", "15 min"],
          ["6", "Science & Technology", "6-10 Qs", "12 min"],
          ["7", "Current Affairs + IR", "15-22 Qs", "17 min"],
        ].map(([n, subj, qs, time]) => (
          <div key={n} className="flex items-center gap-4 text-sm">
            <span className="text-amber-400 font-bold w-4">{n}</span>
            <span className="flex-1 text-gray-200">{subj}</span>
            <span className="text-gray-500">{qs}</span>
            <span className="text-gray-400 w-14 text-right">{time}</span>
          </div>
        ))}
      </div>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-3">
        <h2 className="text-lg font-semibold text-amber-400">Guessing Rules</h2>
        {[
          "Never guess if you cannot confirm even 1 statement.",
          "Guess if you can eliminate 2 options — expected value is positive at –1/3.",
          "'Both A and B' answers: correct ~40% in recent PYQs.",
          "'None of the above': rare in recent years — treat with suspicion.",
          "Statements with absolute words (always, never, only) are often wrong.",
        ].map((rule, i) => (
          <div key={i} className="flex gap-3 text-sm">
            <span className="text-amber-500 mt-0.5">•</span>
            <span className="text-gray-300">{rule}</span>
          </div>
        ))}
      </div>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-3">
        <h2 className="text-lg font-semibold text-amber-400">PYQ Patterns — High-Frequency Topics</h2>
        {[
          ["Polity", "Schedule 7, Fundamental Rights (Art 14-32), Parliamentary procedures"],
          ["Environment", "Ramsar sites, Biodiversity hotspots, COP updates, Species in news"],
          ["Economy", "Budget terms, RBI tools, WTO, Economic Survey themes"],
          ["History", "Bhakti-Sufi movements, INC phases, Art forms"],
          ["Geography", "Rivers, Monsoon mechanism, Straits, Protected areas"],
          ["Science", "ISRO missions, Diseases, AI applications"],
        ].map(([subj, topics]) => (
          <div key={subj} className="text-sm">
            <span className="text-white font-medium">{subj}: </span>
            <span className="text-gray-400">{topics}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
