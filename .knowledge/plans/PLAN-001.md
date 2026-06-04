---
id: PLAN-001
type: plan
project: devthorium
date: 2026-05-30
status: DECIDED
---

# PLAN-001: Two-Table Question Bank Architecture

## Decision
- `pyq_questions` = Civil Services GS Prelims 2013–2025 only (PYQ Browser feature)
- `question_bank` = CDS/NDA/CAPF/CISF PYQs + AI gap-fill (diagnostic engine, simulations, adaptive quizzes)

## Rationale
~6,500–7,000 real UPSC exam questions from CDS/NDA/CAPF/CISF with official answer keys at zero cost.
AI generation is last resort only for subtopics with <10 questions in the bank.
Simpler data sourcing for Phase 0: 2013–2025 only (not 2009–2025).

## Full spec: `plans/multi_exam_bank.md`
