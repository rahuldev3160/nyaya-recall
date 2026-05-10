---
Feature: GitHub Collaboration Setup
Status: In Progress
Priority: Critical
Trigger: User + friend (SE) need to co-develop; user studies 7-8h/day as power tester
---

## Goal

Push this project to GitHub so:
- User = power user / tester, studies 7-8h/day, files issues and requests features in real time
- Friend (SE) = developer, picks up issues and ships features
- Claude Code = AI pair programmer for both parties

## Execution checklist

- [x] Create .gitignore (exclude secrets, vector store, node_modules, DB)
- [x] Create README.md with setup instructions for the friend
- [x] Create CONTRIBUTING.md with dev workflow
- [x] Init git repo
- [x] Create GitHub repo
- [x] First commit + push
- [ ] Create issue templates (bug, feature request)
- [ ] Set up GitHub Projects board (Backlog / In Progress / Done)

## Collaboration model

User (aspirant):
- Uses the app daily, hits bugs, wants features
- Files GitHub Issues with screenshots and context
- Labels: `bug`, `ux`, `feature-request`

Friend (SE):
- Picks up issues from GitHub, implements, opens PRs
- Claude Code assists with PR review and implementation

## Secrets management

Things that MUST NOT go to GitHub:
- `.env` (API key, paths)
- `data/upsc.db` (personal session data)
- `vector_store/` (11K ChromaDB chunks, 500MB+)
- `cache/` (generated explanations)
- `data/prep_profile.json` (personal performance)

Friend sets up their own `.env` from `.env.example`.
Friend runs `python3 scripts/db_init.py` and `python3 scripts/ingest.py` locally.
