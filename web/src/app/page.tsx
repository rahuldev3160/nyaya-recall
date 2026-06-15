"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { getStreakInfo, getDueCount } from "@/lib/api";
import StreakBadge from "@/components/StreakBadge";
import DueBadge from "@/components/DueBadge";
import HeatmapGrid, { SubjectReadiness } from "@/components/HeatmapGrid";
import TodaysFocus from "@/components/TodaysFocus";

// ── helpers ───────────────────────────────────────────────────────────────────

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

/** Map the /tracker/subjects payload to HeatmapGrid's SubjectReadiness shape. */
function mapToSubjectReadiness(raw: Record<string, unknown>[]): SubjectReadiness[] {
  return raw.map((s: Record<string, unknown>) => {
    const subtopics = (s.subtopics as Record<string, unknown>[] | undefined) ?? [];
    const total = subtopics.length;
    let strong = 0, partial = 0, weak = 0;
    for (const st of subtopics) {
      const score = typeof st.avg_score === "number" ? st.avg_score : 0;
      const tested = typeof st.questions_attempted === "number" ? (st.questions_attempted as number) > 0 : false;
      if (!tested) continue;
      if (score >= 70) strong++;
      else if (score >= 40) partial++;
      else weak++;
    }
    const readiness = typeof s.readiness === "number" ? (s.readiness as number) :
      typeof s.avg_score === "number" ? (s.avg_score as number) / 100 : 0;

    return {
      subject_id: String(s.subject_id ?? s.id ?? ""),
      subject_name: String(s.subject_name ?? s.name ?? ""),
      readiness,
      subtopics_total: total,
      subtopics_tested: strong + partial + weak,
      subtopics_weak: weak,
      subtopics_partial: partial,
      subtopics_strong: strong,
    };
  });
}

/** Pick today's focus: weakest subject by readiness. */
function pickFocus(subjects: SubjectReadiness[]): SubjectReadiness | null {
  if (!subjects.length) return null;
  return subjects.reduce((min, s) => (s.readiness < min.readiness ? s : min), subjects[0]);
}

// ── skeleton placeholder ──────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-800 rounded-lg ${className ?? ""}`} />;
}

// ── component ─────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const router = useRouter();

  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [plan, setPlan] = useState<Record<string, unknown> | null>(null);
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [subjects, setSubjects] = useState<SubjectReadiness[]>([]);
  const [streak, setStreak] = useState(0);
  const [dueCount, setDueCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  /** Strip CSAT sessions — CSAT has its own separate flow at /csat */
  const filterPlan = (data: Record<string, unknown>): Record<string, unknown> => {
    if (Array.isArray(data?.sessions)) {
      return {
        ...data,
        sessions: (data.sessions as Record<string, unknown>[]).filter(
          (s) => s.subject_id !== "csat"
        ),
      };
    }
    return data;
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      const results = await Promise.allSettled([
        api.getProfile(),
        api.getPlan(),
        api.getConfig(),
        api.getSubjects(),
        getStreakInfo(),
        getDueCount(),
      ]);

      const [profR, planR, cfgR, subjR, streakR, dueR] = results;

      if (profR.status === "fulfilled") setProfile(profR.value as Record<string, unknown>);
      if (planR.status === "fulfilled") setPlan(filterPlan(planR.value as Record<string, unknown>));
      if (cfgR.status === "fulfilled") setConfig(cfgR.value as Record<string, unknown>);
      if (subjR.status === "fulfilled") {
        const raw = subjR.value;
        const arr: Record<string, unknown>[] = Array.isArray(raw)
          ? (raw as Record<string, unknown>[])
          : typeof raw === "object" && raw !== null
          ? Object.values(raw as Record<string, Record<string, unknown>>)
          : [];
        setSubjects(mapToSubjectReadiness(arr));
      }
      if (streakR.status === "fulfilled") {
        setStreak((streakR.value as { current_streak: number }).current_streak);
      }
      if (dueR.status === "fulfilled") setDueCount(dueR.value as number);

      // Only show error for critical failures; streak/due degrade gracefully to 0
      if (profR.status === "rejected" || planR.status === "rejected") {
        setLoadError(
          "Some dashboard data failed to load — is the backend running?"
        );
      }

      setLoading(false);
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSync = async () => {
    setSyncing(true);
    setLoadError(null);
    try {
      await api.syncAnalysis();
      const [profR, planR, cfgR, subjR] = await Promise.allSettled([
        api.getProfile(),
        api.getPlan(),
        api.getConfig(),
        api.getSubjects(),
      ]);
      if (profR.status === "fulfilled") setProfile(profR.value as Record<string, unknown>);
      if (planR.status === "fulfilled") setPlan(filterPlan(planR.value as Record<string, unknown>));
      if (cfgR.status === "fulfilled") setConfig(cfgR.value as Record<string, unknown>);
      if (subjR.status === "fulfilled") {
        const raw = subjR.value;
        const arr: Record<string, unknown>[] = Array.isArray(raw)
          ? (raw as Record<string, unknown>[])
          : typeof raw === "object" && raw !== null
          ? Object.values(raw as Record<string, Record<string, unknown>>)
          : [];
        setSubjects(mapToSubjectReadiness(arr));
      }
    } catch (e) {
      setLoadError(String(e));
    } finally {
      setSyncing(false);
    }
  };

  // Derive today's focus from subject readiness
  const focusSubject = pickFocus(subjects);
  const focusPlanSession = Array.isArray(plan?.sessions)
    ? (plan!.sessions as Record<string, unknown>[])[0]
    : null;

  // Streak at risk: after 6PM and streak is active but no session today
  const isAfter6PM = new Date().getHours() >= 18;
  const streakAtRisk = isAfter6PM && streak > 0;

  return (
    <div className="space-y-6">
      {loadError && (
        <div className="rounded-lg border border-red-700 bg-red-900/20 px-4 py-3 text-sm text-red-300 flex items-center gap-2">
          <span className="text-red-500">⚠</span> {loadError}
        </div>
      )}

      {/* ── Top bar: greeting + streak + due ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {greeting()}
            {profile && typeof (profile as Record<string, unknown>).username === "string"
              ? `, ${(profile as Record<string, unknown>).username}`
              : ", there"}
            .
          </h1>
          {config && (
            <p className="text-gray-400 text-sm mt-0.5">
              {typeof config.total_days === "number"
                ? `${config.total_days}-day sprint`
                : "Prep sprint active"}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {loading ? (
            <>
              <Skeleton className="w-16 h-7" />
              <Skeleton className="w-16 h-7" />
            </>
          ) : (
            <>
              <StreakBadge streak={streak} atRisk={streakAtRisk} />
              {dueCount > 0 && <DueBadge count={dueCount} />}
            </>
          )}
        </div>
      </div>

      {/* ── No config prompt ── */}
      {!loading && !config && (
        <div className="bg-amber-950 border border-amber-800 rounded-xl p-5 flex items-center justify-between">
          <div>
            <p className="text-amber-300 font-medium">Set up your prep plan first</p>
            <p className="text-amber-500 text-sm mt-0.5">
              Choose your timeline and daily hours to personalise everything.
            </p>
          </div>
          <a
            href="/setup"
            className="bg-amber-600 hover:bg-amber-500 text-white px-4 py-2 rounded-lg text-sm font-medium shrink-0 ml-4"
          >
            Set Up →
          </a>
        </div>
      )}

      {/* ── Today's Focus ── */}
      {loading ? (
        <Skeleton className="h-24 w-full" />
      ) : focusSubject ? (
        <TodaysFocus
          subtopic_name={
            focusPlanSession
              ? String(focusPlanSession.subtopic_id ?? "").replace(/_/g, " ")
              : `Weakest: ${focusSubject.subject_name}`
          }
          subject_name={focusSubject.subject_name}
          estimated_questions={
            typeof focusPlanSession?.num_questions === "number"
              ? (focusPlanSession.num_questions as number)
              : 10
          }
          estimated_minutes={
            typeof focusPlanSession?.estimated_minutes === "number"
              ? (focusPlanSession.estimated_minutes as number)
              : 15
          }
          onStart={() => router.push("/session")}
        />
      ) : null}

      {/* ── Heatmap Grid ── */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Your Readiness
        </h2>
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : subjects.length > 0 ? (
          <HeatmapGrid subjects={subjects} />
        ) : (
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-6 text-center text-gray-400 text-sm">
            No readiness data yet — complete a session to see your heatmap.
          </div>
        )}
      </div>

      {/* ── Quick links row ── */}
      <div className="grid grid-cols-3 gap-3">
        <Link
          href="/pyq"
          className="rounded-xl border border-gray-800 bg-gray-900 hover:border-gray-600 p-4 text-center transition-colors"
        >
          <div className="text-xl mb-1">📚</div>
          <div className="text-sm font-medium text-gray-200">PYQ Browser</div>
        </Link>
        <Link
          href="/tracker"
          className="rounded-xl border border-gray-800 bg-gray-900 hover:border-gray-600 p-4 text-center transition-colors"
        >
          <div className="text-xl mb-1">📊</div>
          <div className="text-sm font-medium text-gray-200">Full Progress</div>
        </Link>
        <Link
          href="/leaderboard"
          className="rounded-xl border border-gray-800 bg-gray-900 hover:border-gray-600 p-4 text-center transition-colors"
        >
          <div className="text-xl mb-1">🏆</div>
          <div className="text-sm font-medium text-gray-200">Leaderboard</div>
        </Link>
      </div>

      {/* ── Last analysis note ── */}
      {profile &&
        typeof (profile as Record<string, unknown>).last_analysis === "string" && (
          <div className="bg-gray-900 border border-amber-900 rounded-xl p-4">
            <p className="text-amber-300 text-sm font-medium mb-1">Last Analysis</p>
            <p className="text-gray-300 text-sm">
              {String((profile as Record<string, unknown>).last_analysis)}
            </p>
          </div>
        )}

      {/* ── Sync button ── */}
      <div className="flex gap-4">
        <button
          onClick={handleSync}
          disabled={syncing}
          className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium px-6 py-3 rounded-lg transition-colors"
        >
          {syncing ? "Syncing..." : "Sync & Plan Tomorrow"}
        </button>
        <a
          href="/analysis"
          className="border border-gray-700 text-gray-300 hover:text-white px-6 py-3 rounded-lg transition-colors"
        >
          View Full Analysis
        </a>
      </div>
    </div>
  );
}
