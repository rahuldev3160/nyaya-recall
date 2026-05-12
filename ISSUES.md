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

### ISSUE- — the notes generated for a session covers all the important dimensions for a subtopic correctly but the explaination around the core concept is missing (for eg: the note on g20, brics subtopic session correctly identified organisations, broader concepts about how are they structured in globalised world, geopolitical angles, pyq angles, current affairs but did not sufficiently explained the confusing concepts or facts, it also should have explained a bit more on BRICS (given the current affairs mention that india as BRICS chair for 2026 clubbed with its expanding nature makes it automatically a concept which user need to read comprehensively in brief and notes should deliver that
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
*(fill in — what were you doing when you noticed this)*

**The problem:**
the notes generated for a session covers all the important dimensions for a subtopic correctly but the explaination around the core concept is missing (for eg: the note on g20, brics subtopic session correctly identified organisations, broader concepts about how are they structured in globalised world, geopolitical angles, pyq angles, current affairs but did not sufficiently explained the confusing concepts or facts, it also should have explained a bit more on BRICS (given the current affairs mention that india as BRICS chair for 2026 clubbed with its expanding nature makes it automatically a concept which user need to read comprehensively in brief and notes should deliver that

**Current state of the code:**
*(Claude to investigate)*

**What's needed to fix:**
*(Claude to determine)*

**Resolution:** *(pending)*

---

### ISSUE- — after the session is complete, it does not show as completed in the today's session tab where all the scheduled sessions are, this does not allow the user to keep a track of what is complete and what is left, all the sessions looks exactly similar even after attempting some of them already
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
*(fill in — what were you doing when you noticed this)*

**The problem:**
after the session is complete, it does not show as completed in the today's session tab where all the scheduled sessions are, this does not allow the user to keep a track of what is complete and what is left, all the sessions looks exactly similar even after attempting some of them already

**Current state of the code:**
*(Claude to investigate)*

**What's needed to fix:**
*(Claude to determine)*

**Resolution:** *(pending)*

---

### ISSUE-008 — once a session is complete, there is no option to access it back as of now, this blocks users revisiting the session to revise a question or concept from the notes of the session
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
*(fill in — what were you doing when you noticed this)*

**The problem:**
once a session is complete, there is no option to access it back as of now, this blocks users revisiting the session to revise a question or concept from the notes of the session

**Current state of the code:**
*(Claude to investigate)*

**What's needed to fix:**
*(Claude to determine)*

**Resolution:** *(pending)*

---

### ISSUE-007 — there is no option to go back to previous question while attempting the quiz, this feature enables user to navigate independently within quiz (just like normal online exams, quizes happen)
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
*(fill in — what were you doing when you noticed this)*

**The problem:**
there is no option to go back to previous question while attempting the quiz, this feature enables user to navigate independently within quiz (just like normal online exams, quizes happen)

**Current state of the code:**
*(Claude to investigate)*

**What's needed to fix:**
*(Claude to determine)*

**Resolution:** *(pending)*

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

### ISSUE-004 — this is a test for issue log through terminal
**Noticed:** 2026-05-12
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
*(fill in — what were you doing when you noticed this)*

**The problem:**
this is a test for issue log through terminal

**Current state of the code:**
*(Claude to investigate)*

**What's needed to fix:**
*(Claude to determine)*

**Resolution:** *(pending)*

---

### ISSUE-002 — Planned session (notes then quiz) shows quiz only, no notes
**Noticed:** 2026-05-12  
**Reported by:** Rahul  
**Status:** In progress — parser fix landed 2026-05-12; Rahul to confirm after 2026-05-13 session  
**Priority:** P1  
**Linked feature:** Plan session formats (`plan_generation.txt` `notes_then_quiz`); adaptive quiz generation (`prompts/adaptive_session.txt`, `backend/routes/quiz.py`, `web/src/app/session/page.tsx`)

**What happened:**  
A planned session whose format is **notes then quiz** was started from Today’s Sessions. The UI should show the “Key Concepts — Read Before Quiz” block (`quiz.notes_summary`) before questions; only the quiz appeared.

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
2026-05-12: **Root cause** was `quiz.py` choosing the first `[` in the model output, which for `{"notes_summary":...,"questions":[...]}` slices only the questions array so `notes_summary` is always `null`. Replaced with logic that prefers a top-level JSON object when `{` appears before `[`. Move to **Resolved** after tomorrow’s session confirms notes appear; if not, re-open investigation (model omitting `notes_summary`, proxy stripping fields, etc.).

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
question the way they would in the real exam. This also means:
- No record of which questions the user chose not to attempt
- No data on skip patterns per subject/topic (which would signal uncertainty clusters)
- Exam strategy practice is unrealistic without the skip option

**Current state of the code:**
Backend is **100% complete** — no backend work needed:
- `session_answers.skipped` column exists in the DB schema
- `score_engine.record_answer()` already stores the `skipped` flag (`answer.get("skipped")`)
- `close_session()` already excludes skipped answers from score: `correct / max(total - skipped, 1)`
- `_store_session_summary()`, `_update_subtopic_scores()`, `_update_subtopic_difficulties()`
  all already handle `skipped=True` rows correctly

Frontend (`web/src/app/diagnostic/page.tsx`): **zero skip functionality** — no button, no
state, nothing. Grep for "skip" returns no results in the file.

**What's needed to fix:**

*Part A — Skip button (est. ~1–2 hrs frontend only):*
1. Add a `[Skip →]` button below the answer options (before the user has selected anything)
2. On click: call `api.submitAnswer({ ..., skipped: true, user_answer: null, is_correct: false })`
3. Button should disappear once an option is selected or answer is revealed
4. Advance to next question the same way a normal answer does

*Part B — Skip metacognition (est. ~1 hr, depends on `plans/metacognition_capture.md` Phase 2):*
After user clicks Skip, show a lightweight prompt before advancing:
```
Why are you skipping?
[ Uncertain — can't decide ]   [ Risky — avoiding negative marking ]
[ Completely unfamiliar ]      [ Running out of time ]
                                                    [ Skip without reason → ]
```
Store as a new `skip_reason` field in `answer_metacognition` table.
This data signals: is the user applying good exam strategy (skipping tactically) or
skipping out of disengagement?

*Part B is optional and should be built as part of the metacognition capture feature, not
as a prerequisite for Part A. Ship Part A first independently.*

**Resolution:** Fixed 2026-05-11. Added `skipQuestion()` in `web/src/app/diagnostic/page.tsx` — calls `api.submitAnswer` with `skipped: true, user_answer: null`, sets `revealed` so Next/Finish buttons appear. Skip button hidden once any option is selected. Skipped card shows correct answer. Finish screen shows skipped count separately; score % is calculated over attempted questions only (not skipped). Backend was already complete.

---

## Resolved

### ISSUE-003 — Session notes: explore links, parallel notetaking, plan personalisation
**Noticed:** 2026-05-12  
**Reported by:** Rahul (approved scope same day)  
**Status:** Resolved  
**Priority:** P1  
**Linked feature:** `FEATURES.md` — Notes deep-links + selection explain; Parallel session notes + plan signals

**What happened:**  
User approved (1) actionable links inside vector-sourced notes + on-demand “explain selection”, (2) parallel structured notetaking during read + quiz, (3) notes drawer **closed by default** once a session starts, (4) entries in FEATURES + ISSUES.

**The problem:**  
Notes lacked per-excerpt source links; no way to deep-dive a highlighted phrase from the notes card; no persisted parallel notes; planner did not see self-reported weak signals.

**Current state of the code (2026-05-12):**  
- `quiz.py` — `build_notes_from_vector_chunks`: after each excerpt, *Open full source:* → `/api/backend/library/file?rel=…` when resolvable under `UPSC_CONTENT_PATH`.  
- `POST /sessions/expand-notes-selection`, `prompts/expand_notes_selection.txt` (Haiku, user-triggered only).  
- `session_user_notes` in `scripts/db_init.py`; `server.py` lifespan creates table if missing.  
- `GET` / `PUT` `/sessions/{session_id}/user-notes` in `backend/routes/sessions.py`.  
- `web/src/app/session/page.tsx` — “Explain selected text” under Key Concepts; **My notes** FAB + slide-over; debounced save; `flushUserNotes` on Finish.  
- `plan_generator.fetch_user_notes_signals()` + `plan_generation.txt` `{{user_notes_signals}}` + rule to prioritise `still_weak` subtopics.

**Resolution:** Shipped 2026-05-12. **Stretch (post–20 May):** PDF page anchors in links, NLP on free-text notes, automatic merge into `prep_profile.json`.

---

### ISSUE-001 — see Open section above (moved to Resolved 2026-05-11)

---

## Won't fix

*(none yet)*

---

## How to add a new issue

1. Copy the format block at the top
2. Increment the issue number (ISSUE-002, etc.)
3. Fill in all fields — especially "Current state of the code" so the next person
   doesn't have to re-investigate
4. Add it under **Open**
5. When resolved: move it to **Resolved**, fill in the Resolution field, commit
