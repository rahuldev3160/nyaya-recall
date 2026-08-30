# Nyaya Recall — Data Audit (2026-08-30)

Source of truth: `.env` → `DB_PATH=data/upsc.db`, `CHROMA_PATH=vector_store/`.

## 1. Data inventory

| Store | Content | Count |
|---|---|---|
| `data/upsc.db` (SQLite, 15MB, mtime 2026-08-30) | `pyq_questions` | 1,985 |
| | `question_bank` | 5,502 |
| | `question_explanations` | 904 |
| | `subtopic_difficulty` | 49 |
| | `topic_weights` | 223 |
| | `source_documents` | 2 |
| | `sar_scores` | 1 |
| | `user_profiles` / `daily_challenge` / `streak_config` / `generation_batches` | 0 (unused — no live users, matches memory) |
| ChromaDB `vector_store/chroma.sqlite3` (229MB, mtime 2026-08-30) | collection `upsc_content` | 11,146 embeddings |

Indexes exist (idx_pyq_*, idx_qb_*, etc.) — schema is properly indexed, not raw table scans. FK pragma is off at connect time (app-level enforcement per PR #49, not DB-level default).

## 2. Provenance

| Dataset | Source | Script | When |
|---|---|---|---|
| `question_bank` (5,502) | 5,181 community_validated + 321 unclassified_legacy | `import_vision_ias_quiz.py`, `import_community_pyq.py` | May–Jun 2026 (ingestion logs) |
| `pyq_questions` (1,985) | `answer_source`: 999 community_validated, 503 **unverified**, 482 **ai_inferred**, 1 community_consensus | `ingest_pyq.py`, `import_answer_keys.py` | May 2026 |
| `question_explanations` (904) | Meant to be AI-generated (Haiku Batch, script hardcodes `MODEL = "claude-haiku-4-5-20251001"`), **but `model_used` column is 100% `'community_import'` (the schema default) for all 904 rows** — the script's actual model tag never got written. Either these were never run through the AI path, or there's a silent write bug. Flag for verification. | `generate_pyq_explanations.py` | 2026-05-30 |
| `source_documents` (2) | Official web sources: PIB Union Budget 2026-27 PDF, RBI MPC Aug 2026 press release | `ingest_source_documents.py` | **2026-08-29** — new, feeds Scribe's RBI feature (see §4) |
| `vector_store` (11,146 embeddings) | Derived from question_bank/pyq content | ingest pipeline | current as of 2026-08-30 |

## 3. Indexing status

Properly indexed (13+ indexes on hot query paths). No corruption/duplicate/orphan findings in ISSUES.md beyond two known non-data-integrity bugs (orphaned quiz sessions on server restart, duplicate same-day plan sessions) — neither is a stored-data-quality issue.

**Real data-quality gap (B-5, still open):** 503 unverified + 482 ai_inferred PYQ answers (49% of 1,985) have no human/official validation.

## 4. Universal-data-source angle — key finding

**An internal API layer already exists and is more advanced than expected**: `backend/routes/internal_arena.py` — stateless, service-credential-authenticated, spec frozen in Arena's `docs/API_CONTRACTS.md`. It was generalized on 2026-08-29 (PLAN-008 §4) from "Arena-only" to **per-caller named keys** — `INTERNAL_API_KEY_ARENA` and `INTERNAL_API_KEY_SCRIBE_RBI`. That second key is real and active: it's why `source_documents` just got 2 official RBI/PIB documents ingested (2026-08-29) — **Scribe now has a live "RBI feature" consuming Recall's data via this API**, not raw DB access. This is the first real instance of the "universal data source" pattern Rahul wants — it should be the template, not a one-off.

Routes never write to `question_bank`/`sar_scores`/`quiz_sessions`/`session_answers` (stateless-read contract, documented). This is a solid access-control pattern to replicate for Scribe/law/content-pipeline consumers generally.

## 5. Gap list

| Gap | Source needed |
|---|---|
| 503 unverified + 482 ai_inferred PYQ answers | Official UPSC answer keys (upsc.gov.in/examinations/answer-keys) — pipeline scripts already exist (`import_answer_keys.py`), just needs approval + run (B-4/B-5, still blocked per SPRINT_BOARD) |
| `question_explanations.model_used` mislabeled as `community_import` for all AI-generated rows | Not a sourcing gap — a data-integrity bug: re-run script with fixed write path, or backfill correct model tag |
| GS1-3 PYQ coverage ~25% (shared blocker with Scribe, per memory) | Official UPSC PDFs |
| No generalized ingestion-provenance table (sourcing is reconstructed from ingestion_log.json files + script names, not a queryable `provenance` column on each table) | Design decision needed for the universal-DB goal — see synthesis |

**Scope note:** did not audit Arena, Scribe, law, or content-pipeline data — those are separate forks.
