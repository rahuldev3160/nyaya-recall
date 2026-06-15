"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { api } from "@/lib/api";

interface SubjectCard {
  id: string;
  name: string;
  readiness: number;
  isWeak: boolean;
  isDue: boolean;
}

function scoreColor(pct: number) {
  if (pct >= 70) return "text-green-400";
  if (pct >= 40) return "text-amber-400";
  return "text-red-400";
}

type Filter = "all" | "due" | "weak";

function PracticePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const modeParam = searchParams.get("mode");
  const initialFilter: Filter = modeParam === "due" ? "due" : "all";

  const [subjects, setSubjects] = useState<SubjectCard[]>([]);
  const [filter, setFilter] = useState<Filter>(initialFilter);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const raw = await api.getSubjects();
        const arr: Record<string, unknown>[] = Array.isArray(raw)
          ? (raw as Record<string, unknown>[])
          : typeof raw === "object" && raw !== null
          ? Object.values(raw as Record<string, Record<string, unknown>>)
          : [];

        const mapped: SubjectCard[] = arr.map((s: Record<string, unknown>) => {
          const score = typeof s.avg_score === "number" ? (s.avg_score as number) :
            typeof s.readiness === "number" ? (s.readiness as number) * 100 : 0;
          return {
            id: String(s.subject_id ?? s.id ?? ""),
            name: String(s.subject_name ?? s.name ?? "Unknown"),
            readiness: Math.round(score),
            isWeak: score < 40,
            isDue: false, // placeholder until due-per-subject endpoint exists
          };
        });
        setSubjects(mapped);
      } catch {
        // Fallback to known subject list with zero readiness
        const FALLBACK = [
          { id: "polity", name: "Polity & Governance" },
          { id: "history_amac", name: "Ancient, Medieval & Culture" },
          { id: "modern_history", name: "Modern History" },
          { id: "geography", name: "Geography" },
          { id: "economy", name: "Economy" },
          { id: "environment", name: "Environment" },
          { id: "science_tech", name: "Science & Tech" },
          { id: "current_affairs", name: "Current Affairs" },
        ];
        setSubjects(FALLBACK.map((s) => ({ ...s, readiness: 0, isWeak: false, isDue: false })));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = subjects.filter((s) => {
    if (filter === "weak") return s.isWeak;
    if (filter === "due") return s.isDue;
    return true;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Choose your drill</h1>
        <p className="text-gray-400 text-sm mt-1">Pick a subject to start a diagnostic session.</p>
      </div>

      {/* Quick filters */}
      <div className="flex gap-2">
        {(["all", "due", "weak"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${
              filter === f
                ? "border-blue-600 bg-blue-950 text-blue-300"
                : "border-gray-700 bg-gray-900 text-gray-400 hover:text-gray-200"
            }`}
          >
            {f === "all" ? "All" : f === "due" ? "Due for review" : "Weak only"}
          </button>
        ))}
      </div>

      {/* Subject grid */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-gray-800 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-8 text-center text-gray-400 text-sm">
          {filter === "weak"
            ? "No weak subjects found — great work!"
            : filter === "due"
            ? "Nothing due for review right now."
            : "No subjects found."}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {filtered.map((s) => (
            <button
              key={s.id}
              onClick={() => router.push(`/diagnostic?subject=${s.id}`)}
              className="flex flex-col items-start p-4 rounded-xl border border-gray-800 bg-gray-900 hover:border-gray-600 hover:bg-gray-800 transition-colors text-left"
            >
              <span className="text-sm font-medium text-gray-100 leading-tight mb-2">
                {s.name}
              </span>
              <span className={`text-lg font-bold ${scoreColor(s.readiness)}`}>
                {s.readiness > 0 ? `${s.readiness}%` : "—"}
              </span>
              {s.readiness > 0 && (
                <div className="w-full mt-2 h-1 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      s.readiness >= 70
                        ? "bg-green-500"
                        : s.readiness >= 40
                        ? "bg-amber-500"
                        : "bg-red-500"
                    }`}
                    style={{ width: `${s.readiness}%` }}
                  />
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Wrap in Suspense because useSearchParams requires it in Next.js 14 App Router
export default function PracticePageWrapper() {
  return (
    <Suspense fallback={
      <div className="space-y-6">
        <div className="h-10 w-48 bg-gray-800 animate-pulse rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-gray-800 animate-pulse" />
          ))}
        </div>
      </div>
    }>
      <PracticePage />
    </Suspense>
  );
}
