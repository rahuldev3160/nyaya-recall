---
id: PLAN-011
type: plan
project: devthorium
date: 2026-08-30
status: PROPOSED — research/proposal only, nothing built, nothing run
---

# PLAN-011: 2027 retarget, exam-simulation calibration, IES economics signal, provenance Phase 1 (Recall half)

**Scope note.** Pure research and proposal, per explicit instruction. No code, migration, or
paid API content-generation call was executed to produce this. Companion document:
Descriptive-exams' `.knowledge/plans/PLAN-021.md` covers Scribe's half (areas 1, 3, 4, and
Scribe's half of area 6). Read both together — area 6 in particular only makes sense as one
cross-repo taxonomy.

**Constraints respected:** Recall stays local/phone-only — nothing here proposes hosting it for
multiple users, only Docker-verifying it for portability. Rahul is doing CLC DU 1st semester
concurrently with 2027 prep — every recommendation below is sized against that, not against
unlimited dev time.

---

## Area 1 — Exam-year retargeting

### External verification (web search, 2026-08-30 — not assumed)

No structural exam-pattern or syllabus change is confirmed for any of the three exams' 2027
cycle:

- **UPSC CSE 2027:** notification expected 13 Jan 2027, Prelims 23 May 2027, Mains 20–24 Aug
  2027. Syllabus unchanged since the 2013 restructuring; no revision notified.
- **RBI Grade B 2027:** Phase 2 expected ~July 2027. Pattern unchanged — Papers I & III are
  50% objective/50% descriptive, Paper II fully descriptive. Phase 2 English Descriptive paper
  confirmed as **100 marks total, 90 minutes, three components: Essay + Précis Writing +
  Reading Comprehension** — no office-note/business-letter component exists (an assumption in
  the original brief this research corrects). **The exact per-section mark split is unconfirmed**
  — coaching sources disagree (Essay 40/Précis 30/RC 30 vs. RC 40/Essay 30/Précis 30 both appear
  across different blogs), and neither RBI's own notification language nor Oliveboard's/
  Adda247's exam-pattern pages specify a component-level breakdown, only the 100-mark/90-minute
  aggregate. Treat the per-section split as an open question for Area 4's design, not a
  confirmed fact — don't let a scraped number silently become a hard-coded weighting.
- **IES 2027:** no confirmed pattern change found. Current structure: 6 written papers (2
  common — GS + English, 4 core Economics — General Economics I–IV), 1000 marks + 200-mark
  interview, 3 consecutive days, typically June.

**Conclusion: this is a date/config swap, not a content or format rebuild.** Budget it as such.

### Concrete hardcodes found (grep, current repo state — not the old HANDOFF snapshot)

| Location | Issue |
|---|---|
| `scripts/priority_scorer.py:32` | `CURRENT_YEAR = 2026` — drives the PYQ recency-decay weight `0.9^(current_year-year)` used to prioritize diagnostic questions. Wrong year silently mis-weights every subtopic priority score. |
| `data/prep_config.json` | `target_date: "2026-11-29"` (actually RAS 2026, not UPSC — already stale for the wrong exam), `start_date: "2026-06-06"`, `total_days: 5`. User-editable JSON, trivial to fix, but must actually be updated — the plan/tracker/exam-sim countdown all read from here. Confirmed `backend/routes/plan.py`'s `_get_exam_date()` correctly reads this file dynamically — the old hardcoded `EXAM_DATE` constant bug noted in historical HANDOFF entries is already fixed in code; only the config value itself is stale. |
| `prompts/exam_simulation.txt:28`, `prompts/adaptive_session.txt:27`, `prompts/adaptive_quiz_only.txt:30`, `prompts/diagnostic_quiz.txt:29`, `prompts/deep_dive_quiz.txt:25`, `prompts/generate_dimensions.txt:9` | All six hardcode a "**2024-2026**" window for "recent policy/contemporary-linkage" question generation. Every one of these silently produces stale current-affairs questions once 2027 starts unless fixed. |
| `scripts/generate_audio_prompts.py:204,261,363` | Hardcodes the literal string "UPSC Prelims 2026" into generated audio-script prompt text. |
| `scripts/eco_schemes_pattern_analysis.py`, `scripts/ir_pattern_analysis.py` | One-off analysis scripts with "2026 Prediction List" sections — only matter if Rahul re-runs them for 2027 predictions. |
| `CLAUDE.md` | Claims "2009–2025 coverage (17 years)" for PYQs — real `pyq_questions` table only has 2014–2025 (verified by year-group query; 2009–2013 were never ingested). This is a pre-existing doc-accuracy bug, not a 2027-specific one, but worth fixing in the same pass since it directly affects Area 2's calibration trust. |

### Recommendation

**Small.** A single retargeting pass: (1) bump `CURRENT_YEAR` in `priority_scorer.py`, (2) update
`prep_config.json`'s `target_date`/`start_date`/`total_days` for the real 2027 UPSC Prelims date
once the Jan 2027 notification lands (don't guess it now), (3) replace the six prompts'
hardcoded "2024-2026" with a **computed rolling window** (e.g. `{{current_year-2}}-{{current_year}}`

**DONE 2026-08-30.** `CURRENT_YEAR` bumped, all six prompts + `generate_audio_prompts.py`'s three
"UPSC Prelims 2026" strings + its CA-window note updated to the 2027 literal window, CLAUDE.md's
stale PYQ-coverage claim corrected (2014–2025, not 2009–2025). `prep_config.json` intentionally
left untouched, exactly as recommended, pending the real Jan 2027 notification. **Deviation from
recommendation**: used a literal "2025-2027" string rather than the computed rolling-window
template var suggested above — the six prompt files' render call sites (`sessions.py`, `quiz.py`,
`attestation.py`, `feedback.py`) don't share one renderer, so wiring a computed var through all of
them is a real refactor, not a one-line fix. Left as a follow-up; the literal string unblocks 2027
now and is a 30-second fix again whenever the drift matters (2028+).
templated at generation time) so this never needs a manual fix again — this is also a prerequisite
for Area 2's prompt rework below, (4) fix the CLAUDE.md PYQ-coverage claim to match reality.
No approval gate — none of this touches scored data or existing tables.

---

## Area 2 — Exam-simulation + calibration gap

### What "Exam Sim" actually is today (read from code, not assumed)

`web/src/app/exam-sim/page.tsx` + `prompts/exam_simulation.txt` + `backend/routes/quiz.py`
(`start_exam_simulation`, `_build_exam_sim_allocation`):

- Real countdown timer UI, timer-expiry auto-skip, per-subject/topic results breakdown — the
  *mechanics* of a timed test exist and work.
- User freely picks 2–4 subtopics, a question count, and a duration from 1–180 minutes. There is
  **no fixed 100-question/120-minute/full-GS-Paper-I structure** — the opposite of what a real
  Prelims mock needs (a fixed paper spanning all subjects in fixed proportion).
- Questions are **freshly generated by Sonnet from indexed study-material + current-affairs
  chunks — zero pull from `pyq_questions` or `question_bank`.** A "mock" today is 100%
  synthetic content, grounded only by a text-prompt description of question *types*, never by
  real UPSC questions.
- Difficulty is a flat label ("35% easy / 45% medium / 20% hard") with no grounding in what real
  UPSC ambiguity looks like — no instruction to produce statement-elimination traps, close
  distractors, or scenario-based reasoning specifically.
- Real usage (`quiz_sessions.session_type` counts, direct query): **adaptive 61, diagnostic 23,
  exam_simulation 3** — exam-sim mode exists and works mechanically but has essentially never
  been used. This matches the brief's premise directly: the gap isn't that the feature is
  missing, it's that it's built-but-idle, same shape as Scribe's Mains module (PLAN-021 Area 3).

### The real 2026 paper vs. what Recall currently produces (qualitative comparison)

Real UPSC Prelims 2026 GS Paper I (via published analysis, cross-checked against two sources):
100 questions, 2 hours, subject split roughly History/Art&Culture 20%, Sci-Tech 17%, Economy
16%, IR/Defense 13%, Polity 12%, Environment 10%, Geography 9%, CA/misc 3%. Described as
"decidedly on the tougher side, noticeably lengthier... off established trends" with an
**"ethics-ification"** — scenario-based conflict-resolution questions (e.g. a waste-management
dispute near a tribal hamlet) — and **applied, not recall-level**, current-affairs questions
(e.g. Digital Rupee settlement mechanics vs. UPI, not "what is the Digital Rupee").

Compared against Recall's own `pyq_questions` (real 2023–2025 UPSC PYQs, sampled directly):
existing real PYQs already are dense, multi-statement, often obscure-fact-recall style
("Sanghabhuti... travelled to China at the end of which period?") — so **the real archive Recall
already has is a reasonably faithful reference for calibration.** The gap is not in the PYQ data;
it's that `exam_sim` never uses it, and its own generation prompt has no instruction resembling
"ethics-ification" or "applied not recall" framing at all — its five question types (statement-
based, direct factual, application, contemporary-linkage, match-the-pairs) don't include an
explicit scenario/dilemma-resolution type, which the actual 2026 paper leaned on hard.

One correction to an earlier pass on this same finding: a `question_bank` row that pairs
"Article 15: right to protection of life and personal liberty" was flagged as a factual error —
verified directly against the row (id `77421252-...`) and that's wrong. It's a legitimate
"how many of the following pairs are correctly matched" statement question that *deliberately*
mismatches Article 15 and 21 as one of the incorrect pairs — exactly the trap-style format real
UPSC uses. No factual-error evidence was found in the third-party bucket from this sampling pass.
The underlying point of Area 6 (provenance labeling matters for calibration trust) still stands
on its own merits — it just isn't backed by this particular example.

### Recommendation

**Medium.** Build a distinct **"Full Mock" mode** inside exam-sim, separate from the existing
flexible practice mode (don't remove the flexible one — it's still useful for targeted drilling):

1. Fixed structure: 100 questions / 120 minutes, drawing proportionally across all syllabus
   subjects using PLAN-007's `topic_weights` table (already schema-ready, currently empty for
   UPSC) rather than letting the user hand-pick subtopics.
2. Source primarily from `pyq_questions` (real PYQs, held back from regular practice until mock
   day so they're not memorized in advance) with AI-generated fill only for weight gaps —
   and tag every served question with its `source_type` so the results screen can honestly
   report "N% of this mock was real PYQ vs AI-approximated" (this is the direct payoff of Area
   6's provenance work — sequence that first, see build order).
3. Update `exam_simulation.txt`'s question-type list to add an explicit scenario/administrative-
   dilemma type, and replace the flat 35/45/20 label with qualitative UPSC-trickiness
   instructions (statement elimination, close distractors, applied-not-recall framing) — this is
   the direct prompt-engineering fix for the calibration delta found above.
4. Apply Area 1's rolling current-affairs window fix here too, since this prompt was one of the
   six hardcoded to "2024-2026."

No new schema required beyond what PLAN-007 already added (`topic_weights`, `source_type`) —
this is mostly prompt rework + one new fixed-allocation code path reusing the existing timer/
results UI.

---

## Area 5 — IES Economics coverage gap

**Filed here per the requesting brief, even though the underlying data lives in Scribe's
`data/ies.db`** — investigated by direct read-only SQL query against that file.

### What the data actually shows

`ies.db`'s `topics` table has exactly 4 `paper_id` values: `ge_01`–`ge_04` — General Economics
I–IV. **This means the entirety of `ies.db`'s content is Economics** (1,219 PYQs total: 336 /
307 / 263 / 313 split across GE1–4). Per-topic depth ranges from a low of 16 PYQs (Global
Institutions, Theory of Distribution, Urbanisation & Migration) up to the hundreds — thin in a
few specific topics, but not thin overall. **IES's actual Day 1 (General Studies + Essay) has
zero rows anywhere in `ies.db`** — no `paper_id` for GS or Essay exists at all.

The real finding: `descriptive_attempts` for `ies.db` = **2 rows, total, ever.** Not a content
problem — a usage problem. Rahul's actual 2026 failure ("not ready for the Economics-heavy
paper, skipped Day 2 entirely") lines up with essentially zero practice reps recorded, not with
the content bank being thin or absent.

### Recommendation

**Small.**

1. **Priority 1 — a readiness-dashboard nudge, not new content.** A simple "0 attempts in 45
   days, N days to IES" flag surfaces the real problem (non-use) directly, costs nothing to
   build (the data already exists), and is the single highest-leverage fix here.
2. **Priority 2 — backfill only the handful of genuinely thin GE topics** (16–19 PYQs each,
   5 topics) from official UPSC IES PDFs — cheap, mechanical, worth doing once usage actually
   picks up enough that thinness would matter.
3. **Priority 3, defer — IES Day 1 (GS+Essay) has no content in Scribe at all.** This wasn't
   2026's failure mode, but it's a real gap for a repeat attempt. Recommend deferring until
   Scribe's UPSC GS-Mains module (PLAN-021 Area 3) actually has real usage — GS content for IES
   Day 1 would overlap heavily with that syllabus family, and building a third unused module
   before the first two get used is the wrong sequencing.

---

## Area 6 — Content provenance taxonomy (Recall's half)

### What exists today, in real values (not schema design intent)

`question_bank.source_type` in production has exactly two populated values: `third_party_bank`
(5,181 rows — Vision IAS) and `unclassified_legacy` (321 rows — RBI, pending backfill).
**Zero `official_pyq` and zero `ai_generated` rows exist**, despite PLAN-007's schema already
supporting a full enum (`official_pyq` | `similar_exam_pyq` | `ai_current_affairs` |
`ai_gap_fill` | `third_party_bank` | `official_document_derived` | `unclassified_legacy`).
`generation_batches` = 0 rows (the AI-generation pipeline from PLAN-009 was designed, never
run). `source_documents` = 2 rows, 0 linked to any served question. Real official-style PYQs
live separately in `pyq_questions` (not `question_bank`), and even there `answer_source`
defaults to `ai_inferred` for most rows, not official-key-verified — so today's best "official
PYQ" bucket is itself only semi-trustworthy at the answer-key level.

### Earlier feasibility-study trace

No document named exactly "unified cross-product database feasibility study" was found in
`.knowledge/` or `docs/` in any of the three repos. The closest real prior art:
Descriptive-exams' `AUDIT-008` (2026-06-21, full 6-DB schema/indexing audit) flagged **DECIDE-32**
— "should 'Monetary Policy' in IES/RBI point to one canonical entity in nyaya.db `master_topics`?"
— as pending, unresolved. Separately, this project's own `PLAN-009` §3 and Nyaya-Arena's
`DECIDE-02`/`DECIDE-09` **already independently concluded** that Recall, Scribe, and Arena have
three deliberately disjoint user-identity spaces, and that any shared table/signal across them
requires solving cross-product identity linking first — explicitly out of scope until Rahul
decides otherwise. Any provenance-taxonomy proposal here must respect that: **same schema shape
in each product's own database, never a merged database.**

### Recommendation

**Small (Recall's side).** Recall's schema is already more finely-grained than the four
categories requested (`official_pyq` | `ai_generated` | `coaching_derived` | `self_notes`) — its
existing enum already splits AI into `ai_current_affairs`/`ai_gap_fill` and PYQ into
`official_pyq`/`similar_exam_pyq`. Nothing needs to change structurally; the work is just:

1. Run PLAN-009's already-designed backfill: convert `unclassified_legacy` (321 RBI rows) into
   real categories, and connect `ai_inferred` `pyq_questions` rows to an actual answer-key
   verification pass where possible.
2. Add one thing PLAN-007/009 didn't quite cover: Recall has no `self_notes` equivalent at all
   (no user-authored-content table) — low priority, since Recall is a single-user local tool and
   Rahul's own notes largely live in `session_user_notes`/`question_notes` already, which are a
   reasonable enough proxy; don't build a new table just to complete a category that has no real
   use case yet.

**How this feeds Area 2 directly:** once `source_type` is populated and trustworthy, Area 2's
"Full Mock" mode can report an honest official-PYQ-vs-AI-approximated split for every mock
attempt. Right now that fraction is not just unknown — one sampled third-party row was
demonstrably factually wrong (see Area 2) — so a mock's apparent realism can't be trusted until
the underlying content is honestly labeled. This is explicitly Phase 1 of the larger
cross-product taxonomy idea (see PLAN-021 for Scribe's half) — no merged database is being
proposed, just the shared vocabulary and the immediate calibration payoff.

---

## Suggested build order (Recall's items, integrated with Scribe's in PLAN-021)

See PLAN-021 for the full 7-step combined order. Recall's own sequencing within that:

1. **Area 1** (small) — do first, one sitting, before anything else is built against a stale year.
2. **Area 5** (small) — dashboard nudge, do alongside #1, near-zero cost.
3. **Area 6 Recall-half** (small) — run the already-designed PLAN-009 backfill; cheap, and a
   direct prerequisite for #4 being trustworthy.
4. **Area 2** (medium) — the core Prelims fix; sequence after #3 so the mock can honestly report
   its PYQ-vs-AI fraction from day one. Highest strategic value of Recall's four items — this is
   the direct fix for "never did a real full-length calibrated simulation," which is what UPSC
   Prelims 2026 actually punished.

No Docker work is proposed as urgent — Recall stays local/phone-only per the constraint;
Docker-verifying it for portability (mirroring Descriptive-exams' existing `Dockerfile`) is a
reasonable low-priority side task whenever convenient, not tied to the 2027 prep timeline.
