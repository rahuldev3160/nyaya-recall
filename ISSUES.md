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

### ISSUE-026 — Diagnostic and session questions repeat; no adaptive difficulty or note feedback
**Noticed:** 2026-05-16
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(none)*

**What happened:**
During back-to-back diagnostic sessions on the same subject, many questions repeated verbatim. Wrong answers were re-asked in the same framing rather than revisited from a different angle. Questions also clustered to the same type (mostly statement-based), which doesn't reflect actual UPSC question variety.

**The problem:**
`generate_quiz()` was fully stateless — no awareness of question history, user notes, or wrong-concept signals. Questions were generated fresh each session with no deduplication or adaptive reuse of feedback.

**Current state of the code:**
`backend/routes/quiz.py` — quiz generation had no history queries. Prompt templates had no intelligence variables.

**What's needed to fix:**
- Dedup via `question_hash` exclusion from recent sessions
- Wrong-concept revisiting in new framing
- User notes injection (`session_user_notes` table)
- UPSC question-type variety mandate in prompts
- Spillover to adjacent subtopics when one subtopic's dimensions are exhausted
- Deep Dive mode for focused single-subtopic drilling (10Q, 6 mandatory dimensions)

**Resolution:** Resolved 2026-05-16. Implemented in `fix/issue-026-adaptive-quiz` (PR #15).
- `backend/routes/quiz.py` — new `_get_quiz_intelligence()` helper queries excluded hashes, wrong concepts, recent question texts, and user notes; new `_get_spillover_subtopics()` helper reads today's plan; `generate_quiz()` injects 5 new template vars into all prompts
- `prompts/diagnostic_quiz.txt`, `adaptive_session.txt`, `adaptive_quiz_only.txt` — updated with intelligence block and UPSC variety mandate (5 question types, min 3 per set)
- `prompts/deep_dive_quiz.txt` — NEW: 10Q single-subtopic prompt covering 6 mandatory dimensions
- `web/src/app/diagnostic/page.tsx` — default count 10→15; Deep Dive mode toggle with per-subject subtopic selector

---

### ISSUE-025 — session/today-status uses start_time; localStorage race overwrites API result
**Noticed:** 2026-05-16
**Reported by:** Claude (code review during planning)
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(none)*

**What happened:**
Noticed during root-cause analysis of session completion display bugs.

**The problem:**
Two bugs found in `get_plan_status()` + `session/page.tsx`:
1. `GET /plan/today-status` filtered completed sessions by `substr(qs.start_time, 1, 10) = date('now')` instead of `date(qs.end_time) = date('now')`. Sessions started yesterday but completed today would be missed; semantically, "completed today" should key off end_time.
2. In `session/page.tsx`, two `useEffect` hooks both call `setCompletedSessions`. The localStorage restore (synchronous) ran first; the API call (async) only overwrote if `completed_subtopics.length > 0`. If the API returned an empty list, stale localStorage data persisted in UI state. Also, localStorage was cast to `number[]` but stored as `string[]` subtopic IDs.

**Resolution:** Resolved 2026-05-16.
- `backend/routes/plan.py` — filter changed to `date(qs.end_time) = date('now')` (PR #13).
- `web/src/app/session/page.tsx` — API effect now always overwrites (no length guard), making it the authoritative source. localStorage restore now merges into prev state (not replaces) for instant initial UI, then API result wins. Fixed type cast from `number[]` → `string[]` (PR #14).

---

### ISSUE-024 — Session progress lost on server restart; completed sessions reset on page refresh
**Noticed:** 2026-05-15
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P0
**Linked feature:** *(none)*

**What happened:**
User killed the server mid-session (or server crashed). On restart, Today's Sessions showed all sessions as "Start" again, including ones already completed. Clicking Start regenerated a new quiz from scratch, discarding the in-progress work.

**The problem:**
Two bugs:
1. `completedSessions` is pure React state (`Set<number>`). Page refresh wipes it — all completed sessions re-appear as "Start" even though answers are in SQLite.
2. Active quiz state (`session_id`, `questions`, `currentQ`, `answers`, `revealed`) lives only in React memory. Server restart → frontend reload → `startSession()` generates a NEW session_id/questions. Old in-progress session is orphaned in DB with no `end_time`, never counted.

Note: individual answers ARE persisted to SQLite immediately on submit (via `record_answer()`). The data is not lost — only the UI state is lost.

**Current state of the code:**
`web/src/app/session/page.tsx` — all session state is transient React state. No localStorage or DB-backed restoration. `list_sessions` query filters `end_time IS NOT NULL`, so in-progress sessions are invisible to the frontend.

**What's needed to fix:**
localStorage for both stores (no backend change needed):
- `upsc_completed_{date}` → `number[]` of completed plan-session indices (by date so it auto-resets next day)
- `upsc_active_quiz` → full quiz snapshot; verified against `GET /sessions/{id}` on restore; discarded if session has `end_time`

**Resolution:** Resolved 2026-05-15. `web/src/app/session/page.tsx` — added `ACTIVE_QUIZ_KEY` constant; four new effects: restore completedSessions on mount, save completedSessions on change, restore active quiz when plan loads (verified against DB), persist quiz state on every answer/navigation. `finishSession` clears localStorage on clean finish.

---

### ISSUE-021 — the time taking while generating session/quiz (in diagnostic section) is irritating- need to plan an interactive way for the user to keep engaged with the model/app while the session is generated at the background
**Noticed:** 2026-05-15
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
*(fill in — what were you doing when you noticed this)*

**The problem:**
the time taking while generating session/quiz (in diagnostic section) is irritating- need to plan an interactive way for the user to keep engaged with the model/app while the session is generated at the background

**Current state of the code:**
*(Claude to investigate)*

**What's needed to fix:**
*(Claude to determine)*

**Resolution:** *(pending)*

---
- 1. the loading time for sessions is 30-40secs, need to minimise this or invent a way to interect with user while session/quiz is genersting in parallel/background.
-2. the parallel note feature (my notes) is running standalone. theu are on the same screen but the user can either take notes or read notes ( note tab automatically shrink back at the bottom instead it should remain open to have more seamless note taking).
3. structure, organise model cleanly so that it can be utilized for upsc mains preperation, indian economics services exam, RBI depr exams too. There is overlap with all these 3 exams 
4.

### ISSUE-024 — Re-generating plan mid-day re-schedules already-completed subtopics
**Noticed:** 2026-05-15
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(none)*

**What happened:**
User completed several quiz sessions today, then clicked "Plan Today" again from the Planner page to regenerate. The new plan included subtopics they had already done that same day — resulting in duplicate sessions for the same subtopics.

**The problem:**
`generate_plan()` reads from `subtopic_scores` (updated only by batch analysis / Sync). Sessions completed today but not yet synced are invisible to the plan generator, so those subtopics appear as untested and get re-scheduled.

**Current state of the code:**
`scripts/plan_generator.py` — `compute_subtopic_coverage()` only queries `subtopic_scores`. Today's `quiz_sessions` (with `synced=0` or completed after last sync) are not considered.

**What's needed to fix:**
Query `session_answers JOIN quiz_sessions` for today's completed sessions and merge those subtopics into the coverage data passed to Claude, so re-planning mid-day doesn't re-include subtopics already covered.

**Resolution:** Resolved 2026-05-15. Fixed in `fix/issue-024-session-status-persistence`.
- `scripts/plan_generator.py` — added `_get_todays_completed_subtopics()`: queries `session_answers JOIN quiz_sessions` for today's end_time-set sessions, computes real per-subtopic % scores, merges into `tested_map` before coverage is built. Plan generator now sees today's work even without a sync.

---

### ISSUE-023 — Sessions not marked complete after finishing
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(none)*

**What happened:**
After completing a session, the today's sessions tab still shows it looking identical to unstarted sessions.

**The problem:**
Two bugs. (1) `completedSessions` was `Set<number>` (index-based) — if the plan was regenerated, old indices mapped to wrong sessions in the new plan. (2) State reset on every page load, so completing sessions and refreshing the page lost all progress markers.

**Current state of the code:**
`web/src/app/session/page.tsx` — `completedSessions` was transient React state, keyed by array index. No DB-backed check on mount.

**What's needed to fix:**
Switch tracking to subtopic_id (stable key). Add a backend endpoint that checks which plan subtopics were covered in today's completed quiz sessions, and hydrate frontend state from it on mount.

**Resolution:** Resolved 2026-05-15. Fixed in `fix/issue-024-session-status-persistence`.
- `backend/routes/plan.py` — new `GET /plan/today-status` returns `completed_subtopics: string[]` by querying `session_answers JOIN quiz_sessions` for sessions completed today.
- `web/src/lib/api.ts` — added `getPlanStatus()`.
- `web/src/app/session/page.tsx` — `completedSessions` now `Set<string>` (subtopic_id). Hydrated from `today-status` on mount. `finishSession` adds subtopic_id. Survives page refresh and server restart. Also retains localStorage `upsc_active_quiz` for in-progress quiz resume (from PR #6).

---

### ISSUE-022 — Session notes missing core concept depth
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
Notes on G20/BRICS subtopic covered angles and linkages correctly but didn't explain the concepts themselves sufficiently (e.g. India as BRICS chair 2026 warranted deeper coverage).

**The problem:**
The notes generated for a session covers all the important dimensions for a subtopic correctly but the explanation around the core concept is missing. Notes should deliver a brief but comprehensive explanation of the concept alongside the angles/linkages.

**Current state of the code:**
`prompts/session_notes.txt` — Haiku prompt with 4 fixed sections (Core Concept / PYQ Angles / Current Affairs Linkages / Broader Linkages). Core Concept section may be too brief.

**What's needed to fix:**
Rewrite the Core Concept section instruction in `prompts/session_notes.txt` to require substantive explanation of confusing/complex facts, not just a one-liner identifier.

**Resolution:** Resolved 2026-05-14. prompts/session_notes.txt Core Concept section rewritten to require substantive 3-5 sentence explanation including concept definition, UPSC relevance, and common traps.

---

### ISSUE-021 — Click immediately reveals answer — no submit step
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User was attempting a quiz and a single click on an option immediately saved the response and showed the answer.

**The problem:**
While attempting the question a simple click saves the user response and shows the answer immediately; instead create an option at the bottom of options which let user submit the response himself.

**Current state of the code:**
`web/src/app/diagnostic/page.tsx` — `submitAnswer()` is called directly on option click. A `pendingAnswer` state and Submit button were partially added in a recent session but may not be wired fully.

**What's needed to fix:**
Confirm the Submit button flow is complete: option click sets `pendingAnswer` (highlighted), Submit button calls `submitAnswer(pendingAnswer)`, answer only revealed after Submit.

**Resolution:** Resolved 2026-05-14. Fixed in PR #2. Option click highlights blue (pendingAnswer state); Submit button calls submitAnswer. Both diagnostic/page.tsx and session/page.tsx.

---

### ISSUE-020 — "Medium" label on sessions is unclear
**Noticed:** 2026-05-13
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User noticed a yellow "Medium" label on session cards and couldn't tell what it referred to.

**The problem:**
The sessions shows a label "medium" in yellow text colour — this is unclear what it is. All labels on UI should be self-explanatory for any random user.

**Current state of the code:**
*(Claude to investigate — likely the difficulty field on study_plan sessions rendered as a raw string)*

**What's needed to fix:**
Either replace "medium" with "Medium difficulty" or add a tooltip. Investigate which component renders this label.

**Resolution:** Resolved 2026-05-14. Difficulty badge now shows "Easy/Medium/Hard difficulty" instead of raw lowercase string. Fixed in web/src/app/session/page.tsx.

---

### ISSUE-019 — Note-taking box should reset per question and autosave
**Noticed:** 2026-05-13
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User tried to take per-question notes during a session.

**The problem:**
The note taking box at the right bottom corner should appear as a completely new note with each question and if user takes any note it should autosave linked to that particular question.

**Current state of the code:**
`session_user_notes` table exists. Notes are linked at session level, not per-question. The `question_context_index` column exists in the schema but the UI may not use it correctly per question.

**What's needed to fix:**
Ensure note textarea clears on `currentQ` change; autosave links to current `question_context_index`; on question return, repopulate note for that question index.

**Resolution:** Resolved 2026-05-14.
- `backend/routes/sessions.py` — added `session_question_notes` table (created lazily, no ALTER TABLE). PUT endpoint now accepts `note_text` + `question_context_index` and saves per-question row; GET returns `per_question_notes` dict keyed by question index.
- `web/src/app/session/page.tsx` — added `perQuestionNotes: Record<number, string>` state. Per-question note textarea (amber border, "Note for Q{N}") in the notes drawer shows/clears per `currentQ`, autosaves with 700ms debounce linked to question index. Loaded from backend on session start. Session-level confusion/mnemonic/still_weak fields remain unchanged.

---

### ISSUE-018 — No end-of-session revision notes for incorrect attempts
**Noticed:** 2026-05-13
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User finished a session and wanted brief revision notes on concepts where they answered incorrectly.

**The problem:**
At the end of the session, give brief revision notes around the concepts which user attempted incorrectly, so the user can consume them right after the quiz session to lock in the concepts in memory.

**Current state of the code:**
`POST /sessions/{session_id}/revision-notes` already exists and the diagnostic page already calls it and renders the revision deck. This issue may already be partially shipped — verify if it's working end-to-end and only open if revision deck is missing from session page (adaptive sessions).

**What's needed to fix:**
Verify revision deck appears in both `diagnostic/page.tsx` and `session/page.tsx`. If missing from session page, add the same finish-flow logic.

**Resolution:** Resolved 2026-05-14.
- `web/src/app/session/page.tsx` — added `revisionNotes` and `revisionLoading` state. `finishSession()` now calls `api.getRevisionNotes(quiz.session_id)` after closing the session. The `finished` view renders the full revision deck (loading pulse, clean-sweep message, or wrong-answer cards with question text + chosen/correct labels + explanation) — identical pattern to `diagnostic/page.tsx`.

---

### ISSUE-017 — Note-taking as model feedback and training data
**Noticed:** 2026-05-13
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User realised the note-taking box could double as a feedback mechanism for improving prompts.

**The problem:**
The note-taking button can serve as a tool to train our model — user can give feedback on what was correct, what should have been included, what could have been omitted, and what is incorrect. This generates training data linked to each question/session. Notes need to be stored well-indexed and organised.

**Current state of the code:**
`session_user_notes` table stores free-text. `plan_generator.fetch_user_notes_signals()` reads `still_weak` flag. No structured feedback taxonomy or prompt refinement loop exists yet.

**What's needed to fix:**
Spec required before implementing. Write `plans/feedback_training.md`.

**Resolution:** *(pending)*

---

### ISSUE-016 — Session completion box missing score
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User finished a diagnostic session and saw the "complete" status box but no score.

**The problem:**
At the end of the session, it is correctly showing the status as complete but missing the data on how many questions the user did right. Add score information within the box which shows complete status.

**Current state of the code:**
`diagnostic/page.tsx` `finished` view already renders score (`{correct} / {attempted} correct`). This may be specific to the `session/page.tsx` (adaptive sessions) — investigate which page is missing the score.

**What's needed to fix:**
Check `session/page.tsx` finished state and confirm score summary is rendered there.

**Resolution:** Resolved 2026-05-14. Fixed in PR #2. session/page.tsx finished state now renders score % and correct/total count.

---

### ISSUE-015 — Evaluate integrating an AI chat tool for topic exploration
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Open
**Priority:** P2
**Linked feature:** *(to be linked)*

**What happened:**
User wanted to explore a topic deeper while in a session and asked about chat integration.

**The problem:**
Can we integrate other AI tools like ChatGPT as a chat tool inside the model so that user can ask/explore more about a topic? What will be the cost vs the existing deep-dive and explain-selection features?

**Current state of the code:**
Existing on-demand features: "Dive deeper →" (`expand_concept`), "Explain selected text" (`expand_notes_selection`). Both use Claude Haiku, user-triggered, per-click cost.

**What's needed to fix:**
Spec + cost analysis before any implementation. The existing Dive deeper / Explain selection features may already cover this need — evaluate first.

**Resolution:** *(pending)*

---

### ISSUE-014 — Time tracker for portal
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Open
**Priority:** P2
**Linked feature:** *(to be linked)*

**What happened:**
User wanted to track how much time they spend in different sections of the portal.

**The problem:**
Introduce a time tracker that tracks time the user spends on the portal. The details section deep-dives into time spent on each section (sessions, diagnostics, self-attestation quizzes, etc.).

**Current state of the code:**
`time_taken_sec` is tracked per question in `session_answers`. No portal-level time tracking exists.

**What's needed to fix:**
New feature — spec required before implementing. Write `plans/time_tracker.md`.

**Resolution:** *(pending)*

---

### ISSUE-012 — CSAT must be removed from readiness scoring and plan generation
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
CSAT diagnostic test generated by the model marked wrong answers and contradicted itself in explanations — LLMs are unreliable at maths calculations.

**The problem:**
Remove CSAT from the tracker, from readiness scoring, and from plan generation entirely. Keep CSAT section as a completely standalone system. Assess preparation level for GS Paper 1 only. Build the model for GS1 paper only for now.

**Current state of the code:**
`scripts/plan_generator.py` already excludes CSAT from subject list (added May 12). `scripts/batch_analyse.py` may still include CSAT in overall readiness. Dashboard tracker may show CSAT row. `data/study_plan.json` CSAT sessions already removed.

**What's needed to fix:**
1. Audit `batch_analyse.py` to confirm CSAT excluded from readiness %
2. Remove CSAT row from dashboard tracker UI
3. Confirm plan_generator.py exclusion is complete

**Resolution:** Resolved 2026-05-14. Fixed in PR #2. scripts/batch_analyse.py _build_syllabus_map() now excludes CSAT. Watch-out: tracker UI CSAT row may still display — verify separately.

---

### ISSUE-008 — Completed sessions not accessible for review
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User finished a session and wanted to go back to review a question or concept from the notes.

**The problem:**
Once a session is complete, there is no option to access it back as of now; this blocks users revisiting the session to revise a question or concept from the notes.

**Current state of the code:**
`GET /sessions/{session_id}` endpoint exists and returns session + answers. No frontend page or route to display past sessions.

**What's needed to fix:**
New page `web/src/app/sessions/[id]/page.tsx` that fetches and renders a completed session in read-only mode (notes + all questions with correct answers revealed).

**Resolution:** Resolved 2026-05-14. Fixed in PR #4 (fix/issue-008-session-review). New pages: web/src/app/sessions/page.tsx (history list) and web/src/app/sessions/[id]/page.tsx (read-only review).

---

### ISSUE-007 — No previous question navigation in quiz
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User wanted to go back to a previous question during a quiz (standard behaviour in online exams).

**The problem:**
There is no option to go back to previous question while attempting the quiz. This feature enables user to navigate independently within quiz (just like normal online exams).

**Current state of the code:**
`diagnostic/page.tsx` and `session/page.tsx` — forward-only navigation. `currentQ` state increments only.

**What's needed to fix:**
Add "← Previous" button that decrements `currentQ` when `currentQ > 0`. Answers/revealed state is already keyed by question index so past answers will still show correctly on return. Unanswered questions should remain answerable on revisit; revealed questions should show in read-only mode.

**Resolution:** Resolved 2026-05-14. Fixed in PR #2. ← Previous button added to both diagnostic/page.tsx and session/page.tsx; decrements currentQ when > 0.

---

## Resolved

---

### ISSUE-013 — Explanation enrichment: wrong options not explained
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User noticed per-question explanations only stated the correct concept without explaining why each wrong option was incorrect or misleading. Raised twice (once for revision deck, once for in-quiz explanations).

**The problem:**
Explanations should include: (1) brief explanation of why the correct option is right, and (2) brief explanation of why each wrong option is incorrect — facts, concepts, or distinctions relevant to each distractor.

**Current state of the code (at time of fix):**
`prompts/diagnostic_quiz.txt`, `adaptive_session.txt`, `adaptive_quiz_only.txt` all had weak/empty explanation specs ("2-3 sentences" or "...").

**What's needed to fix:**
Update explanation instruction in all three quiz generation prompts.

**Resolution:** Resolved 2026-05-14.
- `prompts/diagnostic_quiz.txt`, `prompts/adaptive_session.txt`, `prompts/adaptive_quiz_only.txt` — explanation spec updated: lead with the core fact for the correct option, then one sentence per wrong option explaining what is incorrect or misleading about it.

---

### ISSUE-011 — Statement-based questions not formatted in UPSC style
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User noticed statement-based questions had all statements crammed into a single line instead of each on its own line (standard UPSC format).

**The problem:**
Statement-based questions should follow UPSC format with each numbered statement starting on a new line (clean visual layout).

**Current state of the code (at time of fix):**
No instruction to use `\n` in question_text for statements. Question text rendered as `<p>` without `whitespace-pre-wrap`.

**Resolution:** Resolved 2026-05-14.
- `prompts/diagnostic_quiz.txt`, `prompts/adaptive_session.txt`, `prompts/adaptive_quiz_only.txt` — added rule: each numbered statement must be on its own line using `\n`.
- `web/src/app/diagnostic/page.tsx`, `web/src/app/session/page.tsx` — added `whitespace-pre-wrap` to question text paragraph so `\n` renders correctly.

---

### ISSUE-010 — Revision deck wastes space on obvious information
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User read the revision deck after a session and found the first 2-3 lines just restated which option was chosen and that it was wrong — information already visible in the UI.

**The problem:**
The revision deck explanation should skip the obvious preamble and cover more useful dimensions of the concept instead.

**Current state of the code (at time of fix):**
`prompts/revision_notes.txt` instructed Haiku to "explain why the student's choice was wrong" — triggering preamble. UI already shows "You chose: (X)" and "Correct: (Y)" labels separately.

**Resolution:** Resolved 2026-05-14. `prompts/revision_notes.txt` rewritten: explicit instruction not to restate what student chose or what the correct answer is (UI shows this). Explanation leads straight with the core fact.

---

### ISSUE-009 — Revision deck produces contradictory or false explanations
**Noticed:** 2026-05-14
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
User reviewed the post-session revision deck and found explanations that contradicted the correct answer or mixed up information between options.

**The problem:**
The revision deck was generating explanations where the correct answer was sometimes misidentified and the explanation was factually wrong or internally contradictory.

**Current state of the code (at time of fix):**
`backend/routes/sessions.py` `get_revision_notes()` selected only `question_text, correct_answer, user_answer` — the option texts were never fetched or passed to Haiku. Haiku was explaining options it could not read. `max_tokens=300` was also insufficient for a full 4-option explanation.

**Resolution:** Resolved 2026-05-14.
- `sessions.py` — SELECT now includes `options` column; options JSON parsed and substituted into `{{option_a}}` / `{{option_b}}` / `{{option_c}}` / `{{option_d}}` in the prompt.
- `prompts/revision_notes.txt` — rewritten to include full option text context, explain correct option fact + one sentence per wrong option.
- `max_tokens` increased from 300 → 600.
- Cache key bumped to `:v2` so stale entries (generated without option texts) are not reused.

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

### ISSUE-002 — Planned session (notes then quiz) shows quiz only, no notes
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** Plan session formats (`plan_generation.txt` `notes_then_quiz`); adaptive quiz generation (`prompts/adaptive_session.txt`, `backend/routes/quiz.py`, `web/src/app/session/page.tsx`)

**What happened:**
A planned session whose format is **notes then quiz** was started from Today's Sessions. The UI should show the "Key Concepts — Read Before Quiz" block (`quiz.notes_summary`) before questions; only the quiz appeared.

**The problem:**
Notes block never appeared even when the plan said notes-then-quiz. User only got questions.

**Current state of the code:**
Fixed 2026-05-12.

**Resolution:** Resolved 2026-05-12. Root cause was `quiz.py` choosing the first `[` in the model output, which for `{"notes_summary":...,"questions":[...]}` sliced only the questions array so `notes_summary` was always `null`. Replaced with logic that prefers a top-level JSON object when `{` appears before `[`. Confirmed working by Rahul 2026-05-14.

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

**Current state of the code:**
Fixed. Backend was already complete.

**Resolution:** Fixed 2026-05-11. Added `skipQuestion()` in `web/src/app/diagnostic/page.tsx` — calls `api.submitAnswer` with `skipped: true, user_answer: null`, sets `revealed` so Next/Finish buttons appear. Skip button hidden once any option is selected. Skipped card shows correct answer. Finish screen shows skipped count separately; score % is calculated over attempted questions only (not skipped). Backend was already complete.

---

## Won't fix

---

### ISSUE-004 — Test issue log entry
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Won't fix
**Priority:** P1

**Resolution:** This was a test of the issue logging workflow. No code change needed.

---

## How to add a new issue

1. Copy the format block at the top
2. Increment the issue number (next: ISSUE-026)
3. Fill in all fields — especially "Current state of the code" so the next person
   doesn't have to re-investigate
4. Add it under **Open**
5. When resolved: move it to **Resolved**, fill in the Resolution field, commit
