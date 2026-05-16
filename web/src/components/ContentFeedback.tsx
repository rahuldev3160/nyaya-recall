"use client";
import { useState } from "react";
import { api } from "@/lib/api";

type Verdict = "correct" | "missing" | "omit" | "wrong";
type ContentType = "question" | "explanation" | "notes_section";

interface ContentFeedbackProps {
  sessionId: string;
  contentType: ContentType;
  questionHash?: string | null;
  subtopicId: string;
  subjectId: string;
  notesSection?: string | null;
}

const VERDICT_BUTTONS: { verdict: Verdict; label: string }[] = [
  { verdict: "correct", label: "Looks good" },
  { verdict: "missing", label: "Something's missing" },
  { verdict: "omit",    label: "Should be omitted" },
  { verdict: "wrong",   label: "Factually incorrect" },
];

/**
 * ContentFeedback — Phase 2 of ISSUE-017.
 *
 * Renders a compact 2×2 grid of verdict buttons below any generated content block.
 * After clicking a verdict the buttons dim, a "Saved ✓" indicator appears, and an
 * optional free-text note input is shown. The note is sent (along with the already-
 * saved verdict) when the parent navigates away — the parent is responsible for
 * calling `flushNote()` before advancing.  If the parent never calls it the note is
 * silently dropped (verdict is already persisted).
 *
 * Usage:
 *   <ContentFeedback
 *     sessionId={quiz.session_id}
 *     contentType="explanation"
 *     questionHash={qHash}
 *     subtopicId={subtopicId}
 *     subjectId={subjectId}
 *   />
 */
export default function ContentFeedback({
  sessionId,
  contentType,
  questionHash,
  subtopicId,
  subjectId,
  notesSection,
}: ContentFeedbackProps) {
  const [savedVerdict, setSavedVerdict] = useState<Verdict | null>(null);
  const [saving, setSaving] = useState(false);
  const [noteText, setNoteText] = useState("");
  // Track whether we've already persisted the follow-up note text
  const [noteSaved, setNoteSaved] = useState(false);

  const handleVerdict = async (verdict: Verdict) => {
    if (savedVerdict || saving) return;
    setSaving(true);
    try {
      await api.postContentFeedback({
        session_id: sessionId,
        content_type: contentType,
        question_hash: questionHash ?? null,
        subtopic_id: subtopicId,
        subject_id: subjectId,
        notes_section: notesSection ?? null,
        verdict,
        note_text: "",
      });
      setSavedVerdict(verdict);
    } catch {
      /* silently fail — feedback is non-blocking */
    } finally {
      setSaving(false);
    }
  };

  const handleNoteBlur = async () => {
    if (!savedVerdict || !noteText.trim() || noteSaved) return;
    try {
      await api.postContentFeedback({
        session_id: sessionId,
        content_type: contentType,
        question_hash: questionHash ?? null,
        subtopic_id: subtopicId,
        subject_id: subjectId,
        notes_section: notesSection ?? null,
        verdict: savedVerdict,
        note_text: noteText.trim(),
      });
      setNoteSaved(true);
    } catch {
      /* silently fail */
    }
  };

  return (
    <div className="mt-3 pt-3 border-t border-gray-800 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-gray-500 shrink-0">Rate this:</span>
        {savedVerdict ? (
          <span className="text-xs text-green-400 font-medium">Saved ✓</span>
        ) : null}
      </div>

      {/* 2×2 button grid */}
      <div className="grid grid-cols-2 gap-2">
        {VERDICT_BUTTONS.map(({ verdict, label }) => (
          <button
            key={verdict}
            type="button"
            onClick={() => handleVerdict(verdict)}
            disabled={!!savedVerdict || saving}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors text-left ${
              savedVerdict === verdict
                ? "border-green-600 bg-green-900/30 text-green-300"
                : savedVerdict
                ? "border-gray-800 bg-gray-900/40 text-gray-600 cursor-not-allowed"
                : saving
                ? "border-gray-700 text-gray-600 cursor-not-allowed"
                : "border-gray-700 hover:border-gray-500 text-gray-400 hover:text-gray-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Optional note — shown after a verdict is saved */}
      {savedVerdict && (
        <input
          type="text"
          value={noteText}
          onChange={(e) => {
            setNoteText(e.target.value);
            setNoteSaved(false);
          }}
          onBlur={handleNoteBlur}
          maxLength={2000}
          placeholder="Add a note (optional) — saves on blur"
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-gray-300 placeholder:text-gray-600 focus:outline-none focus:border-gray-500"
        />
      )}
    </div>
  );
}
