# Track 1: Product & Feature Gap Analysis

**Audit date:** 2026-05-17
**Auditor:** Claude Sonnet 4.6 (product/UX lens)
**Scope:** Devthorium — local AI-powered UPSC Prelims prep system
**Based on:** PLAN.md, FEATURES.md, FEATURE_IDEAS.md, ISSUES.md, HANDOFF.md, all frontend pages, all plan files in `plans/`

---

## 1. Vision vs Reality Matrix

| Feature | Planned in PLAN.md | Built | Gap / Delta | Status |
|---|---|---|---|---|
| **Ingestion pipeline** — PDF, DOCX, GoodNotes OCR, 3-tier PYQ | Yes — ingest.py, all parsers, handwritten_pdf.py (Claude Vision) | Core pipeline shipped. 11,146 ChromaDB chunks, 1,081 PYQ questions (2009–2025) | GoodNotes Vision OCR path exists in PLAN.md architecture but untested in logs. Handwritten PDF parser referenced but not confirmed live. | Partial |
| **Topic Priority Weighting** — decay formula (0.9^year × frequency) | Yes — priority_scorer.py | Shipped. 139 subtopics now have real weights after May 12 fix + full retag ($0.05 Haiku run). | Was broken until May 12 (70% of PYQs unmatched). Now fully operational post-retag. | Done |
| **Diagnostic Phase — Time-boxed mode** | Yes — Mode A | Shipped with live countdown, auto-close on expiry, server-side 409 guard | Was broken (timer existed in config but never enforced) until May 16. Now enforced. | Done |
| **Diagnostic Phase — Fixed set mode** | Yes — Mode B | Shipped | — | Done |
| **Diagnostic Phase — Open-ended mode** | Not in PLAN.md | Shipped May 16 | Scope addition — not in original vision, added reactively to address UX friction of upfront count commitment | Unplanned addition |
| **Per-subtopic adaptive questioning (Round 1/2 logic)** | Yes — 75%/50% thresholds with Round 2 for Uncertain | NOT shipped. Current diagnostic does multi-subtopic coverage (10 subtopics × 1 question) but the two-round adaptive cycle with per-subtopic score gates is absent. | Critical gap. The system cannot distinguish "Assessed: Strong" from "Uncertain" after 5 questions per subtopic. No Round 2 escalation. | Missing |
| **Mid-day confidence check (Condition A/B/C triggers)** | Yes — auto-jump to Phase 2 based on PrepProfile confidence | NOT shipped. No automatic transition logic. User manually decides when to stop diagnostics and move to revision. | Significant gap — the system never autonomously recommends "you're ready to advance" or "you're clearly weak, start revision." | Missing |
| **"Pause & Analyse Now" button** | Yes — user triggers analysis mid-diagnostic | Analysis page exists at `/analysis` but is a standalone trigger page, not contextually embedded in the diagnostic flow. User must navigate away from an active session. | Friction — the signal for mid-day analysis break is not in the diagnostic flow itself. | Partial |
| **Self-Attestation (SAR system)** | Yes — full SAR logic, 0.20–0.90 range | Shipped. SAR score, validation quiz (12Q), effective level calculation, transparent display on Tracker. | The original plan specified "12 questions: top-weighted PYQs + 2 current affairs." Unclear if current affairs questions are specifically included. Attestation page has no Skip/Previous button (other pages do). | Mostly done |
| **Content buffer strategy** — batch pre-generate all sessions in 2–3 API calls at day start | Yes — zero API calls during quiz | Shipped partially. `prewarm_notes_cache.py` pre-warms notes. Quiz questions are generated on-demand at session start (30–40s wait), not pre-batched for the whole day. | Major gap vs original cost vision. The plan promised $0.15/day for pre-generated content; actual model is per-session generation with live waits. | Partial |
| **Adaptive Revision Phase — score-based session format decision** | Yes — `<50%` → Notes first; `50–75%` → Light notes + quiz; `>75%` → Quiz only, harder | Shipped structurally. Plan generator uses `notes_then_quiz` vs `quiz_only` format. But the threshold logic is LLM-decided (Claude decides format), not deterministically enforced by Python. | Partially met — format selection happens, but accuracy of threshold application is unverifiable. | Partial |
| **Morning "Plan Today" button** | Yes | Shipped on `/planner` page | No confirmation that re-planning mid-day is guarded properly (spec exists, one fix shipped May 15). | Done |
| **Evening "Sync & Plan" button** | Yes | Shipped on dashboard. Triggers batch_analyse + plan_generator. | Users must trigger manually — no reminder/notification mechanism. | Done |
| **CSAT — fully separate system** | Yes — separate tracker, sessions, no GS interaction | Routes (`/csat`) and frontend page exist. Page is a stub: "coming soon." The CSAT prep profile (`prep_profile_csat.json`) does not exist. No CSAT diagnostic has ever run. | Shipped in architecture only. Zero functional reality. | Missing |
| **Tracker — per-topic readiness, trend, last tested, hours-to-75%** | Yes | Shipped. Topic accordion, risk levels, coverage bars, gaps list, hours-to-75% estimates. | Trend (improving/stable/declining) is not shown — PLAN.md specified this. Tracker topic breakdown requires Sync to populate (not live). | Mostly done |
| **Day 11 view — final readiness summary, attempt order, last-minute list** | Yes — specific Day 11 view planned | NOT shipped. Strategy page shows a static attempt order list (hardcoded, not personalised to actual scores) and static PYQ patterns. No "Day 11" personalised summary based on real data. | Missing personalisation. The "Exam Day Strategy" content is good generic advice but not driven by the user's actual prep_profile. | Missing |
| **Phone + PC via same WiFi** | Yes | Shipped via Tailscale (even works off-network). | Tailscale is a stronger solution than planned. | Done/Exceeded |
| **Offline HTML export + JSON import** | Yes — fallback for off-network | NOT shipped. | Low-priority given Tailscale works, but the fallback safety net doesn't exist. | Missing |
| **Session history / review** | Not in PLAN.md | Shipped May 14 — `/sessions` and `/sessions/[id]` pages | Scope addition. High value — user explicitly asked for it (ISSUE-008). | Unplanned addition |
| **Question deduplication** | Implied by quality bar | NOT shipped. `question_hash` column exists but never filters generation. Same questions can repeat across sessions. | Known bug (P4 in HANDOFF.md). | Missing |
| **Streak + daily time dashboard widget** | Not in PLAN.md | Time tracker data collected and shown on Tracker page. Streak (consecutive days) still missing from dashboard. | `plans/streak_tracker.md` exists. Time data is tracked but no streak counter on dashboard. | Partial |
| **Exam simulation mode (full mock)** | Listed as "Mock test mode" in PROJECT.md, rough notes only | Shipped May 17 as `/exam-sim`. Supports multi-subject, custom Q count, timed. Per-subject + per-topic results. | Significantly stronger than the "rough notes" spec in PROJECT.md. Not fully planned. | Unplanned (exceeded planned spec) |
| **Content feedback + prompt training** | Not in PLAN.md | Shipped May 17 — `ContentFeedback` component, `question_notes` table, `apply_feedback.py` | Major unplanned addition. High value for long-term quality. Reactive to Rahul's observation during sessions. | Unplanned addition |
| **Auto-start on Mac reboot** | Not in PLAN.md | NOT shipped. Both servers require manual start after every restart. | Known open issue (P7). | Missing |
| **Multi-user / dynamic user_id** | Mentioned as future in PLAN.md | `user_id = 'user_1'` hardcoded everywhere. | By design for now. Not a current-exam issue. | Deferred |
| **Session resumption** | Partially planned (localStorage state restore shipped) | Active quiz survives page reload. Full "resume later" (close app, come back hours later) deliberately excluded per `plans/session_resumption.md`. | Scoped down appropriately. | Partial (intentional) |
| **Dimension-aware scoring (4–8 dimensions per subtopic)** | Not in PLAN.md | Shipped May 16 — FEATURE-027. 205 subtopics × 4–8 dimensions, dimension tracking per answer. | Significant unplanned architecture extension. Adds granularity beyond what PLAN.md envisioned. | Unplanned addition (high value) |
| **Multi-subtopic merged sessions** | Not in PLAN.md | Shipped May 17 — up to 4 subtopics per session, PYQ-weighted question allocation, cross-subtopic notes. | Unplanned. Adds flexibility the original plan didn't have. | Unplanned addition |
| **Plan validation layer (deterministic rules)** | Implied — "8 scheduling rules" in PLAN.md | NOT shipped. Claude decides plan, rules are prompt constraints only. Python validation layer does not exist. | P6 in HANDOFF.md. Claude can violate scheduling rules silently. | Missing |
| **Spaced repetition for weak subtopics** | Listed in PROJECT.md "Planned" | NOT shipped. The plan generator re-schedules weak subtopics, but not via a proper spaced-repetition algorithm (e.g. SM-2). | Listed in PROJECT.md but never specced or built. | Missing |

---

## 2. Missing User Journeys

### Journey 1: First-time user setup
**What the user needs:** A guided experience that tells them what to do first, captures their exam date, and explains how the system works.
**What exists:** `/setup` page with sliders for total days and daily hours. Functional but dry — a form, not an experience. If user skips setup, dashboard shows 0% with no clear next step.
**What's missing:** The onboarding redesign (`plans/onboarding_redesign.md`) was specced in May but never built. No exam date input (only total days, which requires the user to calculate). No "start here" hard gate. New user who lands on dashboard sees empty bars and unclear CTAs.
**Impact:** High. First session determines whether Rahul trusts the system. Current experience is confusing on first open.

### Journey 2: Day 1–2 Diagnostic — full cycle with adaptation
**What the user needs:** Complete all subjects in priority order, get mid-day signals when enough is known, and receive a confident "start revision" recommendation.
**What exists:** Diagnostic page with subject selector, mode selector, question generation. Individual sessions work well.
**What's missing:** (a) No subject priority order is shown to guide which subject to diagnose first. (b) The mid-day confidence check (Conditions A/B/C from PLAN.md) is entirely absent — the system never tells the user "you've done enough diagnostic, switch to revision." (c) Round 2 escalation for "Uncertain" subtopics doesn't exist — every subtopic gets one pass only.
**Impact:** Very high. The core diagnostic loop is incomplete. The user has no guidance on when to stop diagnosing and start revising. They have to judge this themselves, defeating the "adaptive" claim.

### Journey 3: Evening sync and tomorrow's plan
**What the user needs:** After a day of sessions, trigger analysis, get personalised insights, and wake up to a plan that reflects today's performance.
**What exists:** "Sync & Plan Tomorrow" button on dashboard and Analysis page. Works end-to-end.
**What's missing:** (a) No reminder or nudge to do the evening sync — easy to forget. (b) The plan for tomorrow is not visible until the user opens the Planner and reads the session list. The dashboard shows session cards but only after plan generation. (c) No "here's what changed based on today" summary shown after sync on the dashboard.
**Impact:** Medium. The mechanics work but the ritual is invisible.

### Journey 4: Day 11 final prep
**What the user needs:** A personalised exam-day strategy: which subjects to attempt in what order (based on actual scores), top 5 subtopics to skim, and a confidence summary.
**What exists:** Strategy page with hardcoded attempt order (static, not from prep_profile) and generic guessing rules/PYQ patterns. These are well-written but not personalised.
**What's missing:** (a) Dynamic attempt order based on user's actual subject readiness scores. (b) "Last 5 things to revise before the exam" list generated from weakest-but-high-weight subtopics. (c) A celebration/readiness card showing final overall readiness.
**Impact:** High. On Day 11 morning the system should feel like a personal coach. Currently it's a generic advice page.

### Journey 5: CSAT practice
**What the user needs:** Separate comprehension, logical reasoning, and numeracy practice independent of GS.
**What exists:** `/csat` page showing "coming soon." Backend routes `csat.py` exist but are untested. No CSAT prep profile exists.
**What's missing:** Everything functional. CSAT ingestion, first-run setup, diagnostic flow, independent scoring.
**Impact:** Medium. CSAT is Paper II of Prelims — it's a real qualifying barrier. The system completely ignores it functionally.

### Journey 6: Reviewing past sessions to understand mistakes
**What the user needs:** After a session, be able to come back later and re-read questions they got wrong with explanations, without redoing the session.
**What exists:** `/sessions` (history list) and `/sessions/[id]` (read-only review) — shipped May 14.
**What's missing:** No way to filter sessions by subject or subtopic. No way to see "all wrong answers across all sessions on Polity." History is purely chronological.
**Impact:** Low-medium. The base journey exists; filtering/search is the gap.

### Journey 7: Loading experience during quiz generation
**What the user needs:** Something to do or read during the 30–40 second quiz generation wait.
**What exists:** A disabled button showing "Generating questions... (15–30s)" text. The wait is real and frequently 30–40 seconds.
**What's missing:** Interactive loading state — a tip carousel, a "while you wait, review this concept" flash card, or at minimum an animated progress indicator. This was identified in simulation_log.md (Step 2) and ISSUE-021, logged as resolved but only via a session UX PR that added a green badge — the loading wait itself was never addressed.
**Impact:** Medium-high. UX during a 40-second wait with no feedback is a trust-breaking moment, especially on a phone.

---

## 3. Scope Creep (Unplanned but Built)

Items built reactively that were not in the original PLAN.md:

| Item | When shipped | Why it was built | Net assessment |
|---|---|---|---|
| **Session history pages** (`/sessions`, `/sessions/[id]`) | May 14 | ISSUE-008: Rahul wanted to re-read completed sessions. Obvious omission discovered during real use. | High value. Should have been in PLAN.md. |
| **Content feedback system** (`ContentFeedback`, `question_notes`, `apply_feedback.py`) | May 17 | Rahul observed note-taking could double as training data (ISSUE-017). | High long-term value, but adds complexity. For a 10-day exam sprint, the feedback data has minimal turnaround time to actually improve prompts before the exam. |
| **Open-ended quiz mode ("Open Practice")** | May 16 | UX friction — forcing a question count upfront felt wrong during practice. | Good addition. Addresses real friction. |
| **Dimension-aware subtopic scoring** (205 subtopics × 4–8 dimensions) | May 16 | Emerged from analysis of subtopic coverage gaps. | High architectural value. Adds real measurement granularity. But the complexity cost (new table, new scoring branch, dimension tracking per question) may not have been planned budget-appropriately. |
| **Multi-subtopic merged sessions** | May 17 | Needed for exam-sim and for planner efficiency. | Good addition — enables more realistic practice. |
| **Exam simulation mode** (`/exam-sim`) | May 17 | PROJECT.md had rough notes for "mock test mode" but it was listed as P3 with no spec. Shipped as a full, well-specced feature. | Good. Should have been earlier in plan. |
| **User-editable daily plan** | May 16/17 | IDEA-003: AI plan doesn't always match what Rahul wants that day. | High value. Addresses real autonomy need. |
| **Cross-session question deduplication prompt logic** | May 16 | Fix for ISSUE-026 (question repetition). | Necessary fix, not scope creep. |
| **Deep Dive mode in Diagnostic** (10Q per single subtopic) | May 16 | Needed to diagnose ISSUE-026 (question clustering). | Good addition, especially for focused revision. |
| **Topic-level hierarchical coverage** (FEATURE-028) | May 16 | Emerged from subtopic tracking analysis. | Significant unplanned architecture extension. Adds real value but was a multi-phase, multi-PR effort. |
| **Tailscale network binding** | May 11 | Original plan was same-WiFi only; Tailscale enables any-network phone access. | Better than planned. |

**Scope creep pattern:** The system was built in a tight feedback loop where Rahul used the product during real study sessions and reported issues immediately. This generated reactive feature additions that are individually high-value but collectively expanded scope well beyond the original 7-phase plan. The result is a richer system than planned, but one that still hasn't finished some of the original P0 commitments (mid-day confidence check, Round 2 diagnostic, CSAT functional, Day 11 view).

---

## 4. UX Gaps (Frontend)

### `/` — Dashboard
- **Empty state problem:** When no sessions have been done (new user), the dashboard shows 0% overall readiness, 9 subject bars all showing "—", and 4 quick-action buttons with no hierarchy. There is no "Start here" call-to-action that makes the next step obvious.
- **No sync reminder:** After completing sessions, there is no visible nudge to run "Sync & Plan Tomorrow." Users who forget this lose continuity.
- **Plan card shows raw IDs:** "history_amac → ind_valley_civilization" instead of "Ancient, Medieval & Culture → Indus Valley Civilisation." Underscores are stripped but the overall presentation feels technical.
- **Format badges are raw strings:** "notes then quiz" shown in session plan cards without capitalisation. Minor.
- **No day progress indicator:** "Day 6 of 10" is shown in the header, but there's no visual showing "you have done 3 sessions today out of 5 planned" or today's completion percentage.
- **Sync button label confusion:** "Sync & Plan Tomorrow" implies it only plans tomorrow. It also updates today's profile. The label undersells what it does.

### `/diagnostic` — Diagnostic Session
- **No subject priority guidance:** User sees a flat dropdown of all 9 subjects. The system knows Polity is highest PYQ priority — this should guide the user. Even a small "(recommended first)" label would help.
- **Deep Dive subtopics are hardcoded:** The `DEEP_DIVE_SUBTOPICS` object in `diagnostic/page.tsx` is a hardcoded list of 6 subtopics per subject. This doesn't use the actual syllabus.json. If the syllabus is updated, this list becomes stale. It also omits most subtopics.
- **Notes panel is a floating button that covers navigation:** On mobile, the "My notes" FAB overlaps with the navigation area. The notes panel taking the full right side is well-executed but the FAB placement needs refinement for small screens.
- **No progress bar during generation:** 30–40 second wait with only a button showing "Generating questions... (15–30s)." The label undersells the wait (it's often 40s). No animation, no tip, no progress.
- **Attestation page lacks Previous/Skip buttons:** `/attestation` does not have the Previous button that both diagnostic and session pages have. In a 12-question validation quiz, being unable to go back is a meaningful UX gap.
- **Mode selector "Quiz Mode" vs "Session Type":** Two separate toggles on the diagnostic page — "Session Type" (Practice Set / Timed Quiz / Open Practice) and "Quiz Mode" (Standard / Deep Dive). Users may not immediately understand how these two dimensions interact. "Standard + Timed Quiz" vs "Deep Dive + Practice Set" — the combinations are not all tested or clearly explained.
- **Open Practice note:** "Answer as many as you want. Save & Close after any question." — accurate but the "Save & Close" button only appears after an answer is revealed, not before. First-time users may not know the escape path.

### `/session` — Today's Sessions
- **Session cards show subtopic_id not subtopic name:** "ir_governance → g20_g7_brics_sco" instead of "IR & Governance → G20, BRICS & SCO." The syllabus tree is loaded (`getSyllabusTree()`) and available — names should be resolved.
- **Edit modal in session page vs planner page is duplicated:** Both `/session` and `/planner` have a session editor modal, but they are different components with slightly different field sets. The `/session` editor does not support multi-subtopic selection (4-subtopic picker is only in `/planner`). Inconsistency.
- **Notes panel persists across sessions awkwardly:** When finishing one session and starting the next, the notes panel FAB stays visible. If the user opens it, they see the previous session's notes. The panel should clear or show session context more clearly.
- **No confirmation before "Finish Session":** Clicking "Finish Session" is irreversible. A brief confirmation prompt ("Are you sure? You have 3 questions left unanswered.") would prevent accidental submissions.
- **"Next Session" after finish goes to session list, not the next session directly:** After completing a session, "Next Session" clears the active quiz and shows the session list again. It doesn't automatically start or highlight the next pending session. Extra click required.
- **Time taken is always 0 in session/page.tsx:** Unlike diagnostic/page.tsx which computes `timeSec` correctly, the session page's `submitAnswer` hardcodes `time_taken_sec: 0`. This means the per-question time data (which feeds the difficulty engine and metacognition analysis) is broken for all adaptive sessions.

### `/planner` — Study Planner
- **No confirmation before re-generating plan:** Clicking "Plan Today" again silently overwrites the existing plan. The `user_editable_plan.md` spec noted this should have a confirmation guard when `is_user_edited: true`, but it is not implemented.
- **"Day X Plan" header shows `plan.day` which may be undefined:** The header renders "Day undefined Plan" if the backend doesn't return a `day` field. Defensive rendering needed.
- **Planner and session page are conceptually redundant:** Both pages show today's sessions and allow editing them. The planner is for planning; the session page is for doing. But the `/session` page also has an inline edit modal, creating confusion about which page is canonical for edits.
- **No "Add session" button on Planner:** The `user_editable_plan.md` spec proposed an "Add session" button below the list. It was not implemented. Users can only edit existing sessions, not add new ones.
- **Drag-to-reorder is absent:** Spec proposed up/down arrows as v1 fallback; not implemented. Session order is fixed as generated.

### `/tracker` — Preparation Tracker
- **Trend (improving/stable/declining) is not shown:** PLAN.md explicitly promised trend arrows per subject/topic. Not in the UI.
- **Topic accordion requires Sync to populate:** "Run Sync to generate topic breakdown" is the message if no topics exist. For a new user who hasn't synced, the entire subject breakdown accordion shows nothing. This is a poor first impression.
- **Gaps list shows subtopic_id not name:** "dir_principles_of_sp" instead of "Directive Principles of State Policy." The raw ID leaks through.
- **Gaps list truncates at 20:** `gaps.slice(0, 20)` is hardcoded. With 205 subtopics, there could be 150+ gaps early on. The user can't see all gaps without a "Show more" or pagination.
- **Hours-to-75% estimates are rough:** Shown per gap row but the basis for the estimate is unclear to the user. No tooltip or explanation of how the estimate is computed.
- **SAR card is prominent but most users won't use attestation:** If the user hasn't done any attestation, the SAR widget shows nothing. A prompt to "Try self-attestation to get a head start" would be more useful than an empty widget.

### `/strategy` — Exam Readiness
- **Attempt order is hardcoded, not personalised:** The attempt order table (Polity first, Environment second, etc.) is static JSX. It does not read from the user's actual subject readiness scores. A user who is weak at Polity and strong at Economy should attempt them in a different order.
- **PYQ patterns section is generic:** These are accurate patterns but they are the same for every user. No personalisation based on the user's weak areas.
- **Trajectory note is a placeholder:** `trajectory.trajectory_note` is shown as italic text, generated by the backend. This could be powerful ("You need to test 8 more subtopics in History to be on track") but its quality depends entirely on the batch_analyse prompt — which has not been quality-reviewed.
- **"Focus" subtopic list truncates at 3:** `s.top_priority_untested.slice(0, 3)` — only 3 shown. A "see all" toggle would be useful especially for subjects with many untested subtopics.

### `/exam-sim` — Exam Simulation
- **No skip button during simulation:** During the running view, unanswered questions can be skipped by clicking "Skip" before answering, but once you move past a question without answering, there's no way to mark it skipped-intentionally vs simply not reached. In UPSC, skipping is a strategic choice — there should be a clear Skip button that marks it differently than "just didn't reach."
- **Generation wait during setup is severe:** For 50–100 questions across multiple subjects, the generation time could be 60–90 seconds. The loading button says "Generating questions — this may take 20–40 seconds..." but the actual wait can be longer. No progress indicator.
- **Results don't link back to question review:** The results page shows scores per subject/topic, but there's no way to drill down into the actual questions you got wrong. The session review page (`/sessions/[id]`) exists but isn't linked from exam-sim results.
- **Exam simulation doesn't feed into prep profile:** By design (HANDOFF notes: "intentionally excluded from prep_profile scoring"). But this means a user who does a 50-question simulation and scores poorly on Environment will not see that reflected in their tracker or next plan.

### `/analysis` — Session Analysis
- **This page is just a button:** The analysis page is the thinnest page in the app. It's one button ("Run Batch Analysis") and then a text dump of the Claude analysis output. There are no charts, no trend lines, no visual before/after comparison.
- **No history of past analyses:** Running Sync again overwrites the display. There's no way to compare "what did analysis say yesterday vs today?"

### `/setup` — Setup
- **No exam date input:** User enters total days as a number (or via presets), not an actual exam date. This requires mental arithmetic and produces confusion when real exam date changes.
- **Phase breakdown math doesn't always add up:** The phase breakdown uses rounding that can cause total phase days to differ from total_days by 1–2. Minor visual bug.
- **No warning if config is already set:** Revisiting `/setup` shows pre-filled values, but there's no indication of what the current config is or when it was set. A "Last saved: May 11" timestamp would help.

### `/csat` — CSAT Practice
- **Stub page:** Shows only "coming soon" text. No estimated timeline, no instructions for what needs to happen for it to activate. Users have no way to know if they need to add material or wait for a feature.

### `/attestation` — Self-Attestation
- **No Previous button in validation quiz:** 12 questions, no ability to go back. A careless click cannot be undone.
- **Attestation is a dead end on the nav:** Accessible from the tracker's SAR widget, but there's no nav link to attestation in the sidebar/top nav. Users who want to attest a subject have to know to go to the tracker first.
- **No way to see previous attestations:** No history of past attestations per subject. User can't see "I attested Polity as Strong on May 12 with 75% validation — SAR went from 50% to 55%."

---

## 5. Product Coverage Assessment

### How well does the current system deliver on the 10-day UPSC Prelims prep goal?

**Overall verdict: 55–60% of the stated goal is delivered well. 40–45% is either missing, broken, or significantly weaker than promised.**

#### What the system does well
- **Question quality:** Claude-generated questions are UPSC-style with varied formats (statement-based, assertion-reason, matching). Explanations include correct answer rationale + wrong option reasoning. This is genuinely strong.
- **PYQ-weighted prioritisation:** 1,081 PYQs across 17 years, decay-weighted, driving subtopic priority. This is the core intellectual contribution and it works.
- **Session experience:** The quiz flow (submit button, previous navigation, skip, explanation, deep dive, notes panel) is polished and functional. Multiple UX iterations have landed in a good state.
- **Tracking granularity:** Topic → subtopic → dimension tracking with coverage bars, risk levels, and gap lists is significantly better than most self-study apps.
- **Adaptivity infrastructure:** The system has all the ingredients for adaptivity (scores, weights, dimension tracking, session history) — the data is there.

#### Where the system falls short of the 10-day goal

**1. The adaptive loop is incomplete.** The most important feature of a "10-day adaptive system" is that it *knows when to stop diagnosing and start revising*, and *knows exactly which subtopics need revision vs which can be skipped*. The mid-day confidence check (Conditions A/B/C from PLAN.md) is entirely absent. The user has to make this call manually, every day.

**2. Coverage is dangerously low with 5 days to exam (as of May 17).** The HANDOFF.md shows 15/205 subtopics tested (7.3% coverage). With 5 days left and 205 subtopics, the system needs to test ~38 new subtopics per day just to achieve full first-pass coverage. The current 10-question diagnostic (10 subtopics per session) means ~4 sessions just for first-pass coverage — and there's no revision yet. The plan generator needs to be much more aggressive.

**3. The 10-day journey has no phase transitions.** PLAN.md promised Day 1–2 diagnostic → Day 3–10 adaptive revision. In reality, the system doesn't distinguish phases. The user can run diagnostics on Day 9 and the system won't object. The planner doesn't say "you should have stopped diagnosing 3 days ago."

**4. CSAT is a stub.** UPSC Prelims requires clearing the CSAT cutoff (33%). A system that promises "10-day Prelims prep" but provides zero CSAT practice is incomplete by definition.

**5. The Day 11 experience doesn't exist.** The most critical moment — exam morning — has no personalised support. The generic strategy page helps, but "here are your top 5 subtopics to skim based on your actual performance" does not exist.

**6. Question repetition still occurs.** Despite the ISSUE-026 fix (hash-based exclusion from prompts), there is no deterministic deduplication mechanism. The hash list is passed to Claude as a soft instruction, which Claude may violate. For a 10-day system, seeing the same question twice is a trust-breaking event.

---

## 6. Multi-Exam Expansion Gap Analysis

Rahul noted in ISSUE-021 that the system should eventually support UPSC Mains, IES (Indian Economic Service), and RBI Grade B alongside Prelims. This is a significant architectural expansion. Below is an honest analysis of what would need to change.

### Current assumptions baked into the architecture

1. **Single exam type:** Everything from syllabus.json to batch_analyse to the strategy page assumes UPSC Prelims MCQ format.
2. **Single user:** `user_id = 'user_1'` is hardcoded throughout.
3. **Fixed 205-subtopic syllabus:** The syllabus.json is UPSC Prelims only.
4. **MCQ-only question format:** All question generation, scoring, and session logic assumes 4-option MCQ with a single correct answer.
5. **Single prep profile:** `prep_profile.json` covers GS1 Prelims. No concept of multiple concurrent exam tracks.

### What each exam expansion requires

#### UPSC Mains
- **Different question format:** Mains has 250-word and 500-word descriptive answers, not MCQs. The entire quiz engine, scoring engine, session flow, and result display would need a parallel descriptive answer path.
- **Different evaluation model:** Descriptive answers cannot be scored by `score_engine.py`. Claude would need to evaluate answer quality against model answers — a fundamentally different cost model ($0.05–0.10 per answer vs near-zero for MCQ).
- **Different syllabus:** Mains GS I-IV papers have separate syllabi. A new `syllabus_mains.json` would be needed.
- **Answer writing practice flow:** The entire session UX (options → answer textarea, word count, evaluation rubric display) needs redesign.
- **Essay mode:** GS IV (Ethics) and Essay paper require free-form writing, even more open than GS descriptive.
- **Estimated effort:** 6–8 weeks of new development. Not a configuration change.

#### IES (Indian Economic Service)
- **Heavy overlap with UPSC Prelims Economy subject:** Economy subtopics (monetary policy, fiscal policy, international trade, WTO) are in the current Prelims syllabus. 60–70% of existing Economy content would apply.
- **Different scope:** IES has deeper economics (micro, macro, econometrics, statistics) not in the Prelims syllabus. New subject-level additions to syllabus.json needed.
- **MCQ + descriptive mix:** IES Prelims is MCQ; IES Mains is descriptive. Same Mains challenge as above for the written portion.
- **Separate exam config:** A new "exam_type" parameter in setup, separate prep_profile, separate plan generator rules.
- **Estimated effort:** 3–4 weeks for Prelims track (mostly syllabus expansion + new PYQ ingestion). Another 6–8 weeks for Mains.

#### RBI Grade B
- **Three phases:** Phase I (MCQ, including Reasoning, English, General Awareness, Quantitative Aptitude); Phase II (Economic and Social Issues, English Writing, Finance and Management — descriptive); Phase III (Interview).
- **General Awareness:** Overlaps with UPSC Current Affairs and Economy. Significant reuse.
- **CSAT-like numeracy:** The "Quantitative Aptitude" component is similar to CSAT. If CSAT were functional, it could partially support this.
- **Finance & Management:** New domain not in Prelims syllabus at all. Requires new content ingestion and syllabus.
- **English Writing:** Descriptive writing evaluation — same challenge as Mains.
- **Estimated effort:** 4–6 weeks for Phase I (MCQ). 8–10 weeks for Phase II + III.

### Specific architectural changes required for any multi-exam expansion

| Component | Change required |
|---|---|
| `data/syllabus.json` | Needs `exam_type` field or separate files per exam (`syllabus_prelims.json`, `syllabus_mains.json`, etc.) |
| `data/prep_profile.json` | Needs to be keyed by `exam_type` or separated into exam-specific files |
| `scripts/plan_generator.py` | Must be aware of which exam is active; scheduling rules differ fundamentally between Prelims (cover breadth in 10 days) and Mains (write 20 answers per day) |
| `scripts/batch_analyse.py` | Must use the correct syllabus map for the active exam |
| `backend/routes/quiz.py` | Must support descriptive question generation for Mains-type exams |
| `scripts/score_engine.py` | MCQ scoring is irrelevant for descriptive answers; needs a parallel evaluation path |
| `web/src/app/setup/page.tsx` | Must ask "which exam are you preparing for?" before asking days/hours |
| `web/src/app/session/page.tsx` | Must render descriptive answer UI (textarea, word count) alongside MCQ UI |
| `data/upsc.db` schema | `user_id = 'user_1'` must become dynamic; `exam_type` column needed in `quiz_sessions`, `session_answers`, `subtopic_scores` |
| `ChromaDB collections` | Currently one collection. Multiple collections (by exam type) or metadata-filtered queries needed |
| `web/src/app/strategy/page.tsx` | Hardcoded UPSC Prelims attempt order must become exam-aware |

### Realistic minimum viable expansion path

The lowest-cost expansion is adding **IES Prelims** because:
1. Economy content already exists and is high-quality
2. MCQ format — no new scoring engine needed
3. Syllabus expansion is bounded (add ~40–50 new subtopics)
4. Can share the same session/diagnostic/tracker UI with minor labels changes
5. Existing PYQ ingestion pipeline can handle IES PYQ PDFs

Estimated: 2–3 weeks of focused development if a separate `exam_type = "ies"` config flag is added and separate syllabus/profile files are used.

**The hardest expansion is UPSC Mains** because it requires rethinking the core product loop — not just adding data.

---

## 7. Top 10 Product Recommendations

### Recommendation 1: Build the mid-day confidence check (Phase gate logic)
**Problem it solves:** Users have no signal for when to stop diagnosing and start revising. The system promises adaptive phase transitions but never executes them. Without this, the "adaptive" label is largely marketing.
**How it improves the system:** After completing each subject's diagnostic sessions, the backend checks Conditions A/B/C from PLAN.md and surfaces a recommendation banner: "You've assessed 5 subjects. Your profile is confident enough to begin revision — start adaptive sessions today." This turns the system from a passive quiz tool into an active guide.
**Priority:** P0 — exam-critical. Missing this means users don't know when to pivot from diagnostic to revision.

### Recommendation 2: Fix the Day 11 / Exam Eve view
**Problem it solves:** The most high-stakes moment (exam morning) has no personalised support. A generic strategy page is available but it doesn't use actual performance data.
**How it improves the system:** Build a "Day 11" view that appears when `days_remaining <= 1`. It should show: (a) overall readiness score with a confidence label, (b) the 5 subtopics with highest PYQ weight that the user tested below 65%, labelled "Quick revision priority," (c) personalised attempt order based on actual subject readiness (strongest subjects first to build momentum, weakest subjects after the confident sections), (d) a "You're ready" or "Watch out for X" message.
**Priority:** P0 — this is the promised Day 11 experience and it doesn't exist.

### Recommendation 3: Fix time_taken_sec in session/page.tsx
**Problem it solves:** Per-question time data is always 0 for all adaptive sessions (only diagnostic page captures it correctly). The difficulty engine and metacognition analysis are running on corrupt data for the majority of the user's sessions.
**How it improves the system:** Single-line fix — add a `questionStartTime` ref and compute elapsed time in `submitAnswer()`, identical to `diagnostic/page.tsx`. This immediately makes the difficulty engine and time analytics work correctly.
**Priority:** P0 — data corruption bug. One developer-hour to fix.

### Recommendation 4: Replace hardcoded strategy page with profile-driven content
**Problem it solves:** The attempt order and focus areas on the Strategy page are static and generic. A user who is weak at Polity and strong at Geography should see a different recommended attempt order.
**How it improves the system:** Read the user's `prep_profile.json` subject readiness scores and generate a personalised attempt order (highest readiness first for momentum, unless a weak subject has very high PYQ frequency in which case it needs early attention). The "PYQ Patterns" section should be filtered to only show the subjects where the user is most at risk.
**Priority:** P1 — the Strategy page is the exam-day guide. It must be personalised.

### Recommendation 5: Build the onboarding redesign (3-step flow)
**Problem it solves:** New users land on a settings form with no emotional hook, no exam date input, and no guidance on what to do first.
**How it improves the system:** The `plans/onboarding_redesign.md` spec is already written — exam date anchor → daily hours commitment → plan preview with "Start My Prep" CTA. This turns the first 2 minutes from "I opened a form" to "I committed to a plan." Add a hard gate: if no config exists, show a full-width onboarding prompt that replaces the empty dashboard.
**Priority:** P1 — first impression determines retention. The spec is already done.

### Recommendation 6: Fix the CSAT stub — build at least a first-run diagnostic
**Problem it solves:** CSAT is a real exam qualifying requirement (33% cutoff). The system that claims "10-day Prelims prep" provides zero CSAT support.
**How it improves the system:** At minimum, activate the existing CSAT backend routes, create `prep_profile_csat.json`, and let the user run a CSAT diagnostic (comprehension + reasoning only — skip numeracy to avoid LLM calculation errors, per ISSUE-012's lesson). Show a CSAT readiness score separate from GS. A basic working CSAT loop is 3–4 days of work.
**Priority:** P1 — Paper II is a qualifier. Missing it is a product-completeness issue.

### Recommendation 7: Add deterministic plan validation layer
**Problem it solves:** Claude decides the plan, scheduling rules are prompt constraints that Claude can silently violate. There's no way to know if today's plan respects the 8 scheduling rules.
**How it improves the system:** Post-generation Python validator checks: (a) total session time fits within `daily_hours × 60` minutes, (b) minimum 3 subjects covered, (c) no re-testing subjects scored >75% more than once this week, (d) untested-high-weight subtopics are represented. If any rule fails, either correct it deterministically or retry the Claude call with the specific violation noted. This makes the plan trustworthy.
**Priority:** P1 — without this, the scheduling rules are aspirational, not enforced.

### Recommendation 8: Build a loading experience for quiz generation
**Problem it solves:** The 30–40 second (sometimes 60+ second) wait for quiz generation has no engagement or feedback. Users stare at a disabled button.
**How it improves the system:** Show an animated loading state with: (a) a progress animation (not a spinner — something that suggests "thinking"), (b) rotating tip cards from a static tips array ("While you wait: Polity Schedule 7 covers distribution of legislative powers. India has 3 lists..."), (c) accurate time estimate ("Usually 25–40 seconds. Timer starts after all questions load."). For exam-sim, this is even more critical — 50-question generation can take 60+ seconds.
**Priority:** P1 — trust and perceived quality are degraded by blank-stare loading states.

### Recommendation 9: Add exam date input and auto-calculate total days
**Problem it solves:** The setup page asks for "total days" as a number, requiring the user to calculate from their exam date. This is a friction point and produces errors (user puts in wrong number).
**How it improves the system:** Add a date picker to `/setup`. Auto-calculate `total_days = exam_date - today`. Show the days count as a large amber number. If the user already has an exam date set, show "X days until your exam" on the dashboard. The `onboarding_redesign.md` spec already proposes this — it just hasn't been built.
**Priority:** P1 — this is the first question in the spec. Exam date is the anchor of all planning.

### Recommendation 10: Make exam-sim results feed into prep profile (optional flag)
**Problem it solves:** A user who does a 50-question simulation and performs poorly on Environment learns nothing actionable from the results page — the tracker doesn't update, the next plan doesn't prioritise Environment more.
**How it improves the system:** Add an option on the exam-sim results screen: "Apply simulation results to your prep profile?" If confirmed, the per-subject scores from the simulation feed into a special `simulation_session` type in batch_analyse — counted at a lower weight than a full adaptive session (e.g., 0.5× weight) but still reflected in the tracker and next plan. Users who use exam-sim as a primary learning tool (not just a mock test) would benefit significantly.
**Priority:** P2 — the current "excluded from prep_profile" is a conscious design choice, but it creates a dead end where exam-sim results are informative but not actionable.

---

*This audit was produced as Track 1 of the Devthorium product review sprint. It covers product/UX/feature completeness only. Code architecture, data quality, and backend correctness are covered in separate audit tracks.*
