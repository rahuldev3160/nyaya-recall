# ISSUES.md — Running Issue Log

> Log of bugs, UX gaps, and problems noticed during actual use.
> Different from FEATURES.md (which tracks pre-planned items) — issues here are
> discovered organically, often by Rahul during study sessions.
>
> Keeping this log prevents repeating the same problems and gives future contributors
> the full context of when an issue arose, what was tried, and how it was resolved.

---

## Format

```
### ISSUE-NNN — Short title
**Noticed:** YYYY-MM-DD  
**Reported by:** Rahul / Friend / Claude  
**Status:** Open | In progress | Resolved | Won't fix  
**Priority:** P0–P3  
**Linked feature:** FEATURES.md item or plan file if applicable  

**What happened:** (context — what the user was doing when they noticed it)  
**The problem:** (what's wrong or missing)  
**Current state of the code:** (what exists vs what's missing — saves investigation time)  
**What's needed to fix:** (specific work required)  
**Resolution:** (how it was fixed, date, commit — fill in when done)  
```

---

## Open

---

### ISSUE-017 — Note-taking as model feedback / training data
**Noticed:** 2026-05-13
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** `plans/feedback_training.md`

**What happened:**
Rahul used the note-taking box during a session and realised it could capture structured feedback on LLM output quality.

**The problem:**
The note-taking feature could let the user flag what was correct, what should have been included, and what was wrong in generated content (questions, explanations, session notes). This feedback, stored per-question and indexed, could drive prompt improvement. Currently notes are per-session and unstructured.

**Current state of the code:**
`session_user_notes` table exists (id, session_id, subject_id, subtopic_id, confusion, mnemonic, still_weak). Notes panel in `fix/explanation-quality` session/page.tsx is per-session only. `plans/feedback_training.md` has a 3-phase spec with 3 open questions for Rahul.

**What's needed to fix:**
Awaiting Rahul's answers to 3 questions in `plans/feedback_training.md` Section 10 before Phase 1 build starts.

**Resolution:** *(pending)*

---

### ISSUE-019 — Note-taking box should reset per question and autosave
**Noticed:** 2026-05-13
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** `plans/feedback_training.md`

**What happened:**
Rahul noticed the note-taking box retains its content as questions advance, and notes are saved for the whole session rather than per question.

**The problem:**
Each question should get a fresh blank note. If the user types anything, it should autosave linked to that specific question (question_hash). This makes each note a granular data point rather than one big session note.

**Current state of the code:**
`fix/explanation-quality` session/page.tsx: notes panel saves to `session_user_notes` via `PUT /sessions/{id}/user-notes` keyed by session_id only. No per-question storage exists. `question_notes` table does not exist yet.

**What's needed to fix:**
1. New DB table `question_notes` (question_hash, session_id, note_text, created_at)
2. Frontend: clear note text on `currentQ` change, debounce-save to a new endpoint `PUT /sessions/{session_id}/question-note/{question_hash}`
3. Backend: new endpoint for per-question notes

**Resolution:** *(pending)*

---

### ISSUE-022 — Session notes missing deep explanation of core concepts
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
Rahul reviewed session notes for the G20/BRICS subtopic and found that while the structure (PYQ angles, current affairs, broader linkages) was correct, the actual explanation of confusing concepts was thin. BRICS with India as 2026 chair should have been explained in depth given its current affairs weight.

**The problem:**
`prompts/session_notes.txt` Core Concept section doesn't go deep enough on concepts with high current-affairs significance. It lists facts rather than explaining them at UPSC exam depth.

**Current state of the code:**
`prompts/session_notes.txt` in `fix/explanation-quality` branch already has an expanded Core Concept section (definition, why it matters, key facts, common misconceptions, current affairs depth with expand instruction for high-significance events). Fix may already be in `fix/explanation-quality` branch.

**What's needed to fix:**
Verify the `fix/explanation-quality` prompt update covers this. If live sessions still show thin core concept sections, add a specific instruction: "for events with current-year significance (BRICS chair, elections, policies), include 2–3 sentences of substantive context."

**Resolution:** *(pending — verify after fix/explanation-quality merges)*

---

### ISSUE-014 — Time tracker for portal usage
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Open
**Priority:** P2
**Linked feature:** *(to be linked)*

**What happened:**
Rahul wants to track how much time he spends in each section of the portal.

**The problem:**
No time-tracking exists. User wants: total time on portal, breakdown by section (sessions, diagnostics, self-attestation), per-day trend.

**Current state of the code:**
`session_answers.time_taken_sec` is populated per question (added May 12). `quiz_sessions` has `start_time` and `end_time`. Session-level time can be derived; page-level dwell time would need frontend instrumentation.

**What's needed to fix:**
1. Backend: aggregate endpoint summing `(end_time - start_time)` from `quiz_sessions` grouped by date + section type
2. Frontend: a tracker page card showing daily usage breakdown
3. Optional: log page visits with timestamps in a new `page_views` table

**Resolution:** *(pending)*

---

### ISSUE-015 — AI chat integration evaluation
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Open
**Priority:** P2
**Linked feature:** *(to be linked)*

**What happened:**
Rahul asks whether integrating another AI (e.g. ChatGPT) as an in-portal chat would be useful and what it would cost vs the existing Dive Deeper feature.

**The problem:**
No in-portal chat exists. The "Dive Deeper" button already calls Claude Haiku on demand. A full chat interface would add significant per-message API cost for a 10-day prep window.

**Current state of the code:**
`POST /sessions/expand-concept` (Haiku) and `POST /sessions/expand-notes-selection` are the two on-demand AI endpoints. There is no chat history or multi-turn conversation.

**What's needed to fix:**
Cost/benefit analysis first: 10-day horizon means ~$0.05–0.10/day of extra cost for heavy chat use on Haiku. Likely not worth building given exam is 6 days away. Defer to post-exam.

**Resolution:** Won't build before exam (May 20). Revisit post-exam if continuing project.

---

### ISSUE-008 — No way to revisit a completed session
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
Rahul completed a session and wanted to go back to review his wrong answers and the explanations.

**The problem:**
Once a session finishes and the user navigates away, there is no history page to re-open it. The data exists in the DB but is inaccessible from the UI.

**Current state of the code:**
`GET /sessions/{session_id}` in `backend/routes/sessions.py` already returns session + full answer list. No list endpoint or history page exists. `quiz_sessions` table has: id, subject_id, score, start_time, end_time, total_questions, answered, skipped.

**What's needed to fix:**
1. Backend: `GET /sessions/` — list recent sessions (last 30), ordered by start_time DESC, return id, subject_id, score, start_time, total_questions, answered, skipped
2. Frontend `api.ts`: add `getSessionHistory()` and `getSession(id)`
3. New page `web/src/app/sessions/[id]/page.tsx` — show Q&A review with correct/wrong highlighting and explanations
4. Link to history: add "Review Sessions" link on the dashboard or sessions list page

**Resolution:** *(pending)*

---

### ISSUE-004 — test issue (terminal logging test)
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Won't fix
**Priority:** P3

**What happened:** Test of the issue logging via terminal.

**The problem:** N/A — was a test.

**Resolution:** Won't fix — test entry.

---

### ISSUE-002 — Planned session (notes then quiz) shows quiz only, no notes
**Noticed:** 2026-05-12  
**Reported by:** Rahul  
**Status:** In progress — parser fix landed 2026-05-12; Rahul to confirm after live session  
**Priority:** P1  
**Linked feature:** Plan session formats (`plan_generation.txt` `notes_then_quiz`); adaptive quiz generation (`prompts/adaptive_session.txt`, `backend/routes/quiz.py`, `web/src/app/session/page.tsx`)

**What happened:**  
A planned session whose format is **notes then quiz** was started from Today's Sessions. The UI should show the "Key Concepts — Read Before Quiz" block (`quiz.notes_summary`) before questions; only the quiz appeared.

**The problem:**  
Notes block never appears even when the plan says notes-then-quiz. User only gets questions.

**Current state of the code:**  
- Frontend correctly sets `show_notes: session.format === "notes_then_quiz"` when calling `api.generateQuiz` (`web/src/app/session/page.tsx`).  
- Prompt template `adaptive_session.txt` asks for JSON with `notes_summary` + `questions` when the notes branch is active.  
- **Bug in `generate_quiz` JSON extraction:** `quiz.py` uses `start = raw.find("[") if "[" in raw else raw.find("{")`. For a normal object response `{"notes_summary":"...","questions":[...]}`, `"[" in raw` is true (the questions array), so the slice is **only the questions array**. Parser then treats the result as a `list`, so `notes_summary` is dropped (`notes = None`). Same symptom if the model returns a perfect object.  
- UI only renders notes when `quiz.notes_summary` is truthy (`session/page.tsx`).

**What's needed to fix:**  
1. **Parser:** Prefer extracting a top-level JSON **object** when `{` appears before the opening `[` of `questions` (or always try object bounds first for adaptive / `show_notes` responses).  
2. **Optional hardening:** If `show_notes` and `notes` is null after parse, retry or log server-side for debugging.  
3. After fix, re-test a `notes_then_quiz` planned session end-to-end.

**Resolution:** *(pending user verification)*  
2026-05-12: **Root cause** was `quiz.py` choosing the first `[` in the model output, which for `{"notes_summary":...,"questions":[...]}` slices only the questions array so `notes_summary` is always `null`. Replaced with logic that prefers a top-level JSON object when `{` appears before `[`. Move to **Resolved** after live session confirms notes appear; if not, re-open investigation.

---

## Resolved

---

### ISSUE-023 — Completed sessions not marked in Today's Sessions list
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1

**What happened:** After finishing a session, the Today's Sessions list still showed all sessions looking identical — no visual indicator for completed ones.

**The problem:** No completed state tracked in the UI; every session card looked the same even after finishing.

**Current state of the code:** Fixed in `fix/session-ux-improvements` PR #2.

**Resolution:** Resolved 2026-05-14. `completedSessions` Set<number> added to state in `session/page.tsx`. Finished sessions show green ✓ badge + "Completed" label. Card background changes to green-tinted.

---

### ISSUE-021 — Clicking an option immediately reveals answer (no confirmation step)
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1

**What happened:** User clicked an option by accident or wanted to confirm — the answer was already revealed.

**The problem:** Option click fired the API call immediately, no way to change mind before submitting.

**Resolution:** Resolved 2026-05-14 in `fix/session-ux-improvements` PR #2. Added `pendingAnswer` state: option click sets blue highlight only, "Submit Answer" button appears below options, actual API call fires only on submit.

---

### ISSUE-020 — "Medium" difficulty label is not self-explanatory
**Noticed:** 2026-05-13
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1

**What happened:** Session card showed "Medium" in yellow text — unclear whether it refers to session difficulty, user level, or content depth.

**Resolution:** Resolved 2026-05-14 in `fix/session-ux-improvements` PR #2. Label changed to "· medium difficulty" inline with the session metadata line (format · duration · difficulty).

---

### ISSUE-016 — Session finish screen missing score data
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1

**What happened:** Session complete screen showed "Saved!" but no score.

**Resolution:** Resolved 2026-05-14 in `fix/session-ux-improvements` PR #2. Finish screen now shows large % score + correct/total count.

---

### ISSUE-013 — Answer explanations don't explain why wrong options are wrong
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved (in fix/explanation-quality, pending merge)
**Priority:** P1

**What happened:** After submitting an answer, the explanation only described the correct option. No context on why the other 3 options were wrong.

**The problem:** User misses learning opportunity on wrong options — exactly the options they might pick in the real exam.

**Current state of the code:** Fixed in `fix/explanation-quality` branch commit `acac3e7`.

**Resolution:** Resolved in `fix/explanation-quality`. `prompts/diagnostic_quiz.txt` explanation field now instructs: "Lead with the specific fact for the correct option (1–2 sentences). Then add one short sentence per wrong option explaining what is incorrect or misleading." Revision notes prompt also updated. Pending merge.

---

### ISSUE-012 — CSAT sessions affecting GS1 readiness score
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1

**What happened:** CSAT diagnostic sessions (which use a separate scoring model) were being included in the overall GS1 readiness calculation, inflating or distorting the GS1 score.

**Resolution:** Resolved 2026-05-14 in `fix/session-ux-improvements` PR #2. `scripts/batch_analyse.py` `_build_syllabus_map()` now excludes CSAT subtopics from GS1 readiness calculation. CSAT remains fully standalone.

---

### ISSUE-011 — Statement-based questions run statements together on one line
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved (in fix/explanation-quality, pending merge)
**Priority:** P1

**What happened:** "Consider the following statements: 1. ... 2. ... 3. ..." appeared as one run-on line, making it hard to read — unlike the real UPSC paper where each statement starts on a new line.

**Resolution:** Resolved in `fix/explanation-quality` branch. `prompts/diagnostic_quiz.txt` now instructs: "Statement-based questions: each numbered statement MUST be on its own line using \n." Pending merge.

---

### ISSUE-010 — Revision deck preamble wastes the first 2–3 lines restating obvious info
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved (in fix/explanation-quality, pending merge)
**Priority:** P1

**What happened:** Post-session revision notes opened with "You chose (b), which is incorrect. The correct answer is (a)." — information the user already knows from the quiz result.

**Resolution:** Resolved in `fix/explanation-quality` branch. `prompts/revision_notes.txt` updated: "The student already knows which option they chose and which was correct — do NOT restate that. Lead straight with the fact."

---

### ISSUE-009 — Revision deck explanations contradict the correct answer
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved (in fix/explanation-quality, pending merge)
**Priority:** P1

**What happened:** The revision notes showed an explanation that mixed up or contradicted which option was actually correct — the LLM was hallucinating the wrong option as the right one in the revision text.

**The problem:** The revision_notes prompt did not have all 4 options as context, only the question and correct answer label. The model filled in the option text from training data — sometimes incorrectly.

**Current state of the code:** Fixed in `fix/explanation-quality` commit `acac3e7`.

**Resolution:** Resolved in `fix/explanation-quality`. `prompts/revision_notes.txt` now includes all four option texts (option_a through option_d) so the model cannot hallucinate option content. Pending merge.

---

### ISSUE-018 — No revision notes at end of quiz session for wrong answers
**Noticed:** 2026-05-13
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1

**What happened:** After finishing a diagnostic session, there was no summary of what the user got wrong and why — the learning opportunity was lost immediately after the session.

**Resolution:** Resolved 2026-05-13. New endpoint `POST /sessions/{session_id}/revision-notes` in `backend/routes/sessions.py`. New `prompts/revision_notes.txt` (Haiku). Results cached by SHA256 in `cache/explanations.json`. Finish screen in `diagnostic/page.tsx` fetches and displays "Concepts to Review" section.

---

### ISSUE-007 — No back-navigation within quiz
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1

**What happened:** User wanted to go back to a previous question to review it before finishing — no way to do it.

**Resolution:** Resolved 2026-05-14 in `fix/session-ux-improvements` PR #2. "← Previous" button added to both `session/page.tsx` and `diagnostic/page.tsx`, shown when `currentQ > 0`.

---

### ISSUE-006 — Session notes vague, unprocessed (ir/governance g20 subtopic)
**Noticed:** 2026-05-12  
**Reported by:** Rahul  
**Status:** Resolved  
**Priority:** P1  
**Linked feature:** *(same root cause as ISSUE-005)*

**What happened:**
Notes panel in ir/governance session showed raw vector excerpts, not structured revision content.

**The problem:**
Raw ChromaDB chunks pasted verbatim — no concept explanation, no PYQ angles, no current affairs linkage.

**Current state of the code:**
`build_notes_from_vector_chunks()` was explicitly no-LLM by design (to save tokens). Fixed — see ISSUE-005 resolution.

**Resolution:** Resolved 2026-05-12. Same fix as ISSUE-005 — Haiku now synthesises structured notes (Core Concept / PYQ Angles / Current Affairs Linkages / Broader Linkages) from vector chunks and caches by content hash. All today's sessions pre-warmed.

---

### ISSUE-005 — Session notes are raw vector excerpts, not synthesised revision notes
**Noticed:** 2026-05-12  
**Reported by:** Rahul  
**Status:** Resolved  
**Priority:** P1  
**Linked feature:** *(to be linked)*

**What happened:**
Notes panel in planned sessions showed unprocessed PDF/document excerpts from ChromaDB.

**The problem:**
`build_notes_from_vector_chunks()` in `backend/routes/quiz.py` deliberately skipped the LLM ("Markdown from stored vectors only (no LLM)") to save tokens. Result: raw, unsynthesised excerpts with no exam framing.

**Current state of the code:**
Fixed. Replaced with `synthesize_notes_cached()`.

**Resolution:** Resolved 2026-05-12.
- New `prompts/session_notes.txt`: Haiku prompt that synthesises 4-section notes (Core Concept, PYQ Angles, Current Affairs Linkages, Broader Linkages) from raw chunks.
- `synthesize_notes_cached()` in `quiz.py`: checks `cache/explanations.json` by SHA256(subtopic+chunks); calls Haiku on cache miss; returns on cache hit (0 API tokens for repeat sessions).
- Library source links (from ISSUE-003) preserved and appended after synthesised notes.
- `scripts/prewarm_notes_cache.py`: pre-warms cache for all today's `notes_then_quiz` sessions. All 12 sessions for May 12 pre-generated and cached.

---

### ISSUE-003 — Session notes: explore links, parallel notetaking, plan personalisation
**Noticed:** 2026-05-12  
**Reported by:** Rahul (approved scope same day)  
**Status:** Resolved  
**Priority:** P1  
**Linked feature:** `FEATURES.md` — Notes deep-links + selection explain; Parallel session notes + plan signals

**What happened:**  
User approved (1) actionable links inside vector-sourced notes + on-demand "explain selection", (2) parallel structured notetaking during read + quiz, (3) notes drawer **closed by default** once a session starts, (4) entries in FEATURES + ISSUES.

**The problem:**  
Notes lacked per-excerpt source links; no way to deep-dive a highlighted phrase from the notes card; no persisted parallel notes; planner did not see self-reported weak signals.

**Current state of the code (2026-05-12):**  
- `quiz.py` — `build_notes_from_vector_chunks`: after each excerpt, *Open full source:* → `/api/backend/library/file?rel=…` when resolvable under `UPSC_CONTENT_PATH`.  
- `POST /sessions/expand-notes-selection`, `prompts/expand_notes_selection.txt` (Haiku, user-triggered only).  
- `session_user_notes` in `scripts/db_init.py`; `server.py` lifespan creates table if missing.  
- `GET` / `PUT` `/sessions/{session_id}/user-notes` in `backend/routes/sessions.py`.  
- `web/src/app/session/page.tsx` — "Explain selected text" under Key Concepts; **My notes** FAB + slide-over; debounced save; `flushUserNotes` on Finish.  
- `plan_generator.fetch_user_notes_signals()` + `plan_generation.txt` `{{user_notes_signals}}` + rule to prioritise `still_weak` subtopics.

**Resolution:** Shipped 2026-05-12. **Stretch (post–20 May):** PDF page anchors in links, NLP on free-text notes, automatic merge into `prep_profile.json`.

---

### ISSUE-001 — No skip button in quiz UI
**Noticed:** 2026-05-11
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** `FEATURES.md` queue item to add; extends `plans/metacognition_capture.md`

**What happened:**
Rahul noted during study sessions that there is no way to skip a question intentionally.
In the real UPSC Prelims, skipping is a deliberate strategy — candidates skip when uncertain
to avoid negative marking (−0.66 per wrong answer). The current quiz forces a selection or
abandonment of the session, which doesn't reflect actual exam conditions.

**The problem:**
No Skip button exists in the diagnostic session UI. Users cannot intentionally skip a
question the way they would in the real exam.

**Resolution:** Fixed 2026-05-11. Added `skipQuestion()` in `web/src/app/diagnostic/page.tsx` — calls `api.submitAnswer` with `skipped: true, user_answer: null`, sets `revealed` so Next/Finish buttons appear. Skip button hidden once any option is selected. Skipped card shows correct answer. Finish screen shows skipped count separately; score % is calculated over attempted questions only (not skipped). Backend was already complete.

---

## Won't fix

### ISSUE-004 — Terminal issue logging test
**Status:** Won't fix — test entry, no actual bug.

### ISSUE-015 — AI chat integration (pre-exam)
**Status:** Won't fix before May 20. Cost/benefit doesn't justify building in exam window. Revisit post-exam.

---

## How to add a new issue

1. Copy the format block at the top
2. Increment the issue number (check the highest existing number above)
3. Fill in all fields — especially "Current state of the code" so the next person
   doesn't have to re-investigate
4. Add it under **Open**
5. When resolved: move it to **Resolved**, fill in the Resolution field, commit
