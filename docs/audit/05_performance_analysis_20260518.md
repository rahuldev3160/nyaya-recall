# Performance Analysis — Rahul Singh — 2026-05-18

**Exam date:** 2026-05-20 (2 days away)
**Analysis run at:** 2026-05-18
**System:** Devthorium local UPSC prep platform

---

## Data Sources Used

| Source | Status | Notes |
|--------|--------|-------|
| `upsc.db` → `quiz_sessions` | Available | 83 sessions recorded |
| `upsc.db` → `session_answers` | Available | 955 answers total |
| `upsc.db` → `session_summaries` | Available | 66 sessions with full summaries |
| `upsc.db` → `subtopic_scores` | Available | 166 subtopic score rows |
| `upsc.db` → `sar_scores` | Available (minimal) | Only 1 row; 0 total_claims — effectively unused |
| `upsc.db` → `subject_attestations` | Empty | No self-attestation records |
| `upsc.db` → `subtopic_difficulty` | Available | Difficulty tracking (all "easy") |
| `data/prep_profile.json` | Available | Full readiness state as of 2026-05-17T09:25 |
| `data/study_plan.json` | Not queried | Not needed for this analysis |
| PYQ question bank | Not queried | No PYQ-linked accuracy data available |
| `time_taken_sec` for 8 of 11 subjects | Zeroed out | Only polity, economy, geography have non-zero avg times; the rest were batch-generated without per-question timing |

---

## Overall Standing — Executive Summary

- **Overall computed readiness: 64.4%** (from prep_profile.json, last updated 2026-05-17T09:25). With the UPSC cutoff typically requiring ~55–60% raw score (80–90 of 150 questions, net of negative marking), Rahul is in a borderline zone — neither safe nor certainly failing.
- **Raw quiz accuracy: 72.9% overall** (693 correct of 955 answered). However, this figure is inflated by subjects with high attempt counts where questions were easier or repeated across topics. Net exam score after one-third negative marking would be meaningfully lower.
- **CSAT is undiagnosed.** With 0 subtopics assessed in the profile and only 15 diagnostic-labelled questions in the DB (73.3% on those), the qualifying paper is effectively a blind spot entering exam day.
- **IR/Governance is the weakest content subject** (55.7% raw accuracy, 56.3% readiness) and has 6 of 12 subtopics at zero score, including the entire global_issues_geopolitics cluster.
- **History (Art/Culture/Medieval) has a critical coverage gap**: only 41.4% of its 29 subtopics tested, with statement_based accuracy at 55.6% — the worst format accuracy of any subject.

---

## Study Activity

| Metric | Value |
|--------|-------|
| Total sessions | 83 |
| Total questions answered | 955 |
| Total estimated study hours | ~1.83 hours (only timed questions; the vast majority have time_taken_sec=0) |
| Active study days | 8 (May 10–17) |
| Days 1–3 (May 10–12) | Diagnostic phase; 221 questions |
| Days 4–8 (May 13–17) | Adaptive + targeted; 734 questions |

**Study activity by day:**

| Date | Sessions | Questions | Correct | Accuracy |
|------|----------|-----------|---------|----------|
| 2026-05-10 | 5 sessions (9 quiz_sessions records) | 52 | 45 | 86.5% |
| 2026-05-11 | 9 sessions | 99 | 50 | 50.5% |
| 2026-05-12 | 5 sessions | 70 | 44 | 62.9% |
| 2026-05-13 | 9 sessions | 135 | 107 | 79.3% |
| 2026-05-14 | 11 sessions | 155 | 116 | 74.8% |
| 2026-05-15 | 14 sessions | 218 | 163 | 74.8% |
| 2026-05-16 | 7 sessions | 107 | 85 | 79.4% |
| 2026-05-17 | 8 sessions | 119 | 86 | 72.3% |

**Note:** May 11 dropped to 50.5% — the first day of diagnostic sessions across weakest subjects (ir_governance diagnostic: 20%, environment diagnostic: 33.3%, science_tech: 53.3%). This represents honest early baselines, not a bad day.

---

## Subject-Level Performance

| Subject | Attempted | Accuracy (raw) | Readiness (profile) | Coverage | Confidence | Assessment |
|---------|-----------|---------------|---------------------|----------|------------|------------|
| history (IVC only) | 30 | 100.0% | n/a (absorbed) | — | — | Artificial 100% — only one subtopic tested |
| economy | 97 | 78.4% | 79.1% | 95.8% | Strong | Well-prepared; 5 zero-subtopics suppress ceiling |
| history_amac | 201 | 77.6% | 49.4% | 41.4% | Moderate | **Gap alert**: profile readiness (49.4%) far below raw accuracy; 17 of 29 subtopics untested |
| polity | 137 | 76.6% | 79.7% | 100% | Strong | Strong; 6 weak subtopics need targeted revision |
| csat | 15 | 73.3% | 0.0% | 0% | Unassessed | **Critical**: qualifying paper essentially undiagnosed |
| current_affairs | 47 | 72.3% | 32.7% | 41.7% | Moderate | Only 5 of 12 subtopics tested; 7 fully blind |
| science_tech | 45 | 71.1% | 77.0% | 100% | Strong | 5 zero-scored subtopics, all one-attempt |
| environment | 186 | 69.9% | 67.5% | 90.9% | Moderate | Statement-based weak (60.4%); 4 zero-scored subtopics |
| geography | 70 | 68.6% | 71.0% | 100% | Moderate | Economic geography and mapping clusters weak |
| modern_history | 30 | 66.7% | 77.3% | 100% | Moderate | 3 subtopics at zero; main body solid |
| ir_governance | 97 | 55.7% | 56.3% | 100% | Moderate | **Weakest content subject**; both question formats weak |

---

## Strong Areas (>70% accuracy, ≥20 attempts)

1. **Economy — WTO Agreements**: 93.3% on 15 attempts. Last session 93.3%. Confirmed strong in profile.
2. **History AMAC — IVC Sites & Features**: 84.4% on 45 attempts. The single most attempted subtopic. Reliable knowledge base.
3. **History AMAC — Post-Mauryan period**: 88.9% on 18 attempts.
4. **Polity — Right to Freedom**: 94.1% on 17 attempts.
5. **Polity — President**: 81.3% on 16 attempts.
6. **Polity — Distribution of Powers (Federalism)**: 76.5% on 17 attempts.
7. **Environment — Pollution Types**: 83.3% on 18 attempts.
8. **Environment — Flora/Fauna in News**: 83.3% on 18 attempts.
9. **Environment — Biosphere Reserves**: 81.3% on 16 attempts.
10. **Economy — RBI Functions**: 86.7% on 15 attempts.
11. **Economy — Monetary Policy**: 86.7% on 15 attempts.
12. **Geography — Agriculture & Crops**: 76.5% on 17 attempts.
13. **History AMAC — Regional Kingdoms**: 86.7% on 15 attempts.
14. **IR — Trade Orgs/WTO**: 81.3% on 16 attempts.

---

## Weak Areas (<55% accuracy, ≥10 attempts) — Backed by Data

| Area | Attempts | Correct | Accuracy | Trend | Evidence |
|------|----------|---------|----------|-------|---------|
| **IR — India-Neighbours SAARC** | 32 | 16 | 50.0% | Improving | Largest bilateral subtopic; 50% is well below exam requirement |
| **Environment — Climate Conventions/COP** | 16 | 8 | 50.0% | Unknown | Below minimum viable for exam |
| **IR — India Other Regions** (bilateral) | 12 | 6 | 50.0% | Improving | Flagged "weak" in subtopic_scores |
| **Environment — Solid Waste/Plastic** | 15 | 8 | 53.3% | Stable | Consistently weak across sessions |
| **IR — G20/G7/BRICS/SCO** | 26 | 16 | 61.5% | Stable | Second most attempted IR subtopic; underperforming |
| **History AMAC — Rock Cut Cave (Art/Arch)** | 15 | 9 | 60.0% | Stable | Only 20% of art_architecture subtopics tested |
| **Geography — Military Exercises Locations** | 16 | 10 | 62.5% | Stable | Mapping cluster weakness |
| **Modern History — Civil Disobedience/Salt** | 16 | 10 | 62.5% | Stable | Core freedom struggle topic underperforming |
| **Economy — IMF/World Bank** | 16 | 10 | 62.5% | Stable | International trade cluster |
| **Environment — Wildlife Projects** | 16 | 10 | 62.5% | Stable | Protected areas topic |

**Additionally — zero-scored but single attempts only (exam risk if appears):**
- IR: regional_orgs_asean (0%), ongoing_conflicts (0%), nuclear_treaties_npt (0%), terrorism_int_security (0%)
- Environment: biogeochemical_cycles (0%), invasive_alien_species (0%), ramsar_wetlands (0%), ozone_montreal (0%)
- Geography: monsoon_el_nino (0%), coastal_islands (0%), minerals_distribution (0%), industries_location (0%)
- Science/Tech: missiles_drdo (0%), indigenisation_defence (0%), genetic_engineering_gmo (0%)
- Modern History: constitutional_reforms (0%), partition_bengal_swadeshi (0%), subsidiary_lapse (0%)

---

## Coverage Gaps (Subjects/Topics Barely Touched)

### CSAT (Qualifying Paper) — CRITICAL
- Profile readiness: 0.0% (unassessed)
- 0 of 11 subtopics in the profile have been tested
- Only 15 questions in DB under subject_id='csat', from 1 adaptive session (73.3%) on May 14
- CSAT is a qualifying gate — failing it nullifies any GS score. This is the single biggest exam-day risk.

### Current Affairs — High Risk
- Only 5 of 12 subtopics tested; 7 completely blind
- **defence_military_news**: 0% coverage, 0 attempts
- **awards_persons_news**: 1 of 3 subtopics tested (33.3% topic coverage)
- **gi_tags_culture_news**: 1 of 2 tested
- Profile readiness: 32.7% — the lowest of any content subject

### History AMAC (Art, Medieval, Culture) — High Risk
- 12 of 29 subtopics tested (41.4% coverage)
- **handicrafts_gi**: 0 of 3 subtopics tested — 0 attempts, profile readiness 0%
- **art_architecture**: 1 of 5 subtopics tested — profile readiness 18.8%
- **performing_arts**: 1 of 3 subtopics tested
- 17 subtopics completely undiagnosed going into exam

### IR/Governance — Global Issues Cluster
- global_issues_geopolitics: all 3 subtopics (ongoing_conflicts, nuclear_treaties_npt, terrorism_int_security) at 0% readiness, 1 attempt each
- Profile labels this topic as 0.0% readiness despite showing 100% coverage — the system counted them as "tested" on 1-attempt basis

---

## Performance Trajectory

**Day-by-day accuracy trend:**

| Date | Accuracy | Key subjects | Signal |
|------|----------|-------------|--------|
| May 10 | 86.5% | History (IVC only, easy) | Misleading baseline — only strong subjects |
| May 11 | 50.5% | Diagnostics across weak subjects | True baseline for weak areas: IR=20%, Env=33% |
| May 12 | 62.9% | IR adaptive sessions | Struggling with IR (multiple <75% sessions) |
| May 13 | 79.3% | Economy, Polity, Environment | Recovery; strong subjects dominate session mix |
| May 14 | 74.8% | Mixed including CSAT | Stable; first CSAT session |
| May 15 | 74.8% | Geography, Polity, Science | Consistent mid-70s |
| May 16 | 79.4% | History AMAC, Environment | Best multi-subject day; solid adaptive sessions |
| May 17 | 72.3% | Exam sim (Polity), IR, Economy | Slight dip; exam sim scored 65% |

**Trajectory verdict:** Accuracy improved from the true diagnostic baseline (50.5%) to a consistent 72–79% range. The improvement is real but has plateaued in the mid-70s since May 13. There is no strong upward trend in the final days — accuracy has oscillated between 72–79% for 5 consecutive days.

**The exam simulation on May 17 (polity, 65% on 20 mixed questions) is the single most relevant data point**: it represents near-exam conditions with mixed question types and is significantly below the raw adaptive scores, consistent with the thesis that adaptive quiz accuracy (which often re-targets familiar subtopics) overstates true exam readiness.

---

## Time Management Analysis

| Subject | Avg Sec/Question | Min | Max (<300s) | Notes |
|---------|-----------------|-----|------------|-------|
| Polity | 108.2 sec | 10 | 240 | ~1:48 per question — above UPSC target (~90 sec) |
| Economy | 57.3 sec | 15 | 256 | Good pace |
| Geography | 56.9 sec | 18 | 59 | Good pace |
| All others | NULL / 0 | — | — | No timing data captured |

**Major limitation:** 8 of 11 subjects have zero timing data (time_taken_sec=0 for all questions). This means:
- We cannot assess time management for environment, history, IR, modern history, science, current affairs, or CSAT
- Polity's 108-second average is concerning — UPSC Prelims allows ~144 seconds per question across 100 questions (2 hours), but polity questions requiring careful statement analysis appear to be taking longer than ideal
- The economy and geography paces are good and suggest no panic for factual questions

---

## Topic-Level Breakdown

### Polity (76.6% raw, 79.7% readiness, 100% coverage)

| Topic | Readiness | At-Risk Subtopics |
|-------|-----------|------------------|
| Fundamental Rights & DPSP | 92.0% | right_against_exploitation (0%) |
| Judiciary | 100.0% | None |
| Federalism | 100.0% | None |
| Constitutional Bodies | 77.8% | finance_commission (0%), election_commission (42.9%) |
| Union Executive | 75.7% | prime_minister_cabinet (50%) |
| Parliament | 64.6% | bills_legislation (50%), lok_sabha (50%) |
| Constitutional Framework | 63.6% | preamble (0%), union_territories (0%) |
| Local Governance | 67.1% | panchayati_raj (0%) |
| Schedules | 100.0% | None |

**Exam simulation on May 17 scored 65% (13/20), with statement_based at 55.6% in that session.** The gap between adaptive quiz scores (often 80–90%) and the exam simulation score is significant.

### Economy (78.4% raw, 79.1% readiness, 95.8% coverage)

| Topic | Readiness | At-Risk Subtopics |
|-------|-----------|------------------|
| Macroeconomic Basics | 89.0% | None |
| Banking & Finance | 82.0% | digital_payments_fintech (0%) |
| International Trade | 77.8% | One subtopic untested |
| Agriculture & Rural | 77.8% | agriculture_revolutions (0%) |
| Poverty & Development | 73.1% | None |
| Union Budget & Taxation | 57.3% | budget_2025_highlights (0%), budget_2026_highlights (0%) |
| Economic Survey | 51.3% | india_rankings_reports (0%) |

**Budget & taxation (57.3% readiness) and Economic Survey (51.3%) are underprepared for a subject otherwise strong.** These are high-probability UPSC questions.

### History AMAC (77.6% raw, 49.4% readiness, 41.4% coverage)

| Topic | Coverage | Readiness | Risk |
|-------|----------|-----------|------|
| Ancient Dynasties | 60% | 60.9% | Medium |
| Indus Valley | 50% | 65.3% | Medium |
| Vedic Age | 50% | 59.7% | Medium |
| Religion & Philosophy | 50% | 59.2% | Medium |
| Medieval India | 40% | 55.9% | **High** |
| Art & Architecture | 20% | 18.8% | **High** |
| Performing Arts | 33% | 34.3% | **High** |
| Handicrafts & GI Tags | 0% | 0.0% | **High** |

**The 77.6% raw accuracy is deceptive.** It's driven by IVC (84.4% on 45 questions, tested 3 times) and strong performance on Mauryan/Post-Mauryan dynasties. The 17 untested subtopics include the entire handicrafts/GI cluster and most of art/architecture. UPSC Prelims consistently tests art, architecture, performing arts, and handicrafts — this is a structural preparation gap.

### Environment (69.9% raw, 67.5% readiness, 90.9% coverage)

| Topic | Coverage | Readiness | Weak Subtopics |
|-------|----------|-----------|----------------|
| Biodiversity | 100% | 85.3% | invasive_alien_species (0%) |
| Ecology Basics | 100% | 73.3% | biogeochemical_cycles (0%) |
| Species in News | 50% | 71.7% | One untested |
| Protected Areas | 100% | 66.9% | ramsar_wetlands (0%) |
| Climate Change | 100% | 62.2% | ozone_montreal (0%), climate_conventions_cop (50%) |
| Env Laws & Policies | 67% | 61.7% | One untested |

**Statement-based accuracy in environment: 60.4%** — the worst among subjects with substantial statement-based exposure. Direct-fact accuracy is better at 74.8%. This matters because UPSC heavily uses statement-based format for environment questions.

### IR/Governance (55.7% raw, 56.3% readiness, 100% coverage)

| Topic | Readiness | Weak Subtopics |
|-------|-----------|----------------|
| Governance Initiatives | 79.3% | transparency_accountability (0%) |
| International Orgs | 66.7% | regional_orgs_asean (0%) |
| India Bilateral | 46.3% | india_neighbours_saarc (50%), india_other_regions (42.9%) |
| Global Issues/Geopolitics | 0.0% | ongoing_conflicts (0%), nuclear_treaties_npt (0%), terrorism_int_security (0%) |

**Statement-based accuracy: 40.7% — the worst of any subject.** Direct-fact accuracy: 62.7% — also the worst. Both question formats are weak in IR. The global_issues_geopolitics cluster (3 subtopics) has 0% readiness and only 1 attempt each; this is tested in every UPSC Prelims paper.

### Geography (68.6% raw, 71.0% readiness, 100% coverage)

| Topic | Readiness | Weak Subtopics |
|-------|-----------|----------------|
| Physical Geography | 96.6% | monsoon_el_nino (0%) |
| Indian Geography | 92.9% | coastal_islands (0%) |
| Economic Geography | 46.5% | minerals_distribution (0%), industries_location (0%) |
| World Geography | 47.5% | world_mountains_plateaus (0%) |
| Mapping & Places in News | 26.3% | world_mapping_news (0%), military_exercises_locations (62.5%) |

**Physical and Indian geography are solid. Economic geography (46.5%) and mapping (26.3%) are the structural weakness clusters.** Mapping-based questions are increasing in UPSC Prelims — this is a risk.

### Modern History (66.7% raw, 77.3% readiness, 100% coverage)

| Topic | Readiness | Weak Subtopics |
|-------|-----------|----------------|
| Revolt of 1857 | 100% | None |
| British Expansion | 76% | subsidiary_lapse (0%) |
| Freedom Struggle | 67.5% | partition_bengal_swadeshi (0%), constitutional_reforms (0%) |

Civil Disobedience/Salt March: 62.5% on 16 attempts — underperforming for a core topic.

### Science & Technology (71.1% raw, 77.0% readiness, 100% coverage)

| Topic | Readiness | Weak Subtopics |
|-------|-----------|----------------|
| IT & Emerging Tech | 100% | None |
| Space Technology | 97.3% | None |
| Basic Science | 91.0% | diseases_nutrition_health (0%) |
| Biotechnology | 36.7% | genetic_engineering_gmo (0%), nanotech_applications (0%) |
| Defence Technology | 36.7% | missiles_drdo (0%), indigenisation_defence (0%) |

IT and space are reliable. Defence and biotech are underprepared on specific subtopics.

### Current Affairs (72.3% raw on attempted, 32.7% readiness overall)

| Topic | Coverage | Readiness | Weak Subtopics |
|-------|----------|-----------|----------------|
| GI Tags/Culture News | 50% | 31.8% | art_products_news untested |
| PIB/Govt Communications | 50% | 54.9% | One untested |
| Govt Schemes & Programmes | 67% | 0.0% | flagship_central_schemes (0%), new_modified_schemes (0%) |
| Awards & Persons | 33% | 45.0% | Two subtopics untested |
| Defence & Military | 0% | 0.0% | Entirely untested |

**58.3% of current affairs is completely undiagnosed.** Flagship government schemes (PM Awas, PM Kisan, etc.) are 0% readiness and are virtually guaranteed to appear in UPSC Prelims.

---

## SAR (Self-Assessment Reliability) Analysis

**Data available:**
- sar_scores table: 1 row, sar=0.5, total_claims=0, created 2026-05-10
- subject_attestations table: 0 rows

**Assessment:** The SAR system was never actively used. The score defaulted to 0.5 and no self-attestation claims were made. This means:
- The formula `effective_level = (validation_score × 0.5) + (claimed_level × 0.5)` never ran with actual claim data
- All readiness computations in prep_profile.json are based purely on quiz performance, not self-assessment — which is actually better for analytical reliability
- The SAR feature exists architecturally but was not leveraged during this prep period

---

## Readiness Score Analysis

**Overall readiness from prep_profile.json: 64.4%**

Cross-checking this against raw quiz data:

| Subject | Profile Readiness | Raw Quiz Accuracy | Gap | Explanation |
|---------|------------------|-------------------|-----|-------------|
| history_amac | 49.4% | 77.6% | -28.2 pts | Profile penalises uncovered subtopics heavily |
| current_affairs | 32.7% | 72.3% | -39.6 pts | 7 untested subtopics pull readiness to floor |
| csat | 0.0% | 73.3% (15 q) | -73.3 pts | Profile shows 0% because no subtopic-level testing |
| environment | 67.5% | 69.9% | -2.4 pts | Well-calibrated |
| polity | 79.7% | 76.6% | +3.1 pts | Slight optimism; exam sim was 65% |
| economy | 79.1% | 78.4% | +0.7 pts | Excellent calibration |
| modern_history | 77.3% | 66.7% | +10.6 pts | Profile over-confident; 3 zero subtopics suppressed in small sample |
| science_tech | 77.0% | 71.1% | +5.9 pts | Minor optimism; zero subtopics dragging it down |
| geography | 71.0% | 68.6% | +2.4 pts | Well-calibrated |
| ir_governance | 56.3% | 55.7% | +0.6 pts | Excellent calibration — the system correctly identifies this as weak |

**The profile readiness score (64.4%) is broadly trustworthy for relative subject ranking but understates true coverage gaps in subjects like history_amac where tested subtopics perform well but most are untested.** The profile's weighted readiness formula correctly penalises uncoverage.

**The exam simulation score (65%, May 17) is the best single predictor of exam performance.** It is 9.7 points below the adaptive quiz accuracy average.

---

## Key Risks Before Exam

### Risk 1 — CSAT Qualifying Failure (Severity: Critical)
- 0% profile readiness; 0 structured subtopic sessions
- UPSC CSAT cutoff is typically 33% of 200 = 66 marks. With only 15 questions ever attempted (73.3%), there is no validated baseline.
- **If CSAT is failed, the GS score is irrelevant.** This is a pass/fail gate.

### Risk 2 — History AMAC Coverage Black Holes (Severity: High)
- 17 of 29 subtopics never tested — including the entire handicrafts/GI cluster (0 attempts, 0% readiness)
- Art & Architecture tested on only 1 subtopic at 60% accuracy
- UPSC Prelims tests art, architecture, and handicrafts in every paper (typically 3–6 questions)
- Statement-based accuracy in history_amac: 55.6% — the lowest subject-format combination

### Risk 3 — IR/Governance — Format and Content Both Weak (Severity: High)
- Statement-based: 40.7% (worst of any subject)
- Direct-fact: 62.7% (worst of any subject)
- Global Issues cluster (3 subtopics): 0% readiness, only 1 attempt each
- India-Neighbours SAARC: 50% on 32 attempts — heavily attempted but still underperforming
- UPSC Prelims typically has 8–12 IR questions; current form suggests 4–6 correct at best

### Risk 4 — Current Affairs Blind Spots (Severity: High)
- Flagship government schemes: 0% readiness (0/2 correct in 2 attempts)
- Defence/Military: 0 attempts
- UPSC Prelims has 10–15 current affairs questions; 58% of the topic taxonomy is undiagnosed

### Risk 5 — Statement-Based Question Format Weakness (Severity: Medium-High)
- Across all subjects, statement-based questions consistently underperform direct-fact:
  - IR: 40.7% vs 62.7%
  - History AMAC: 55.6% vs 82.8%
  - Environment: 60.4% vs 74.8%
  - Modern History: 60.0% vs 68.4%
  - Economy: 67.9% vs 86.8%
- UPSC Prelims uses statement-based format for ~40–50% of questions. This is a systematic skill gap.

### Risk 6 — Exam Simulation Score Gap (Severity: Medium)
- Only 1 exam simulation run (May 17, polity, 65%)
- Adaptive quiz accuracy (~75%) is systematically higher than simulation performance
- The actual exam experience with time pressure, mixed difficulty, and unfamiliar question phrasing will likely result in a score closer to 65–70% than the 75%+ adaptive average

### Risk 7 — Zero-Scored Subtopics Across All Subjects (Severity: Medium)
- 30+ subtopics across all subjects have 0% score from only 1–2 attempts
- These are effectively "blind spots" where any exam question will likely be guessed
- Concentration: IR geopolitics, Environment (ozone, wetlands), Geography (economic), Science (defence, biotech)

---

## Honest Verdict

**Where Rahul stands (as of 2026-05-18, 2 days before exam):**

Rahul has put in a serious 8-day preparation effort — 955 questions, 83 sessions, genuine improvement from diagnostic baselines. The system has worked as designed. However, the honest picture for a Prelims requiring ~55–60% net score (accounting for negative marking) after negative marking is:

**Likely exam score: 62–70% gross accuracy on attempted questions, translating to approximately 55–65 net marks out of 100 questions (after one-third negative marking deduction).** This is at or just below the typical cutoff zone — neither safe nor certainly failing.

**Three things that would move the needle most in the next 2 days:**

1. **Do at least 2 full CSAT practice sessions covering comprehension, maths basics, and reasoning.** A CSAT failure is a complete GS wipeout regardless of preparation. The qualifying cutoff is 33% (66/200) — it should be achievable but must be confirmed.

2. **Targeted revision of zero-scored subtopics in the highest-frequency UPSC subjects: IR geopolitics (nuclear treaties, ASEAN, ongoing conflicts), environment (Ramsar/ozone/wetlands), and economy (budget highlights, agriculture revolutions).** These are short-fact topics that can be crammed in 1–2 hours from notes and PYQ patterns.

3. **Do not practice more adaptive quizzes — the adaptive format shows 75%+ and creates false confidence. Instead, do 1 more mixed-subject exam simulation (100 questions, 2-hour timer) and honestly measure the score.** Adaptive quizzes have been testing familiar subtopics; the exam will not.

---

## Data Limitations

| Limitation | Impact on Analysis |
|-----------|-------------------|
| Time data missing for 8 of 11 subjects (time_taken_sec=0) | Cannot assess speed risk for Environment, History, IR, Current Affairs |
| Zero subject_attestations and SAR effectively unused | SAR-based calibration of readiness unavailable; all readiness is quiz-derived |
| History AMAC tested only 41.4% of subtopics | Raw accuracy of 77.6% is misleading; performance on untested subtopics unknowable |
| CSAT has 15 questions from 1 session, no subtopic structure | Cannot assess CSAT readiness by topic (comprehension vs maths vs reasoning) |
| Subtopics with 1–2 attempts treated as "assessed" in subtopic_scores | Single-question accuracy is statistically unreliable; many "strong" subtopics may be false positives |
| No PYQ-linked accuracy tracking queried | Cannot cross-reference performance against prior-year question frequency weighting |
| Subtopic difficulty table shows all subtopics at "easy" | Either difficulty scaling hasn't activated or all sessions ran on easy — cannot assess performance under harder question conditions |
| Only 1 exam simulation session in the entire DB | Insufficient to establish a reliable near-exam performance baseline |

---

*Report generated by automated performance analysis. Data reflects upsc.db state and prep_profile.json as of 2026-05-17T09:25:07 UTC. No data added between that time and report generation on 2026-05-18.*
