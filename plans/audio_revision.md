# Feature Plan: Audio Revision via NotebookLM Export

**Status:** Planned
**Priority:** P1
**Effort estimate:** ~9 hours across 4 phases
**Depends on:** Nothing — can start immediately. Reads from existing DB and ChromaDB only.
**Unlocks:** Passive revision during commute/exercise; audio-format engagement with highest-risk subtopics; zero-screen study time that compounds on top of quiz sessions

---

## Problem

All revision in the current system is screen-based: quizzes, notes, explanations. Rahul has
dead time (commute, exercise, household tasks) where he cannot look at a screen but CAN
listen. That time is currently wasted.

The system already has everything needed to generate personalised revision content:
- Which subtopics Rahul is weakest on (subtopic_scores)
- Which subtopics the examiner tests most (pyq_questions weight)
- The actual questions that appeared in past exams (pyq_questions table)
- What Rahul got wrong and when (session_answers)
- His study notes and source material (ChromaDB)

Without this feature, that data sits in a database and never reaches his ears.
A generic UPSC podcast covers everything — it cannot tell him "you scored 0% on
fiscal_policy_budget and here are the 6 PYQ questions on it from 2017–2024."

---

## Solution overview

The system exports structured documents. Rahul uploads them to Google NotebookLM
(notebooklm.google.com). NotebookLM generates a podcast-style Audio Overview (10-20 min,
two AI hosts, genuinely conversational). Rahul downloads and listens.

**What the system does:** assembles data from DB + ChromaDB into a well-structured
markdown document designed to prompt NotebookLM toward focused, useful audio.

**What Rahul does:** upload the file, click "Generate Audio Overview", wait ~8 minutes,
listen on phone.

**Three document types:**

| Type | When | Source data | Typical length | NotebookLM audio |
|------|------|-------------|---------------|-----------------|
| Daily priority brief | Every morning | study_plan.json + subtopic_scores + pyq_questions | ~1,500 words | 12–18 min |
| Weak topic deep-dive | On demand | ChromaDB chunks + pyq_questions + session_answers | ~2,000 words | 15–20 min |
| Subject overview | After completing all subtopics in a subject | prep_profile.json + pyq_questions + subtopic_scores | ~1,800 words | 12–18 min |

---

## Three export types

### Type 1: Daily Priority Brief

**Purpose:** Pre-study or morning commute. Hear what today's sessions cover, why those
topics matter, and which factual anchors to remember before sitting down.

**Trigger:** `--type daily` — reads today's study_plan.json + current subtopic_scores
+ pyq_questions for each planned subtopic.

**Selection logic (deterministic Python, no API call):**
1. Pull today's sessions from study_plan.json (up to 8 subtopics)
2. For each subtopic, fetch score from subtopic_scores (0 if untested)
3. Fetch PYQ count for each subtopic from pyq_questions
4. Rank by: `priority_score = pyq_count × (1 - score/100)` — high PYQ + low score = top
5. Take top 5–8 (capped by what's in today's plan)
6. For each subtopic: pull up to 3 representative PYQ questions (most recent years first)
7. Pull up to 2 ChromaDB chunks for each subtopic (highest cosine similarity to subtopic name)

**Document structure:**

```markdown
# UPSC Prelims Daily Brief — [Date]
## Today's Priority Revision: [Subject names]

> This document covers your 5 highest-priority revision topics for today.
> Each topic's weight reflects how often the UPSC examiner has tested it in real exams
> combined with your current readiness gap. Cover these before your quiz sessions.

---

## 1. [Subtopic display name] — [Subject]
**Your score:** [X]%  |  **PYQ appearances:** [N] times (2009–2025)  |  **Priority:** HIGH / CRITICAL

### Why this matters for the exam
[2–3 sentence context drawn from ChromaDB chunk: what the subtopic covers, why it recurs
in Prelims, what the examiner tends to test. Pure text extraction — no API call needed
if chunk text is high quality; optionally one Haiku call for a 2-sentence synthesis.]

### Key concepts to remember
- [Bullet point 1 — factual anchor from ChromaDB chunk]
- [Bullet point 2]
- [Bullet point 3]

### Real exam questions on this topic
**[Year] Prelims:**
Q: [question_text]
Options: (a) [option_a]  (b) [option_b]  (c) [option_c]  (d) [option_d]
Answer: [correct_answer]

**[Year] Prelims:**
Q: [question_text]
...

### What to watch out for
[1–2 sentences: common trap in this subtopic's PYQ pattern — e.g., "Examiner frequently
asks about exceptions, not the rule" or "3 of last 5 questions were statement-based."]

---

## 2. [Next subtopic] ...

[Repeat for each of the 5–8 selected subtopics]

---

## Today's Study Plan at a Glance

| Session | Subject | Subtopic | Duration | Your Score |
|---------|---------|----------|----------|------------|
| 1 | [subject] | [subtopic] | [N] min | [X]% |
...

**Total today:** [N] sessions, [X] minutes

---

## Quick-fire recall prompts
[10 rapid-fire question stubs for NotebookLM hosts to quiz each other — drawn verbatim
from PYQ options but phrased as recall challenges, not MCQs]

1. What is the composition of [X]?
2. In which year was [Y] established?
3. Name three features of [Z].
...
```

**Example populated entry:**

```markdown
## 1. Fiscal Policy and Budget — Economy
**Your score:** 0%  |  **PYQ appearances:** 14 times (2009–2025)  |  **Priority:** CRITICAL

### Why this matters for the exam
The Union Budget and fiscal policy mechanisms appear in Prelims almost every year —
typically 2–3 questions mixing direct-fact (deficit types, FRBM targets) with
statement-based questions on government borrowing and revenue classification.
You have not yet been tested on this subtopic.

### Key concepts to remember
- Fiscal deficit = Total expenditure − (Revenue receipts + Non-debt capital receipts)
- Revenue deficit = Revenue expenditure − Revenue receipts
- FRBM Act 2003 mandates elimination of revenue deficit and reduction of fiscal deficit
- Primary deficit = Fiscal deficit − Interest payments
- Capital Budget vs Revenue Budget distinction

### Real exam questions on this topic
**2023 Prelims:**
Q: With reference to the Union Budget, which of the following is/are
   included in the non-plan expenditure?
   1. Defence expenditure  2. Interest payments  3. Salaries and pensions
Options: (a) 1 only  (b) 2 and 3 only  (c) 1, 2 and 3  (d) None of the above
Answer: (c)

**2019 Prelims:**
Q: What is "Fiscal Consolidation"?
...
```

---

### Type 2: Weak Topic Deep-Dive

**Purpose:** Targeted revision of a specific subtopic where Rahul scored below 50%.
Goes deeper than the daily brief — covers concepts, what he got wrong, and all PYQs.
Best for long commutes or gym sessions.

**Trigger:** `--type weak --subtopic <subtopic_id>` (e.g. `--subtopic fiscal_policy_budget`)

**Selection logic (deterministic, zero API calls in base version):**
1. Validate subtopic_id exists in subtopic_scores with score < 50% (error if not)
2. Pull all session_answers for this subtopic (is_correct, user_answer, question_text)
3. Pull all pyq_questions for this subtopic (all years)
4. Query ChromaDB: top 5 chunks by cosine similarity to subtopic display name
5. Assemble document — optionally one Haiku call (< $0.01) to generate a 3-sentence
   "what the examiner tests" synthesis from the PYQ pattern

**Document structure:**

```markdown
# Deep Dive: [Subtopic display name]
## Subject: [Subject] | Topic: [Topic]

> Personalised revision document for [Subtopic].
> Your current score: [X]% across [N] attempts.
> This document covers: core concepts from your notes, all past exam questions on this
> topic, and what you got wrong in your quiz sessions.

---

## Your performance on this subtopic

| Session date | Questions | Correct | Score |
|---|---|---|---|
| [date] | [N] | [N] | [X]% |
| [date] | [N] | [N] | [X]% |

**Questions you got wrong:**
[List each incorrectly answered question with: question text, your answer, correct answer]

Q: [question_text]
Your answer: (b) [option you picked]
Correct answer: (a) [correct option]

Q: ...

---

## Core concepts (from your study notes)

[ChromaDB chunk 1 — full text of highest-similarity chunk]

---

[ChromaDB chunk 2 — full text of second-highest chunk]

---

[ChromaDB chunk 3...]

---

## What the UPSC examiner tests on [Subtopic]

[2–3 paragraph synthesis — either assembled from PYQ patterns or generated by one Haiku
call analysing the question list. Covers: question types used, which sub-aspects recur,
common traps, years with notable questions.]

**Question type breakdown (2009–2025):**
- Statement-based (true/false statements): [N] questions
- Direct fact recall: [N] questions
- Match the following: [N] questions
- Application/scenario: [N] questions

---

## All past exam questions on [Subtopic] — [Total N] questions (2009–2025)

### [Year]
Q: [full question text]
(a) [option_a]
(b) [option_b]
(c) [option_c]
(d) [option_d]
**Answer: [correct_answer]**

### [Year]
...

---

## Revision anchors — 5 facts you must own

[5 bullet points: the most-tested specific facts drawn from correct answers across all PYQs.
These are the literal facts that answer the most questions. Zero AI — pure extraction from
pyq_questions.correct_answer and concepts field.]

1. [Fact]
2. [Fact]
3. [Fact]
4. [Fact]
5. [Fact]

---

## Likely exam question patterns

[3–5 example question stems in the style of this subtopic's PYQ pattern — templated from
actual question structures, no generation needed. E.g., for Fiscal Policy:
"Consider the following statements about [X]: 1. ... 2. ... Which is/are correct?"]
```

---

### Type 3: Subject Overview

**Purpose:** After completing all (or most) subtopics in a subject — a synthesising listen
that consolidates everything. Good for the evening before a mock test or before moving to a
new subject.

**Trigger:** `--type subject --subject <subject_id>` (e.g. `--subject polity`)

**Selection logic:**
1. Load prep_profile.json for the subject — avg_score, coverage_pct, weak/strong subtopics,
   insight text
2. Load all subtopic_scores for the subject with score and total_attempts
3. Load all pyq_questions for the subject — group by subtopic, count per subtopic
4. Compute: `gap_score = pyq_count × (1 - score/100)` — rank subtopics by risk
5. Top 5 risk subtopics get expanded treatment; rest are summarised in a table
6. Pull 1 ChromaDB chunk per top-5 risk subtopic (quick concept recall)

**Document structure:**

```markdown
# Subject Overview: [Subject display name]
## UPSC Prelims Revision — Generated [Date]

> Comprehensive overview of your [Subject] preparation.
> Coverage: [X]% of syllabus tested  |  Average score: [X]%  |  Trend: [improving/stable/declining]
> Exam weight: approximately [N] questions per year in Prelims

---

## Where you stand

**Overall readiness:** [X]% (weighted by PYQ frequency)
**Syllabus coverage:** [X]% ([N] of [Total] subtopics tested)
**Confidence level:** [moderate/low/high]

### Score by subtopic

| Subtopic | Score | Attempts | PYQ count | Risk level |
|---------|-------|----------|-----------|------------|
| [subtopic] | [X]% | [N] | [N] | HIGH |
| [subtopic] | [X]% | [N] | [N] | MEDIUM |
...
| [subtopic — untested] | Not yet tested | 0 | [N] | UNKNOWN |

---

## Your 5 highest-risk areas

[For each of the top 5 by gap_score:]

### [Subtopic display name]
**Score:** [X]%  |  **PYQ appearances:** [N]  |  **Risk:** CRITICAL / HIGH

[ChromaDB chunk extract — 150–200 words, core concepts for this subtopic]

**PYQ snapshot — [N] questions on this topic:**
[3 most recent PYQ questions, full text + answer]

---

## What you've mastered

**Strong subtopics (score > 70%):**
[List with score and PYQ count — these are safe, mention briefly]

---

## What the examiner focuses on in [Subject]

**Top 10 most-tested subtopics by PYQ frequency (2009–2025):**

| Rank | Subtopic | Total PYQs | Your score | Gap |
|------|---------|------------|------------|-----|
| 1 | [subtopic] | [N] | [X]% | [X]% |
...

**Recurring question types in [Subject]:**
- [Pattern 1 — e.g., "Article-number identification questions appear ~4 times per year"]
- [Pattern 2]
- [Pattern 3]

---

## Last [N] sessions summary

[Table: session date, subtopic tested, score, weak subtopics flagged — from session_summaries]

---

## Gaps remaining before exam

**Untested subtopics with high PYQ weight (must cover):**
[List of untested subtopics with their PYQ count — sorted by count desc]

**Tested but still weak (score < 50%):**
[List with score + PYQ count]

**What to prioritise in final 3 days:**
[3-bullet deterministic recommendation: highest gap_score subtopics not yet at 60%]
```

---

## Data model

No new tables required. All data comes from existing tables.

One optional new table if export history is desired (Phase 4, not required for core feature):

```sql
CREATE TABLE IF NOT EXISTS audio_exports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT    NOT NULL DEFAULT 'user_1',
    export_type     TEXT    NOT NULL,   -- 'daily' | 'weak' | 'subject'
    export_key      TEXT    NOT NULL,   -- date for daily, subtopic_id for weak, subject_id for subject
    filename        TEXT    NOT NULL,
    filepath        TEXT    NOT NULL,
    word_count      INTEGER,
    subtopics_count INTEGER,
    pyq_count       INTEGER,
    generated_at    TEXT    DEFAULT (datetime('now'))
);
```

This table is purely a log — the API uses it to return a download link and let the UI show
"last generated: [date]". It does not affect scoring or planning.

---

## Export format

All documents are exported as:
1. **Primary:** `.md` (markdown) — NotebookLM accepts this via Google Docs paste or as `.txt`
2. **Secondary:** `.txt` with identical content — for direct NotebookLM upload

Filename conventions:
- `audio_brief_2026-05-12.md`
- `audio_deep_dive_fiscal_policy_budget_2026-05-12.md`
- `audio_subject_polity_2026-05-12.md`

Output directory: `exports/audio/` (created automatically, gitignored).

NotebookLM works best with documents that:
- Have clear headers (the hosts use them as topic transitions)
- Mix factual content with questions (hosts quiz each other)
- Have explicit "why this matters" framing (hosts focus their discussion)
- Are 1,000–3,000 words (optimal for 10–20 min audio)

The document structures above are designed specifically for this pattern.

---

## Script design — `scripts/generate_audio_brief.py`

```python
#!/usr/bin/env python3
"""
Generate personalised audio revision documents for NotebookLM upload.

Usage:
  python generate_audio_brief.py --type daily
  python generate_audio_brief.py --type weak --subtopic fiscal_policy_budget
  python generate_audio_brief.py --type subject --subject polity
  python generate_audio_brief.py --type weak --subtopic election_commission --no-llm
"""
```

### CLI flags

| Flag | Required | Values | Description |
|------|----------|--------|-------------|
| `--type` | Yes | `daily`, `weak`, `subject` | Which document type to generate |
| `--subtopic` | If `--type weak` | any subtopic_id | Target subtopic for deep-dive |
| `--subject` | If `--type subject` | any subject_id | Target subject for overview |
| `--no-llm` | No (default: False) | flag | Skip all Claude API calls — pure DB + ChromaDB assembly only |
| `--output` | No | path | Override output directory (default: `exports/audio/`) |
| `--open` | No | flag | Open the generated file in default text editor after creation |
| `--date` | No | YYYY-MM-DD | For daily brief: override date (default: today) |

### Internal module structure

```
generate_audio_brief.py
  main()
    → parse_args()
    → if type == 'daily':   DailyBriefBuilder(db, chroma, plan).build()
    → if type == 'weak':    WeakTopicBuilder(db, chroma, subtopic_id).build()
    → if type == 'subject': SubjectOverviewBuilder(db, chroma, subject_id).build()
    → write_output(content, filename, output_dir)
    → print success + file path

class DailyBriefBuilder:
    - load_today_plan()            ← study_plan.json
    - load_subtopic_scores()       ← subtopic_scores table
    - fetch_pyqs(subtopic_id)      ← pyq_questions table
    - fetch_chroma_chunks(subtopic_id, n=2)   ← ChromaDB query
    - rank_by_priority()           ← pyq_count × (1 - score/100), deterministic
    - maybe_llm_synthesis(chunk_texts)  ← Haiku only if --no-llm not set
    - render_document()            ← fills markdown template

class WeakTopicBuilder:
    - validate_subtopic(subtopic_id)   ← must exist in subtopic_scores with score < 50
    - load_session_answers(subtopic_id) ← session_answers table, wrong answers only
    - load_all_pyqs(subtopic_id)       ← pyq_questions, all years
    - fetch_chroma_chunks(subtopic_id, n=5)
    - maybe_llm_examiner_synthesis()   ← one Haiku call for "what examiner tests"
    - render_document()

class SubjectOverviewBuilder:
    - load_subject_profile(subject_id) ← prep_profile.json
    - load_all_subtopic_scores(subject_id) ← subtopic_scores table
    - load_pyq_distribution(subject_id)    ← COUNT(*) GROUP BY subtopic_id
    - compute_gap_scores()             ← pyq_count × (1 - score/100), deterministic
    - load_session_history(subject_id) ← session_summaries table, last 10
    - fetch_chroma_chunks()            ← top 5 risk subtopics only, 1 chunk each
    - render_document()
```

### Cost per export

| Document type | Claude calls | Model | Tokens (est.) | Cost |
|---|---|---|---|---|
| Daily brief (with LLM) | 1 × synthesis | Haiku | ~800 in / 200 out | ~$0.001 |
| Daily brief (--no-llm) | 0 | — | — | $0.00 |
| Weak topic (with LLM) | 1 × examiner synthesis | Haiku | ~1,200 in / 300 out | ~$0.002 |
| Weak topic (--no-llm) | 0 | — | — | $0.00 |
| Subject overview | 0 | — | — | $0.00 |

Default is `--no-llm` OFF (LLM enabled). For exam crunch days, user can pass `--no-llm`
to generate instantly with zero cost. The LLM synthesis step is purely additive quality —
the document is fully useful without it.

---

## API endpoint

### POST `/audio/generate`

Triggers document generation from the backend and returns a download link.
Used by the UI buttons. Runs the same logic as the CLI script.

**Request:**
```json
{
  "type": "daily",
  "subtopic_id": null,
  "subject_id": null,
  "no_llm": false
}
```

For weak topic:
```json
{
  "type": "weak",
  "subtopic_id": "fiscal_policy_budget",
  "subject_id": null,
  "no_llm": false
}
```

For subject overview:
```json
{
  "type": "subject",
  "subtopic_id": null,
  "subject_id": "polity",
  "no_llm": false
}
```

**Response (202 Accepted — generation is synchronous but may take 2–5 sec):**
```json
{
  "status": "ok",
  "filename": "audio_brief_2026-05-12.md",
  "download_url": "/audio/download/audio_brief_2026-05-12.md",
  "word_count": 1842,
  "subtopics_count": 6,
  "pyq_count": 31,
  "generated_at": "2026-05-12T07:34:01Z"
}
```

**Error response (400):**
```json
{
  "status": "error",
  "code": "subtopic_score_above_threshold",
  "message": "election_commission has score 72% — only subtopics below 50% qualify for deep-dive. Use --force to override."
}
```

### GET `/audio/download/<filename>`

Streams the file as `text/markdown` with Content-Disposition header for browser download.

### GET `/audio/history`

Returns the last 10 exports from the `audio_exports` table (if Phase 4 is built):
```json
{
  "exports": [
    {
      "export_type": "daily",
      "export_key": "2026-05-12",
      "filename": "audio_brief_2026-05-12.md",
      "download_url": "/audio/download/audio_brief_2026-05-12.md",
      "word_count": 1842,
      "generated_at": "2026-05-12T07:34:01Z"
    }
  ]
}
```

---

## UI integration

### Dashboard page (`web/src/app/page.tsx`)

Add a new "Audio Revision" card in the quick-action section alongside existing
"Start Session" and "Sync & Plan" buttons:

```
┌─────────────────────────────────────────────┐
│  Audio Revision                             │
│                                             │
│  [ Generate Today's Brief ]                 │
│                                             │
│  Last generated: May 12, 7:34am             │
│  audio_brief_2026-05-12.md  [Download]      │
└─────────────────────────────────────────────┘
```

"Generate Today's Brief" → calls `POST /audio/generate` with `type: "daily"` →
shows a spinner (generation takes 2–5 sec) → on success, shows download link.

### Tracker page (`web/src/app/tracker/page.tsx`)

Add a "Generate Audio" button on each subject card and each weak subtopic row:

**Subject card (existing):**
```
Polity — 38.8%  [████░░░░░░]
[Start session]  [Generate Audio Overview]
```

"Generate Audio Overview" → calls `POST /audio/generate` with `type: "subject"` and
`subject_id: "polity"` → spinner → download link appears inline.

**Weak subtopics list (existing gaps section):**
```
Gaps  (5 weak subtopics)

  fiscal_policy_budget     0%     14 PYQs   [Deep-Dive Audio]
  digital_payments_fintech 0%     9 PYQs    [Deep-Dive Audio]
  election_commission      34%    11 PYQs   [Deep-Dive Audio]
```

"Deep-Dive Audio" → calls `POST /audio/generate` with `type: "weak"` and the subtopic_id.

### UI state

- Button shows spinner while generating
- On success: button text changes to "Download" and the link opens the file
- On error: shows toast with error message (e.g., "Score too high for deep-dive")
- No full-page reload needed — all state local to the button component

---

## Implementation phases

### Phase 1 — Core script + daily brief · ~2.5 hrs

Build the script foundation and the daily brief export. This phase alone delivers the
highest-value use case (morning commute brief).

**Files to create:**
- `scripts/generate_audio_brief.py` — main script with `DailyBriefBuilder` class
- `exports/audio/.gitkeep` — create the output directory (gitignore the contents)
- `prompts/audio_synthesis.txt` — Haiku prompt for the optional synthesis step

**What DailyBriefBuilder does:**
1. Reads study_plan.json
2. Queries subtopic_scores for each planned subtopic
3. Queries pyq_questions for each subtopic (SELECT * WHERE subtopic_id = ?)
4. Queries ChromaDB: `collection.query(query_texts=[subtopic_display_name], n_results=2)`
5. Computes priority rank: `pyq_count × (1 - score/100)`
6. Optionally calls Haiku with `prompts/audio_synthesis.txt` for "why this matters" section
7. Renders the markdown template and writes to `exports/audio/`

**Test:** Run `python generate_audio_brief.py --type daily --no-llm` and verify
a readable, well-structured markdown file in `exports/audio/`.

### Phase 2 — Weak topic deep-dive · ~2 hrs

Build `WeakTopicBuilder`. More complex because it joins session_answers.

**Additions:**
- `WeakTopicBuilder` class in `generate_audio_brief.py`
- Query: `SELECT question_text, user_answer, correct_answer FROM session_answers WHERE subtopic_id = ? AND is_correct = 0`
- Query: `SELECT * FROM pyq_questions WHERE subtopic_id = ? ORDER BY year DESC`
- ChromaDB query with `where={"subject_id": subject_id}` filter + subtopic text query

**Test:** Run `python generate_audio_brief.py --type weak --subtopic fiscal_policy_budget`
and verify the "questions you got wrong" section lists real wrong answers.

### Phase 3 — Subject overview + API endpoint · ~2.5 hrs

Build `SubjectOverviewBuilder` and wire up the FastAPI routes.

**Files to create/modify:**
- `backend/routes/audio.py` — new route file with POST /audio/generate, GET /audio/download,
  GET /audio/history
- `backend/server.py` — add `from routes import audio; app.include_router(audio.router)`
- Update `generate_audio_brief.py` to add `SubjectOverviewBuilder`

**SubjectOverviewBuilder data sources:**
- prep_profile.json → subject object
- `SELECT subtopic_id, score, total_attempts FROM subtopic_scores WHERE subject_id = ?`
- `SELECT subtopic_id, COUNT(*) as pyq_count FROM pyq_questions WHERE subject_id = ? GROUP BY subtopic_id`
- `SELECT * FROM session_summaries WHERE subject_id = ? ORDER BY session_date DESC LIMIT 10`

**Test:** Call `POST /audio/generate` with curl, verify file is created and
`/audio/download/<filename>` returns the file.

### Phase 4 — UI integration + export log table · ~2 hrs

Add buttons to dashboard and tracker pages. Optionally add the `audio_exports` table
for history tracking.

**Files to modify:**
- `web/src/app/page.tsx` — add Audio Revision quick-action card
- `web/src/app/tracker/page.tsx` — add Generate buttons to subject cards + weak subtopic rows
- `scripts/db_init.py` — add `audio_exports` table (CREATE TABLE IF NOT EXISTS — no migration needed)

**UI component:** `AudioGenerateButton` — reusable button that:
1. Accepts `type`, `subtopicId`, `subjectId` props
2. POSTs to `/audio/generate`
3. Shows spinner during generation
4. Renders download link on success
5. Shows error toast on failure

**Test:** Click "Generate Today's Brief" on dashboard, verify download link appears,
open file and confirm it's readable.

---

## NotebookLM workflow

Step-by-step for Rahul:

1. **Generate** — from the dashboard or tracker, click the relevant button and wait ~5 sec
2. **Download** — click the download link; the `.md` file saves to Downloads/
3. **Open NotebookLM** — go to notebooklm.google.com (bookmarked on phone/laptop)
4. **Create or open a notebook** — use one notebook per document type or one shared notebook.
   For exam prep: keep one "Daily Briefs" notebook and one "Deep Dives" notebook.
5. **Upload** — click "+ Source" → "Upload file" → select the downloaded `.md` file.
   NotebookLM accepts `.md` files directly.
6. **Generate Audio Overview** — once the source loads (~30 sec), click "Audio Overview" in
   the right panel. NotebookLM starts generating (takes ~5–10 min, runs in background).
7. **Download the audio** — click the three-dot menu on the Audio Overview card → "Download".
   The file downloads as `.wav` or `.mp3` to your phone/laptop.
8. **Listen** — AirPods in, go for a walk. The two AI hosts will discuss your specific topics,
   quiz each other on the PYQ questions you included, and focus on your weak areas because
   that's what the document leads with.

**Optimal timing:**
- Daily brief: generate at night after Sync & Plan, listen next morning commute
- Weak topic: generate after a quiz session where you scored < 40%, listen same evening
- Subject overview: generate after completing all subtopics in a subject, listen next morning

**One notebook tip:** Keep all deep-dive docs in a single "Weak Topics" notebook.
NotebookLM's Audio Overview synthesises across ALL sources in the notebook — so adding
3 weak topic documents creates one audio that covers all 3. More efficient than separate
notebooks per subtopic.

---

## Cost summary

| Phase | Claude usage | Cost per run | Monthly (30 runs) |
|---|---|---|---|
| Daily brief with synthesis | 1 × Haiku | ~$0.001 | ~$0.03 |
| Daily brief --no-llm | None | $0.00 | $0.00 |
| Weak topic with synthesis | 1 × Haiku | ~$0.002 | ~$0.06 |
| Subject overview | None | $0.00 | $0.00 |
| NotebookLM audio generation | Google (free) | $0.00 | $0.00 |

Total for 10-day sprint (worst case, all with LLM enabled): **< $0.10**

Document assembly (DB queries, ChromaDB lookups, template rendering) is entirely free.
The optional Haiku synthesis step can always be disabled with `--no-llm`.

---

## Scalability notes

- `audio_exports` table is append-only and tiny — one row per export, no joins
- ChromaDB queries use existing indexes — no new collections or metadata fields needed
- The script imports the existing `priority_scorer.py` for PYQ weights — no duplication
- All three document types follow the same render pipeline — adding a 4th type
  (e.g., "mock test preview") is a new Builder class only, no changes to shared code
- `user_id` is on every `audio_exports` row — multi-user extension is one WHERE clause
