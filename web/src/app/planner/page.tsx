"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

interface SyllabusSubtopic {
  id: string;
  name: string;
}

interface SyllabusTopic {
  id: string;
  name: string;
  subtopics: SyllabusSubtopic[];
}

interface SyllabusSubject {
  id: string;
  name: string;
  topics: SyllabusTopic[];
}

interface PlanSession {
  order?: number;
  subject_id: string;
  topic_id?: string;
  subtopic_id: string;
  subtopic_ids?: string[];
  format: string;
  estimated_minutes?: number;
  num_questions: number;
  difficulty?: string;
  rationale?: string;
}

// ── Subtopic multi-picker ──────────────────────────────────────────────────

interface SubtopicPickerProps {
  subjectId: string;
  selected: string[];
  onChange: (ids: string[]) => void;
  syllabusTree: SyllabusSubject[];
}

function SubtopicPicker({ subjectId, selected, onChange, syllabusTree }: SubtopicPickerProps) {
  const subject = syllabusTree.find((s) => s.id === subjectId);
  if (!subject) {
    return (
      <p className="text-xs text-gray-500">
        Select a subject first to pick subtopics.
      </p>
    );
  }

  const toggle = (id: string) => {
    if (selected.includes(id)) {
      onChange(selected.filter((s) => s !== id));
    } else if (selected.length < 4) {
      onChange([...selected, id]);
    }
  };

  return (
    <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
      {subject.topics.map((topic) => (
        <div key={topic.id}>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            {topic.name}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {topic.subtopics.map((st) => {
              const isSelected = selected.includes(st.id);
              const isDisabled = !isSelected && selected.length >= 4;
              return (
                <button
                  key={st.id}
                  type="button"
                  disabled={isDisabled}
                  onClick={() => toggle(st.id)}
                  className={`text-xs px-2 py-1 rounded border transition-colors ${
                    isSelected
                      ? "bg-amber-600 border-amber-500 text-white"
                      : isDisabled
                      ? "bg-gray-800 border-gray-700 text-gray-600 cursor-not-allowed"
                      : "bg-gray-800 border-gray-600 text-gray-300 hover:border-amber-500 hover:text-white"
                  }`}
                >
                  {st.name}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Session editor modal ───────────────────────────────────────────────────

interface EditorProps {
  session: PlanSession;
  sessionIndex: number;
  syllabusTree: SyllabusSubject[];
  onSave: (index: number, updated: PlanSession) => void;
  onClose: () => void;
}

function SessionEditorModal({ session, sessionIndex, syllabusTree, onSave, onClose }: EditorProps) {
  const [subjectId, setSubjectId] = useState(session.subject_id);
  const [subtopicIds, setSubtopicIds] = useState<string[]>(
    session.subtopic_ids && session.subtopic_ids.length > 0
      ? session.subtopic_ids
      : session.subtopic_id
      ? [session.subtopic_id]
      : []
  );
  const [format, setFormat] = useState(session.format || "quiz_only");
  const [numQ, setNumQ] = useState(session.num_questions || 15);
  const [minutes, setMinutes] = useState(session.estimated_minutes || 45);
  const [difficulty, setDifficulty] = useState(session.difficulty || "medium");

  // When subject changes reset subtopic selection
  const handleSubjectChange = (newSubject: string) => {
    setSubjectId(newSubject);
    setSubtopicIds([]);
  };

  // Derive primary subtopic (first selected, used for subtopic_id backward compat)
  const primarySubtopicId = subtopicIds[0] ?? "";

  // Resolve subtopic name for display
  const getSubtopicName = (id: string): string => {
    for (const subj of syllabusTree) {
      for (const topic of subj.topics) {
        const st = topic.subtopics.find((s) => s.id === id);
        if (st) return st.name;
      }
    }
    return id.replace(/_/g, " ");
  };

  const handleSave = () => {
    const updated: PlanSession = {
      ...session,
      subject_id: subjectId,
      subtopic_id: primarySubtopicId,
      subtopic_ids: subtopicIds.length > 1 ? subtopicIds : undefined,
      format,
      num_questions: numQ,
      estimated_minutes: minutes,
      difficulty,
    };
    onSave(sessionIndex, updated);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h3 className="text-lg font-semibold text-white">Edit Session {sessionIndex + 1}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">
            ×
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          {/* Subject */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Subject</label>
            <select
              value={subjectId}
              onChange={(e) => handleSubjectChange(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
            >
              {syllabusTree.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Subtopic multi-picker */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs text-gray-400 uppercase tracking-wide">
                Subtopics (select 1–4)
              </label>
              {subtopicIds.length > 0 && (
                <span className="text-xs text-amber-400">{subtopicIds.length}/4 selected</span>
              )}
            </div>

            {/* Selected tag list */}
            {subtopicIds.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {subtopicIds.map((id) => (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 bg-amber-900/40 border border-amber-700/50 text-amber-300 text-xs px-2 py-0.5 rounded-full"
                  >
                    {getSubtopicName(id)}
                    <button
                      type="button"
                      onClick={() => setSubtopicIds(subtopicIds.filter((s) => s !== id))}
                      className="hover:text-white leading-none"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}

            <SubtopicPicker
              subjectId={subjectId}
              selected={subtopicIds}
              onChange={setSubtopicIds}
              syllabusTree={syllabusTree}
            />
          </div>

          {/* Format + difficulty row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              >
                <option value="quiz_only">Quiz only</option>
                <option value="notes_then_quiz">Notes then quiz</option>
                <option value="adaptive">Adaptive</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Difficulty</label>
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              >
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
                <option value="mixed">Mixed</option>
              </select>
            </div>
          </div>

          {/* Questions + minutes row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Questions</label>
              <input
                type="number"
                min={5}
                max={40}
                value={numQ}
                onChange={(e) => setNumQ(+e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Minutes</label>
              <input
                type="number"
                min={15}
                max={120}
                value={minutes}
                onChange={(e) => setMinutes(+e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              />
            </div>
          </div>

          {/* Multi-subtopic info badge */}
          {subtopicIds.length > 1 && (
            <div className="bg-blue-950/40 border border-blue-800/50 rounded-lg px-3 py-2 text-blue-300 text-xs">
              Merged session — questions will be allocated proportionally by PYQ weight across
              the {subtopicIds.length} selected subtopics. Notes will include a Cross-Subtopic
              Linkages section.
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={subtopicIds.length === 0}
            className="px-5 py-2 text-sm bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white rounded-lg font-medium transition-colors"
          >
            Save changes
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Session card display ───────────────────────────────────────────────────

interface SessionCardProps {
  session: PlanSession;
  index: number;
  syllabusTree: SyllabusSubject[];
  onEdit: (index: number) => void;
}

function SessionCard({ session, index, syllabusTree, onEdit }: SessionCardProps) {
  const isMerged = session.subtopic_ids && session.subtopic_ids.length > 1;

  const getSubtopicName = (id: string): string => {
    for (const subj of syllabusTree) {
      for (const topic of subj.topics) {
        const st = topic.subtopics.find((s) => s.id === id);
        if (st) return st.name;
      }
    }
    return id.replace(/_/g, " ");
  };

  return (
    <div className="flex items-start gap-4 p-4 bg-gray-800 rounded-lg group">
      <span className="text-gray-500 text-sm mt-0.5 w-5 shrink-0">{index + 1}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className="text-white font-medium text-sm">
            {session.subject_id?.replace(/_/g, " ")}
          </span>
          <span className="text-gray-500 text-xs">→</span>
          {isMerged ? (
            <div className="flex flex-wrap gap-1">
              {session.subtopic_ids!.map((id) => (
                <span
                  key={id}
                  className="bg-amber-900/30 border border-amber-700/40 text-amber-300 text-xs px-1.5 py-0.5 rounded"
                >
                  {getSubtopicName(id)}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-gray-300 text-sm">
              {getSubtopicName(session.subtopic_id)}
            </span>
          )}
        </div>
        {session.rationale && (
          <p className="text-gray-500 text-xs truncate">{session.rationale}</p>
        )}
      </div>
      <div className="text-right shrink-0 flex flex-col items-end gap-1">
        <div className="text-sm text-gray-400">{session.estimated_minutes} min</div>
        <div
          className={`text-xs px-2 py-0.5 rounded ${
            session.format === "notes_then_quiz"
              ? "bg-blue-900 text-blue-300"
              : "bg-gray-700 text-gray-300"
          }`}
        >
          {session.format?.replace(/_/g, " ")}
        </div>
        <button
          onClick={() => onEdit(index)}
          className="text-xs text-gray-600 hover:text-amber-400 transition-colors opacity-0 group-hover:opacity-100 mt-0.5"
        >
          Edit
        </button>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function PlannerPage() {
  const [plan, setPlan] = useState<any>(null);
  const [hours, setHours] = useState(8);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [syllabusTree, setSyllabusTree] = useState<SyllabusSubject[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [localSessions, setLocalSessions] = useState<PlanSession[]>([]);
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    api.getPlan().then(setPlan).catch(() => {});
    api.getSyllabusTree().then(setSyllabusTree).catch(() => {});
  }, []);

  useEffect(() => {
    if (plan?.sessions) {
      setLocalSessions(plan.sessions);
      setIsDirty(false);
    }
  }, [plan]);

  const generatePlan = async () => {
    setLoading(true);
    try {
      const p = await api.generatePlan(hours);
      setPlan(p);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (index: number) => setEditingIndex(index);

  const handleSaveSession = useCallback(
    (index: number, updated: PlanSession) => {
      const next = localSessions.map((s, i) => (i === index ? updated : s));
      setLocalSessions(next);
      setIsDirty(true);
    },
    [localSessions]
  );

  const handleSavePlan = async () => {
    setSaving(true);
    try {
      await api.patchUserPlan(localSessions);
      setIsDirty(false);
    } catch (e) {
      // surface error to user minimally
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const editingSession =
    editingIndex !== null ? localSessions[editingIndex] : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Study Planner</h1>

      <div className="flex items-end gap-4">
        <div>
          <label className="block text-sm text-gray-400 mb-2">Available hours today</label>
          <input
            type="number"
            min={2}
            max={14}
            value={hours}
            onChange={(e) => setHours(+e.target.value)}
            className="w-28 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white"
          />
        </div>
        <button
          onClick={generatePlan}
          disabled={loading}
          className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-medium"
        >
          {loading ? "Generating..." : "Plan Today"}
        </button>
      </div>

      {localSessions.length > 0 && (
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-4">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-lg font-semibold">Day {plan?.day} Plan</h2>
              <p className="text-amber-300 text-sm mt-1">{plan?.daily_goal}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-gray-500 text-sm">{localSessions.length} sessions</span>
              {isDirty && (
                <button
                  onClick={handleSavePlan}
                  disabled={saving}
                  className="bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded-lg font-medium"
                >
                  {saving ? "Saving..." : "Save changes"}
                </button>
              )}
            </div>
          </div>

          <div className="space-y-3">
            {localSessions.map((s, i) => (
              <SessionCard
                key={i}
                session={s}
                index={i}
                syllabusTree={syllabusTree}
                onEdit={handleEdit}
              />
            ))}
          </div>

          {plan?.sync_reminder && (
            <div className="border-t border-gray-800 pt-4">
              <p className="text-sm text-gray-400">
                <span className="text-amber-400 font-medium">Evening reminder: </span>
                {plan.sync_reminder}
              </p>
            </div>
          )}
        </div>
      )}

      {editingSession && editingIndex !== null && (
        <SessionEditorModal
          session={editingSession}
          sessionIndex={editingIndex}
          syllabusTree={syllabusTree}
          onSave={handleSaveSession}
          onClose={() => setEditingIndex(null)}
        />
      )}
    </div>
  );
}
