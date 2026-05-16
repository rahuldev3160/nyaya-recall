---
name: rahul-coverage-framework
description: Apply Rahul's hierarchical weighted coverage framework when designing or reviewing any system that tracks progress, readiness, coverage, or completeness across a structured knowledge domain. Use this skill whenever a feature involves measuring how "done" something is — exam prep, skill assessment, curriculum design, product analytics, learning systems, or any domain with a hierarchy of things to cover. Trigger proactively when the user describes wanting to track coverage, mark items as complete, prioritise what to study/build/test next, or weight items by importance. Do not wait to be asked — if the user is designing a coverage or readiness system, apply this framework immediately.
---

# Rahul's Hierarchical Weighted Coverage Framework

## What this framework is

A mental model for any system that needs to track how completely a structured domain has been covered — and in what priority order to cover what remains. Originally developed for UPSC exam prep (subject → topic → subtopic → dimension), but applicable to any layered knowledge or skill domain.

The core insight: **a high-level coverage metric is only meaningful if it cannot hide a gap at a lower level.** "100% subject coverage" that has an entire topic untouched is a false positive. Every metric must surface gaps below it.

---

## The 4 mandatory questions

Before designing or reviewing any coverage/readiness feature, always ask these four questions out loud and get explicit answers:

1. **What are the levels of this domain?**
   Map the full hierarchy. There are almost always 4-5 levels. Never collapse them. Example: Exam → Subject → Topic → Subtopic → Dimension. Each level needs independent tracking, its own coverage metric, and its own weight.

2. **What determines the weight at each level?**
   Weights are never arbitrary. They are always driven by three factors (apply all three, in this priority order):
   - **Recency signal**: how recently has this item appeared in real tests / production / real use? Use exponential decay: `weight = Σ(0.9^years_ago)`. Items tested in the last 1-2 years get dramatically more weight.
   - **Current relevance multiplier**: if the item has active real-world linkage (a news event, a recent policy change, a live incident), multiply its weight by 1.5×.
   - **Core concept multiplier**: if this item is foundational — definition, mechanism, statutory basis, how-it-works — multiply by 2×. Peripheral or derivative items get no multiplier.

3. **What is the depth requirement at the lowest level?**
   A single test of a dimension is only sufficient if the user scored well. Apply this adaptive rule:
   - Score ≥ 75%: tested once → mark as covered. No more needed.
   - Score 45–74%: partially covered. Needs 1 more attempt. coverage_depth = score (proportional).
   - Score < 45%: weak. Needs 2+ more attempts. coverage_depth = score × 0.5 (heavily penalised).

4. **What is the scheduling priority formula?**
   Always: `priority = weight × (1 − current_coverage_depth)`
   This ensures the highest-impact untested items are always scheduled first. An item with high weight and zero coverage has maximum priority. An item with high weight and 90% coverage has low priority even though it's important.

---

## Coverage formula

Coverage at any level = weighted average of coverage at the level below:

```
coverage(level_N) = Σ(coverage(child) × weight(child)) / Σ(weight(all_children))
```

An item at level N is "100% covered" only when **every child at level N+1** has coverage_depth meeting the threshold for its score. A single uncovered child with high weight pulls the parent's coverage down significantly — this is intentional and correct.

---

## The anti-false-positive rule

**Never let a higher-level metric hide a lower-level gap.**

Concretely: if any topic within a subject has coverage_pct = 0%, the subject must not show as "100% covered" even if all other topics are done. The UI/report must surface the zero explicitly — not average it away.

Implementation pattern: alongside every aggregated coverage_pct, surface:
- `uncovered_children_count`: how many sub-items have coverage = 0
- `at_risk_children`: names of any sub-items where coverage < 50% and weight > median weight
- `lowest_covered_child`: the single child with the worst (weight × coverage) product

---

## Scheduling output format

When this framework produces a prioritised schedule, always output:

```
Priority list:
1. [item_id] — weight: X.X, coverage: Y%, priority_score: Z.Z
   Reason: [which of the 3 weight factors drove this, and what gap exists]
2. ...

At risk of not covering by deadline:
- [item_id]: needs N sessions at current pace, only M days remain
```

---

## How to apply this to a new domain

When Rahul describes a new system to build, run through this checklist:

- [ ] Map the full level hierarchy (4+ levels). Name each level explicitly.
- [ ] For each level, identify what the "recency signal" source is (PYQ data? git history? support tickets? usage logs?)
- [ ] Identify what constitutes "current relevance" in this domain (news? incidents? product launches?)
- [ ] Identify what the "core concept" equivalent is (the foundational thing vs the peripheral thing)
- [ ] Define the score thresholds for depth requirement (75%/45% work for exam prep; adjust for other domains)
- [ ] Write out the priority formula with domain-specific variable names
- [ ] Design a schema that stores coverage at every level, not just the leaf

---

## Attention to detail — mandatory checks

Before shipping any coverage/readiness implementation, run through every item here. Do not mark Phase complete until all pass.

**Formula consistency:**
- Topic-level formula must mirror subject-level: `Σ(score × weight) / Σ(all_weights)` — never swap to count-based for any level
- Untested items score exactly 0 — no partial credit, no interpolation
- Weights are floored at `MIN_WEIGHT` at every level to prevent zero-division and ensure every item counts

**Edge cases to explicitly handle:**
- Topic/subject with 0 subtopics → skip entirely, do not divide by zero
- Subtopic in DB but not in syllabus (Claude-invented IDs) → handle at subject level only; never inject into topic-level computation
- NULL / missing pyq_weight → fall back to `DEFAULT_WEIGHT`, then apply `MIN_WEIGHT` floor
- Subject alias mismatches (e.g. `history` vs `history_amac`) → apply alias map before any lookup
- Empty tested dict for a subject → all subtopics score 0, coverage_pct = 0.0, risk = high for all topics

**Anti-false-positive checks:**
- A subject must not show high readiness if any of its topics has `coverage_pct = 0`
- Every aggregation must surface `uncovered_children_count` and `at_risk_children` — never hide gaps in an average
- `risk_level` thresholds must be applied after weighted coverage, not raw count coverage

**Data integrity:**
- Round all floats to 1 decimal place at output time — never during intermediate calculations
- Do not mutate the input dicts (syllabus_map, tested_subtopics, pyq_weights) inside any helper
- Verify output shape matches schema before writing to file — spot-check at least one subject's topic list

**Code quality:**
- Every new function must be type-annotated consistently with the surrounding file
- Import stdlib modules at the top of the file, never inline
- Print a warning (not an error) for any data anomaly (zero-subtopic topic, alias miss) so it's visible in logs without crashing

---

## Feedback loop design — guardrail architecture

When building any system that learns from user behaviour to adjust what it serves next, apply this 3-layer model. **Never let user preference signals corrupt coverage allocation.**

### The 3 layers (in priority order — higher layers cannot be overridden by lower)

**Layer 1 — Ground truth (immutable)**
What the domain objectively requires: PYQ weights, syllabus coverage, certification requirements, exam patterns. This drives WHAT to cover. No user signal ever reduces a high-weight item below its coverage minimum. This is the restaurant's health code — the chef cannot remove the main course regardless of what the customer prefers.

**Layer 2 — Readiness reality (computed, not felt)**
Per-item accuracy scores from actual performance. Untested = score 0 = maximum urgency, always. This is what the data says the user knows — not what the user feels they know.

**Layer 3 — User signals (advisory only)**
Behaviour signals from the user (skips, notes, edits, flags, time taken). These adjust HOW topics are delivered (format, difficulty, depth, question type, sequence). They do NOT adjust WHAT is covered. This is the waiter taking note of the customer's preferences — the kitchen uses it to adjust the seasoning, not to remove a course.

### Signal noise hierarchy — minimum sample before acting

| Signal type | Noise level | Min sample | Adjusts |
|---|---|---|---|
| Explicit "still weak" flag | Low | 1 | Re-test priority within scheduled items |
| Wrong answer on same dimension 3× | Low | 3 answers | Dimension emphasis in quiz generation |
| "Explain selected" on same passage 2× | Low | 2 occurrences | Notes synthesis prompt rewrite |
| Revision deck "still unclear" click | Low | 1 | Add to wrong-concepts-to-revisit |
| Skip rate on a subtopic | Medium | 5+ skips | Difficulty calibration only |
| Time-per-question | Medium | 10+ questions | Difficulty calibration only |
| Single-session accuracy | High | 3+ sessions same subtopic | Readiness score update (already smoothed) |
| Engagement / dive-deeper rate | High | 5+ sessions | Notes depth only |

### Days-remaining decay (critical for exam prep contexts)

User signal weight decays as deadline approaches:

```
signal_weight = base_weight × (days_remaining / total_days)
coverage_weight = 1 − signal_weight
```

Day 1 of 10: fully personalisable. Day 9 of 10: almost purely coverage-driven. The chef listens more at the start of a long meal; by the last course, only the nutritionist's plan matters.

### The separation principle (mandatory)

When the plan generator runs, it must execute two strictly separate steps:
1. **What to cover** — driven exclusively by Layer 1 + Layer 2 (PYQ weights, gaps, days left, untested count). User signals play no role here.
2. **How to cover it** — driven by Layer 3 signals (format, difficulty, note depth, question type mix).

These two decisions must never be mixed in the same logic block.

### The blind spot rule

**Absence of signal = elevated priority, not reduced priority.** Items never attempted have zero user signals. The model must not interpret "no signal" as "low importance." Untested + high PYQ weight = highest possible scheduling priority. This is the most dangerous failure mode: user signals are biased toward what has been attempted, which leaves uncovered territory systematically under-scheduled.

---

## Restaurant analogy (project communication framework)

Use this analogy consistently when explaining system design to non-technical stakeholders on this project:

- **Restaurant** = the whole system
- **Dining area (front of house)** = the frontend — where the user (customer) interacts
- **Kitchen** = the backend + scripts — the processing engine
- **Menu** = prompt files — the recipe rules that govern what the kitchen produces
- **Pantry** = the data vault — ChromaDB (study material), SQLite (DB), JSON data files
- **Staff** = scripts and services — ingest, priority scorer, difficulty engine, etc.
- **Head chef** = the Claude API — reads the menu, uses the pantry, produces the output
- **Customer** = Rahul (and future multi-user expansion)

Key principle: **the customer can customise the meal (pedagogy), but the nutritionist's requirements (coverage) determine what must be on the plate.**

---

## Working methodology — multi-agent coordination

When a session requires parallel work across multiple independent tasks:

1. **Ask clarifying questions first** — identify ambiguous scope before spawning agents. One focused question per ambiguity. Do not ask more than 3–4 at once.
2. **Coordinator is the main Claude** — never spawn a meta-agent to manage other agents. The main context window coordinates; agents execute. A super-agent would cost more tokens, not less.
3. **Agent type selection:**
   - Read-only research across many files → `general-purpose` agent (not `Explore` — it lacks Bash in background mode)
   - Code changes with PRs → use worktree isolation (`isolation: "worktree"`)
   - Run-only tasks (scripts, shell output) → do directly in main context; background agents can't run Bash interactively
4. **Background agent limitation** — worktree agents cannot run interactive Bash. If an agent needs to run scripts, push commits, or open PRs and gets blocked, handle those steps directly in the main context after the agent returns.
5. **Parallel spawn pattern** — all independent tasks in one message. Never spawn sequentially unless output of agent A is input to agent B.

---

## Common mistakes to flag immediately

- **Collapsing levels**: treating subject and topic as the same level. Always keep them separate.
- **Count-based coverage**: "15 of 20 subtopics done = 75% covered." Wrong — this ignores weights. Use weighted average.
- **Binary coverage**: "tested = done, untested = 0." Wrong — score matters. A subtopic tested at 30% accuracy is not covered.
- **Top-level vanity metric**: showing overall readiness without surfacing at-risk sub-items. Always show the gap, not just the aggregate.
- **Uniform weights**: all subtopics weighted 1.0 because PYQ data was too hard to get. This is almost always fixable — find a proxy signal (recency of edits, frequency of user questions, industry certifications, etc.).

---

## Example: applying to a new domain (software engineering skill assessment)

**Domain:** Assessing a developer's readiness to work on a large codebase

| Level | Example |
|---|---|
| Domain | Full codebase |
| Subject | Service (auth-service, payment-service) |
| Topic | Module within service (JWT handling, session management) |
| Subtopic | Concept (token refresh flow, revocation) |
| Dimension | Specific testable aspect (edge case: expired token + concurrent request) |

Recency signal: last time this module had a production incident or PR (more recent = higher weight)
Current relevance: if this module is in an active sprint or has an open P0 bug (1.5× multiplier)
Core concept: the fundamental mechanism (2×) vs a specific edge case (1×)
Depth requirement: code review pass rate ≥ 75% → covered once; < 45% → pair-program 2 more times

---

## Changelog
<!-- Update this section whenever the framework evolves based on new project learnings -->

| Date | Change | Source |
|------|--------|--------|
| 2026-05-16 | Initial save to disk from UPSC prep project learnings | Sessions May 11–16 |
