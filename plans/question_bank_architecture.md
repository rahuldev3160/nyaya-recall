# Question Bank Architecture — Nyaya Recall
_Created: 2026-06-15_

## Why This Exists

Calling AI per user query is: expensive (~$0.001/question), slow (2–4s latency), unreliable
(hallucinations in MCQ options), and impossible to deduplicate across users. A pre-built,
richly indexed question bank eliminates all four problems. AI generation is a last-resort
fallback only — triggered server-side when a subtopic has < 5 questions left for a user.

**Target bank size:** ~8,000–10,000 questions at launch.
**AI generation fallback:** < 5% of questions served should be AI-generated.

---

## Data Sources

### Tier 1 — UPSC Civil Services (highest relevance, already partially ingested)
| Source | Questions | Status |
|--------|-----------|--------|
| CS GS Paper I PYQs 2009–2025 | ~1,600 | Partially in DB (~1,300). Needs 2009–2012 + answer key import. |
| CS GS Paper II (CSAT) 2011–2025 | ~1,200 | Separate system — ingest after Tier 1 complete |

### Tier 2 — Cross-UPSC Exams (official answer keys, zero cost)
| Source | Questions | Notes |
|--------|-----------|-------|
| CDS GK Paper (10 yr × 2/yr × ~120q) | ~2,400 | Subject overlap: polity, geography, history, science |
| NDA GAT GK sections (10 yr × 2/yr × ~75q) | ~1,500 | Heavy on science, geography |
| CAPF Paper I (10 yr × 125q) | ~1,250 | Strong on current affairs, environment |
| CISF AC GK (10 yr × ~100q) | ~1,000 | Mix of all subjects |
| **Tier 2 total** | **~6,150** | All have official answer keys on upsc.gov.in |

### Tier 3 — State PSC (lower UPSC relevance, broader reach)
| Source | Questions | Notes |
|--------|-----------|-------|
| RAS/RPSC PYQs 2015–2024 | ~800 | High priority — Rahul's target exam Nov 2026 |
| BPSC PYQs 2015–2024 | ~500 | Bihar PSC, high aspirant count |
| UPPSC PYQs 2015–2024 | ~500 | Largest state PSC aspirant pool |
| **Tier 3 total** | **~1,800** | Lower priority, add post-launch |

### Tier 4 — AI Gap-Fill (last resort)
- Only for subtopics with < 5 questions across Tier 1+2+3
- One-time Haiku Batch generation (~₹75 total, ~800 questions)
- Tagged `answer_source = 'ai_generated'` — never shown without human review flag

**Grand total at launch:** ~8,000–9,000 questions (Tier 1+2+AI gap-fill)

---

## Schema Design

### Primary table: `question_bank`

```sql
CREATE TABLE question_bank (
  id                  TEXT PRIMARY KEY,        -- UUID v4
  question_hash       TEXT UNIQUE NOT NULL,    -- SHA256(question_text) first 32 chars

  -- Content
  question_text       TEXT NOT NULL,
  option_a            TEXT NOT NULL,
  option_b            TEXT NOT NULL,
  option_c            TEXT NOT NULL,
  option_d            TEXT NOT NULL,
  correct_answer      TEXT NOT NULL,           -- 'A' | 'B' | 'C' | 'D'
  explanation_short   TEXT,                   -- 1-sentence (free tier)
  explanation_full    TEXT,                   -- full Pro analysis (concept + wrong options + hook)

  -- Source & provenance
  exam_source         TEXT NOT NULL,           -- 'upsc_cse' | 'upsc_cds' | 'upsc_nda' | 'upsc_capf' | 'ras' | 'bpsc' | 'ai_generated'
  year                INTEGER,
  paper               TEXT,                   -- 'GS1' | 'GS2' | 'Paper_I' | 'GAT'
  q_number            INTEGER,                -- original question number in paper
  answer_source       TEXT NOT NULL,           -- 'upsc_official_key' | 'community_validated' | 'ai_inferred'
  answer_disputed     INTEGER DEFAULT 0,
  dispute_note        TEXT,
  cancelled           INTEGER DEFAULT 0,       -- UPSC cancels some questions

  -- Taxonomy (canonical — from syllabus.json)
  subject_id          TEXT NOT NULL,           -- 'polity' | 'economy' | 'geography' | ...
  topic_id            TEXT NOT NULL,
  subtopic_id         TEXT NOT NULL,
  dimension_id        TEXT,                   -- which testable dimension within subtopic
  question_type       TEXT,                   -- 'statement_based' | 'single_fact' | 'match_following' | 'map_based' | 'analytical'
  upsc_relevance      REAL DEFAULT 1.0,       -- PYQ weight if CS PYQ; else 0.3–0.8 by exam tier

  -- Cross-cutting tags
  tags                TEXT,                   -- JSON array: ['environment', 'constitutional', 'current_affairs_link']
  is_evergreen        INTEGER DEFAULT 1,       -- 0 = time-sensitive (current affairs), expires
  expires_after_year  INTEGER,                -- for current affairs questions

  -- Aggregate stats (updated on serve)
  times_served        INTEGER DEFAULT 0,
  times_correct       INTEGER DEFAULT 0,
  global_accuracy     REAL,                   -- times_correct / times_served, updated async

  created_at          TEXT DEFAULT (datetime('now'))
);
```

### Per-user relationship table: `user_question_log`

```sql
CREATE TABLE user_question_log (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id             TEXT NOT NULL,
  question_id         TEXT NOT NULL,           -- FK → question_bank.id

  -- Session context
  session_id          TEXT,                   -- FK → quiz_sessions.id (nullable for standalone)
  exam_context        TEXT,                   -- 'adaptive' | 'diagnostic' | 'pyq_browser' | 'simulation' | 'daily_challenge'

  -- Answer data
  user_answer         TEXT,                   -- 'A'|'B'|'C'|'D'|null (skipped)
  is_correct          INTEGER,                -- 0|1|null
  confidence          TEXT,                   -- 'sure'|'unsure'|'guess'
  time_taken_sec      INTEGER,
  skipped             INTEGER DEFAULT 0,

  -- Spaced repetition scheduling
  interval_days       INTEGER DEFAULT 1,       -- current SRS interval
  ease_factor         REAL DEFAULT 2.5,        -- SM-2 ease factor
  next_review_at      TEXT,                   -- ISO datetime for next due
  repetition_count    INTEGER DEFAULT 0,

  answered_at         TEXT DEFAULT (datetime('now')),

  UNIQUE(user_id, question_id, answered_at)   -- allows re-attempts; latest drives SRS
);
```

### Streak config table: `streak_config`

```sql
CREATE TABLE streak_config (
  user_id             TEXT PRIMARY KEY,
  shield_enabled      INTEGER DEFAULT 1,       -- 0 = strict mode
  max_grace_per_week  INTEGER DEFAULT 1,       -- user-adjustable: 0, 1, or 2
  grace_used_this_week INTEGER DEFAULT 0,
  week_start_date     TEXT,                   -- ISO date of Monday that started current week
  current_streak      INTEGER DEFAULT 0,
  longest_streak      INTEGER DEFAULT 0,
  last_activity_date  TEXT,                   -- ISO date of last drill session
  updated_at          TEXT DEFAULT (datetime('now'))
);
```

### Daily challenge table: `daily_challenge`

```sql
CREATE TABLE daily_challenge (
  challenge_date      TEXT PRIMARY KEY,        -- ISO date 'YYYY-MM-DD'
  question_ids        TEXT NOT NULL,           -- JSON array of 10 question_ids (same for all users)
  subject_focus       TEXT,                   -- which subject today's set emphasises
  generated_at        TEXT DEFAULT (datetime('now'))
);
```

### Username table (extends user_profiles):

```sql
ALTER TABLE user_profiles ADD COLUMN username TEXT UNIQUE;
ALTER TABLE user_profiles ADD COLUMN username_locked_until TEXT; -- can change once per 30 days
```

---

## Indexing Strategy

```sql
-- Serving indexes (hot path — every question fetch hits these)
CREATE INDEX idx_qb_subtopic_serve
  ON question_bank(subject_id, subtopic_id, times_served, cancelled);

CREATE INDEX idx_qb_subtopic_type
  ON question_bank(subject_id, subtopic_id, question_type, upsc_relevance);

CREATE INDEX idx_qb_exam_year
  ON question_bank(exam_source, year, subject_id);

CREATE INDEX idx_qb_topic
  ON question_bank(subject_id, topic_id, subtopic_id);

CREATE INDEX idx_qb_relevance
  ON question_bank(subject_id, upsc_relevance DESC);

CREATE INDEX idx_qb_evergreen
  ON question_bank(is_evergreen, expires_after_year);

-- User history indexes (every "not seen" query hits these)
CREATE INDEX idx_uql_user_question
  ON user_question_log(user_id, question_id);

CREATE INDEX idx_uql_user_subject
  ON user_question_log(user_id, session_id);

CREATE INDEX idx_uql_due_review
  ON user_question_log(user_id, next_review_at)
  WHERE is_correct IS NOT NULL;

CREATE INDEX idx_uql_wrong_confidence
  ON user_question_log(user_id, is_correct, confidence)
  WHERE is_correct = 0 AND confidence = 'sure';
```

---

## Pre-Planned Query Patterns

These are the ~12 common queries the serving layer runs. All pure SQL, zero AI calls.
Each is a named function in `backend/routes/questions.py`.

### QP-1: Adaptive Diagnostic
_"Give me questions on subtopics I haven't tested, sorted by UPSC importance"_
```sql
SELECT qb.* FROM question_bank qb
WHERE qb.subject_id = :subject_id
  AND qb.subtopic_id NOT IN (
    SELECT DISTINCT subtopic_id FROM user_question_log WHERE user_id = :user_id
  )
  AND qb.cancelled = 0
  AND qb.answer_source != 'ai_inferred'
ORDER BY qb.upsc_relevance DESC, qb.times_served ASC
LIMIT :limit;
```

### QP-2: Daily Adaptive Drill
_"Give me questions on my weak subtopics, not seen in last 30 days"_
```sql
SELECT qb.* FROM question_bank qb
JOIN (
  SELECT subtopic_id, AVG(is_correct) as score
  FROM user_question_log WHERE user_id = :user_id GROUP BY subtopic_id
) scores ON qb.subtopic_id = scores.subtopic_id
WHERE qb.subject_id = :subject_id
  AND scores.score < 0.7
  AND qb.id NOT IN (
    SELECT question_id FROM user_question_log
    WHERE user_id = :user_id AND answered_at > datetime('now', '-30 days')
  )
  AND qb.cancelled = 0
ORDER BY scores.score ASC, qb.upsc_relevance DESC
LIMIT :limit;
```

### QP-3: Spaced Repetition Due
_"Questions I got wrong earlier, now due for review"_
```sql
SELECT qb.*, uql.ease_factor, uql.repetition_count
FROM user_question_log uql
JOIN question_bank qb ON qb.id = uql.question_id
WHERE uql.user_id = :user_id
  AND uql.next_review_at <= datetime('now')
  AND uql.is_correct = 0
  AND qb.cancelled = 0
ORDER BY uql.next_review_at ASC
LIMIT :limit;
```

### QP-4: PYQ Browser (year + subject drill)
_"All questions from UPSC CSE 2019 Polity"_
```sql
SELECT * FROM question_bank
WHERE exam_source = 'upsc_cse'
  AND year = :year
  AND subject_id = :subject_id
  AND cancelled = 0
ORDER BY q_number ASC;
```

### QP-5: Exam Simulation
_"100 UPSC-style questions across subjects in exam distribution"_
```sql
-- Called per subject with exam-distribution weights
-- Polity: 20q, Economy: 18q, Geography: 15q, History+Culture: 20q, etc.
SELECT * FROM question_bank
WHERE subject_id = :subject_id
  AND exam_source IN ('upsc_cse', 'upsc_cds', 'upsc_nda', 'upsc_capf')
  AND id NOT IN (
    SELECT question_id FROM user_question_log WHERE user_id = :user_id
  )
  AND cancelled = 0
ORDER BY upsc_relevance DESC, RANDOM()
LIMIT :subject_quota;
```

### QP-6: Subtopic Deep Dive
_"All questions on Preamble, sorted by difficulty"_
```sql
SELECT qb.*, COALESCE(uql.is_correct, -1) as user_status
FROM question_bank qb
LEFT JOIN (
  SELECT question_id, is_correct
  FROM user_question_log
  WHERE user_id = :user_id
  ORDER BY answered_at DESC -- latest attempt
) uql ON qb.id = uql.question_id
WHERE qb.subtopic_id = :subtopic_id
  AND qb.cancelled = 0
ORDER BY qb.upsc_relevance DESC, global_accuracy ASC;  -- hardest first
```

### QP-7: Follow-up on Wrong Answer
_"Show more questions testing the same concept I just got wrong"_
```sql
SELECT * FROM question_bank
WHERE subtopic_id = :subtopic_id
  AND dimension_id = :dimension_id
  AND id != :just_answered_id
  AND id NOT IN (
    SELECT question_id FROM user_question_log
    WHERE user_id = :user_id AND answered_at > datetime('now', '-7 days')
  )
  AND cancelled = 0
ORDER BY exam_source = 'upsc_cse' DESC, upsc_relevance DESC
LIMIT 5;
```

### QP-8: Overconfidence Drill
_"Questions I said 'Sure' but got wrong — my dangerous blind spots"_
```sql
SELECT qb.*, uql.answered_at, uql.user_answer
FROM user_question_log uql
JOIN question_bank qb ON qb.id = uql.question_id
WHERE uql.user_id = :user_id
  AND uql.confidence = 'sure'
  AND uql.is_correct = 0
  AND uql.answered_at > datetime('now', '-30 days')
  AND qb.cancelled = 0
ORDER BY uql.answered_at DESC
LIMIT 20;
```

### QP-9: Daily Leaderboard Challenge
_"Same 10 questions for all users today"_
```sql
-- Reading side: just fetch from daily_challenge table
SELECT qb.* FROM question_bank qb
JOIN json_each((
  SELECT question_ids FROM daily_challenge WHERE challenge_date = date('now')
)) j ON qb.id = j.value;

-- Generation side (runs once daily at midnight via cron):
-- SELECT id FROM question_bank
-- WHERE upsc_relevance > 0.5 AND cancelled = 0 AND answer_source != 'ai_inferred'
-- ORDER BY RANDOM() LIMIT 10;
```

### QP-10: Cross-Exam Discovery
_"Show all times this concept appeared across different exams"_
```sql
SELECT exam_source, year, q_number, question_text, correct_answer
FROM question_bank
WHERE subtopic_id = :subtopic_id
  AND cancelled = 0
ORDER BY upsc_relevance DESC, year DESC;
```

### QP-11: Question Bank Coverage Audit
_"Which subtopics have < 5 questions? Trigger AI gap-fill."_
```sql
SELECT s.subtopic_id, s.subject_id, COUNT(qb.id) as question_count
FROM syllabus_subtopics s
LEFT JOIN question_bank qb ON qb.subtopic_id = s.subtopic_id AND qb.cancelled = 0
GROUP BY s.subtopic_id
HAVING COUNT(qb.id) < 5
ORDER BY s.upsc_weight DESC;
```

### QP-12: Unseen Questions Count (for due badge)
_"How many questions are due today for the user?"_
```sql
SELECT COUNT(*) FROM (
  -- Spaced repetition reviews due
  SELECT question_id FROM user_question_log
  WHERE user_id = :user_id AND next_review_at <= datetime('now')
  UNION ALL
  -- Untested high-priority subtopics (estimated 10 per subtopic × count)
  SELECT id FROM question_bank
  WHERE subtopic_id IN (
    SELECT subtopic_id FROM high_priority_untested_view WHERE user_id = :user_id
  )
  LIMIT 30
) due;
```

---

## Spaced Repetition Algorithm (SM-2 simplified)

When a user answers a question, `backend/services/srs.py` updates `user_question_log`:

```python
def update_srs(log_row: dict, is_correct: bool, confidence: str) -> dict:
    """SM-2 simplified with confidence modifier."""
    q = 5 if (is_correct and confidence == 'sure') else \
        4 if (is_correct and confidence == 'unsure') else \
        3 if (is_correct and confidence == 'guess') else \
        2 if (not is_correct and confidence == 'sure') else \    # overconfidence penalty
        1 if (not is_correct and confidence == 'unsure') else 0

    ease = max(1.3, log_row['ease_factor'] + 0.1 - (5 - q) * 0.08)
    n = log_row['repetition_count']

    if q < 3:  # got it wrong
        interval = 1  # review tomorrow
        n = 0
    elif n == 0:
        interval = 1
    elif n == 1:
        interval = 6
    else:
        interval = round(log_row['interval_days'] * ease)

    return {
        'interval_days': interval,
        'ease_factor': ease,
        'repetition_count': n + 1,
        'next_review_at': datetime.utcnow() + timedelta(days=interval)
    }
```

**Key modifier:** `sure + wrong` sets q=2 (harsh), meaning the interval resets to 1 day and ease factor drops. This surfaces overconfident wrong answers more aggressively than regular wrong answers.

---

## Streak Shield Logic

```python
# backend/services/streak.py

def record_activity(user_id: str, db) -> dict:
    """Call once per session completion."""
    config = db.get_streak_config(user_id)
    today = date.today().isoformat()

    # Reset weekly grace counter on Monday
    week_monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    if config['week_start_date'] != week_monday:
        config['grace_used_this_week'] = 0
        config['week_start_date'] = week_monday

    last = config['last_activity_date']
    if last == today:
        return config  # already studied today, no change

    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if last == yesterday:
        # Consecutive day — extend streak
        config['current_streak'] += 1
    elif config['shield_enabled'] and config['grace_used_this_week'] < config['max_grace_per_week']:
        # Missed a day but shield absorbs it
        config['grace_used_this_week'] += 1
        config['current_streak'] += 1  # streak continues
    else:
        # Streak broken
        config['longest_streak'] = max(config['longest_streak'], config['current_streak'])
        config['current_streak'] = 1  # restart

    config['last_activity_date'] = today
    config['longest_streak'] = max(config['longest_streak'], config['current_streak'])
    db.update_streak_config(user_id, config)
    return config
```

**User-facing settings (Profile → Accountability):**
```
Streak Shield
─────────────────────────────
○ Strict mode     — no misses allowed
● 1 miss/week     — recommended for most
○ 2 misses/week   — for busy schedules

"Shield resets every Monday morning."
```

---

## Username Generation

```python
# backend/services/username.py

ADJECTIVES = [
    "Swift", "Bold", "Sharp", "Deep", "Clear", "Calm", "Keen",
    "Bright", "Quick", "Solid", "Wise", "Firm", "Steady", "Just"
]

UPSC_TERMS = [
    "Polity", "Economy", "History", "Geography", "Science", "Enviro",
    "Ethics", "Mains", "Prelims", "Aspirant", "Scholar", "Recall"
]

def generate_username() -> str:
    adj = random.choice(ADJECTIVES)
    term = random.choice(UPSC_TERMS)
    num = random.randint(10, 99)
    return f"{adj}{term}_{num:02d}"   # e.g. "BoldPolity_07"

def is_available(username: str, db) -> bool:
    return db.query("SELECT 1 FROM user_profiles WHERE username = ?", [username]) is None
```

Onboarding generates 3 options, user picks one or skips (auto-assigned). Editable in Profile, max 1 change per 30 days (`username_locked_until`).

---

## Ingestion Pipeline

### Phase A — CS PYQs (already started)
- Complete 2009–2012 ingestion (missing years)
- Run `scripts/import_answer_keys.py` after Rahul downloads official PDFs
- Target: ~1,600 questions, all with `answer_source = 'upsc_official_key'`

### Phase B — Cross-UPSC (CDS/NDA/CAPF/CISF)
New script: `scripts/ingest_cross_exam.py`
- Input: PDF or structured CSV per exam per year
- Extracts: question_text, options, correct_answer from answer key
- Classifies to subject/topic/subtopic using Haiku batch (~₹50 one-time for 6,000 questions)
- Sets `upsc_relevance` based on exam tier (CDS=0.6, NDA=0.5, CAPF=0.55, CISF=0.45)
- Deduplicates by `question_hash` before insert

### Phase C — AI Gap-Fill
Run `scripts/audit_qb_coverage.py` → identify subtopics with < 5 questions → trigger Haiku batch
- One-time cost: ~₹75
- Tagged `answer_source = 'ai_generated'`, shown with "AI-generated" badge to users

### Phase D — RAS/State PSC (post-launch)
- Same pipeline as Phase B, lower priority
- Higher `upsc_relevance` for RAS than BPSC/UPPSC if user has set exam = 'ras'

---

## Daily Challenge Generation (Cron)

Runs at 00:01 IST every day via Railway Cron:

```python
# scripts/generate_daily_challenge.py
def generate():
    """Pick 10 questions for today's leaderboard challenge."""
    today = date.today().isoformat()

    # Requirements:
    # - Mix of subjects (≥3 different subjects)
    # - At least 3 CS PYQs (upsc_cse source)
    # - No question used in last 30 days
    # - All answer_source != 'ai_generated'
    # - global_accuracy between 0.3–0.7 (not too easy, not too hard)

    questions = db.query("""
        SELECT id, subject_id FROM question_bank
        WHERE cancelled = 0
          AND answer_source != 'ai_generated'
          AND global_accuracy BETWEEN 0.3 AND 0.7
          AND id NOT IN (
            SELECT json_each.value FROM daily_challenge, json_each(question_ids)
            WHERE challenge_date > date('now', '-30 days')
          )
        ORDER BY exam_source = 'upsc_cse' DESC, RANDOM()
        LIMIT 50
    """)

    # Enforce subject diversity
    selected = pick_diverse(questions, count=10, min_subjects=3)
    db.upsert_daily_challenge(today, [q['id'] for q in selected])
```

---

## Serving Layer — Question Priority Waterfall

`backend/services/question_server.py` — called by every quiz generation endpoint.

```
Request: user_id + context (diagnostic|drill|simulation|pyq|challenge)
         + subject_id + subtopic_ids[] + count

Priority waterfall (pure SQL, checked in order):
┌─────────────────────────────────────────────────────┐
│ 1. Spaced repetition reviews due          (QP-3)    │  ← overdue = highest priority
│ 2. CS PYQs user hasn't seen              (QP-1)    │  ← highest relevance
│ 3. Cross-exam (CDS/NDA/CAPF) not seen   (QP-2)    │  ← medium relevance
│ 4. Questions seen > 30 days ago, weak   (QP-2)    │  ← re-test
│ 5. AI-generated questions               (fallback) │  ← only when bank < 5 for subtopic
└─────────────────────────────────────────────────────┘

After each waterfall step: check if count filled.
If yes: return. If no: proceed to next step.

Result: questions[] with source tagged so UI can show
"UPSC 2021" or "CDS 2019" badge on each question.
```

---

## Question Card UI Additions (from this architecture)

Each question card gains:
```
┌────────────────────────────────────┐
│  UPSC CSE 2019 · Polity · Q.47     │  ← source badge
│  🔁 Due for review                 │  ← if SRS-triggered
│                                    │
│  [question text]                   │
│                                    │
│  [Sure] [Unsure] [Guessing]        │
│                                    │
│  A ...                             │
│  B ...  ← selected                 │
│  C ...                             │
│  D ...                             │
│                                    │
│  [Submit →]                        │
└────────────────────────────────────┘
```

After answer reveal, cross-exam discovery (Pro):
```
│  This concept also appeared in:    │
│  • CDS 2022 (Q.31)                 │
│  • NDA 2021 (Q.18)                 │
│  • CAPF 2020 (Q.55)                │
```

---

## Implementation Sequence

| Phase | Task | Sprint | Blocker |
|-------|------|--------|---------|
| 1 | Schema: `question_bank`, `user_question_log`, `streak_config`, `daily_challenge` | Sprint 2 | None |
| 2 | Complete CS PYQ import (2009–2012 + answer keys) | Sprint 1 | Rahul PDFs |
| 3 | `ingest_cross_exam.py` for CDS/NDA/CAPF/CISF | Sprint 4 | PDF sourcing |
| 4 | Serving layer `question_server.py` (QP-1 to QP-12) | Sprint 4 | Schema done |
| 5 | SRS engine `srs.py` | Sprint 4 | Schema done |
| 6 | Streak shield service | Sprint 4 | Schema done |
| 7 | Username generation + onboarding | Sprint 5 | None |
| 8 | Daily challenge cron + leaderboard | Sprint 6 | Bank filled |
| 9 | AI gap-fill audit + Haiku batch | Sprint 4 | Bank ingested |
| 10 | Cross-exam discovery UI (Pro) | Sprint 7 | Bank filled |
