"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import YearGrid, { YearEntry } from "@/components/YearGrid";
import SubjectCards, { SubjectEntry } from "@/components/SubjectCards";
import TopicAccordion, { TopicEntry } from "@/components/TopicAccordion";
import PYQQuizRunner, { PYQQuestion } from "@/components/PYQQuizRunner";

type View = "years" | "subjects" | "topics" | "quiz";

export default function PYQPage() {
  const [view, setView] = useState<View>("years");

  const [years, setYears] = useState<YearEntry[]>([]);
  const [subjects, setSubjects] = useState<SubjectEntry[]>([]);
  const [topics, setTopics] = useState<TopicEntry[]>([]);
  const [questions, setQuestions] = useState<PYQQuestion[]>([]);

  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [stats, setStats] = useState<{
    total_attempted: number;
    total_correct: number;
    accuracy_pct: number;
    years_touched: number[];
  } | null>(null);

  // Load years + stats on mount
  useEffect(() => {
    setLoading(true);
    Promise.all([api.getPYQYears(), api.getPYQStats()])
      .then(([yr, st]) => {
        setYears(yr);
        setStats(st);
      })
      .catch(() => setError("Failed to load PYQ data."))
      .finally(() => setLoading(false));
  }, []);

  const selectYear = useCallback(async (year: number) => {
    setSelectedYear(year);
    setSelectedSubject(null);
    setSelectedTopic(null);
    setLoading(true);
    setError(null);
    try {
      const data = await api.getPYQSubjects(year);
      setSubjects(data);
      setView("subjects");
    } catch {
      setError("Failed to load subjects.");
    } finally {
      setLoading(false);
    }
  }, []);

  const selectSubject = useCallback(
    async (subjectId: string) => {
      if (!selectedYear) return;
      setSelectedSubject(subjectId);
      setSelectedTopic(null);
      setLoading(true);
      setError(null);
      try {
        const data = await api.getPYQTopics(selectedYear, subjectId);
        setTopics(data);
        setView("topics");
      } catch {
        setError("Failed to load topics.");
      } finally {
        setLoading(false);
      }
    },
    [selectedYear]
  );

  const selectTopic = useCallback(
    async (topicId: string) => {
      if (!selectedYear || !selectedSubject) return;
      setSelectedTopic(topicId);
      setLoading(true);
      setError(null);
      try {
        const data = await api.getPYQQuestions(selectedYear, selectedSubject, topicId);
        setQuestions(data);
        setView("quiz");
      } catch {
        setError("Failed to load questions.");
      } finally {
        setLoading(false);
      }
    },
    [selectedYear, selectedSubject]
  );

  function handleDone() {
    // Refresh years (updated attempt counts), go back to topics
    setView("topics");
    api.getPYQYears().then(setYears).catch(() => null);
    api.getPYQStats().then(setStats).catch(() => null);
  }

  const subjectLabel = subjects.find((s) => s.subject_id === selectedSubject)?.label;
  const topicLabel = topics.find((t) => t.topic_id === selectedTopic)?.label;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">PYQ Browser</h1>
          <p className="text-sm text-gray-400 mt-0.5">Previous Year Questions — 2009 to 2025</p>
        </div>
        {stats && stats.total_attempted > 0 && (
          <div className="flex gap-4 text-right">
            <div>
              <div className="text-lg font-bold text-amber-400">{stats.total_attempted}</div>
              <div className="text-xs text-gray-500">attempted</div>
            </div>
            <div>
              <div className="text-lg font-bold text-green-400">{stats.accuracy_pct}%</div>
              <div className="text-xs text-gray-500">accuracy</div>
            </div>
          </div>
        )}
      </div>

      {/* Breadcrumb */}
      {view !== "years" && (
        <nav className="flex items-center gap-2 text-sm">
          <button
            onClick={() => setView("years")}
            className="text-amber-400 hover:text-amber-300"
          >
            Years
          </button>
          {selectedYear && (
            <>
              <span className="text-gray-600">/</span>
              <button
                onClick={() => setView("subjects")}
                className={view === "subjects" ? "text-white" : "text-amber-400 hover:text-amber-300"}
              >
                {selectedYear}
              </button>
            </>
          )}
          {selectedSubject && (
            <>
              <span className="text-gray-600">/</span>
              <button
                onClick={() => setView("topics")}
                className={view === "topics" ? "text-white" : "text-amber-400 hover:text-amber-300"}
              >
                {subjectLabel ?? selectedSubject}
              </button>
            </>
          )}
          {selectedTopic && view === "quiz" && (
            <>
              <span className="text-gray-600">/</span>
              <span className="text-white">{topicLabel ?? selectedTopic}</span>
            </>
          )}
        </nav>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-700 bg-red-900/20 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Loading spinner */}
      {loading && (
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Loading…
        </div>
      )}

      {/* Views */}
      {!loading && view === "years" && (
        <YearGrid years={years} selected={selectedYear} onSelect={selectYear} />
      )}

      {!loading && view === "subjects" && (
        <SubjectCards subjects={subjects} selected={selectedSubject} onSelect={selectSubject} />
      )}

      {!loading && view === "topics" && (
        <TopicAccordion topics={topics} selected={selectedTopic} onSelect={selectTopic} />
      )}

      {!loading && view === "quiz" && questions.length > 0 && selectedYear && (
        <PYQQuizRunner questions={questions} year={selectedYear} onDone={handleDone} />
      )}

      {!loading && view === "quiz" && questions.length === 0 && (
        <div className="text-sm text-gray-500">No questions found for this selection.</div>
      )}
    </div>
  );
}
