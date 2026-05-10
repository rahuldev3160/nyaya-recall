# 2-Hour App Simulation Guide

Run this end-to-end walkthrough to test every major feature in realistic sequence.
**Total time: ~2 hours.** Each step has a time budget, expected outcome, and what to check.

Open http://localhost:3000 in your browser before starting.

---

## Step 1 — Setup your prep plan (10 min)

**Where:** Click "Setup" in the top nav.

**What to do:**
1. Click the "10-day sprint" preset (or pick any duration you want to test)
2. Set daily hours to 6
3. Look at the phase breakdown — confirm it shows Diagnostic / Intensive Revision / Mock phases
4. Click "Save & Start Prep →"

**Expected:** Redirects to dashboard. Dashboard now shows "Day 1 of 10 · 10 days remaining" and the amber "Set up your prep plan" banner disappears.

**What breaks if this step fails:** Plan generator uses hardcoded dates. Fix: check /config/ API in the browser dev console.

---

## Step 2 — First diagnostic session: Polity (25 min)

**Where:** Click "Start Diagnostic" on the dashboard.

**What to do:**
1. Select subject: **Polity & Governance**
2. Mode: Fixed Questions, set to **10 questions**
3. Click "Start Diagnostic" — button shows "Generating questions... (15–30s)"
4. Wait for questions to appear (Claude is generating them, takes 15–30 seconds)
5. Answer all 10 questions. Don't look up answers — your natural performance is the data.
6. After each question, read the explanation shown in amber.
7. After Q10, click "Finish & Save Session"

**Expected:** Score screen showing X/10 correct and overall % score.

**Check:** Go to Tracker — Polity should now show a score bar (not "—").

---

## Step 3 — Second diagnostic session: Economy (20 min)

**Where:** Go back to Diagnostic page.

**What to do:**
1. Select subject: **Economy**
2. 10 questions, fixed set
3. Complete and save session

**Expected:** Economy bar appears in Tracker.

---

## Step 4 — Run Batch Analysis (10 min)

**Where:** Click "View Full Analysis" on dashboard, OR go to Analysis page directly.

**What to do:**
1. Click "Run Batch Analysis"
2. Wait ~20 seconds (Claude analyses both sessions)

**Expected:**
- Summary paragraph describing your performance
- Subject-by-subject breakdown with accuracy %
- Weak subtopics flagged
- Overall readiness % shown

**Then:** Go back to dashboard. The readiness % and subject bars should now be populated.

---

## Step 5 — Generate tomorrow's plan (5 min)

**Where:** Dashboard — click "Sync & Plan Tomorrow" OR go to Planner page.

**What to do:**
1. Click "Sync & Plan Tomorrow" on dashboard (or "Generate Plan" in Planner with 6 hours)
2. Wait ~15 seconds

**Expected:** Dashboard shows "Today's Plan" section with 3–5 sessions listed, each with subject, subtopic, format, and time.

---

## Step 6 — Self-Attestation for a subject you know well (15 min)

**Where:** Click "Attest" in nav.

**What to do:**
1. Select a subject you genuinely feel strong about (e.g., Modern History or Polity)
2. Select your claimed level — be honest: Strong, Very Strong, or Expert
3. Click "Start Validation Quiz (12 Qs)"
4. Complete all 12 questions
5. Click "Submit & See Result"

**Expected on result page:**
- Validation score (your actual quiz %)
- Effective level (blend of quiz + claim)
- New SAR score with +/- indicator (no "NaN%")
- Explanation of how the blend was calculated

**Check SAR:** Go to Tracker — SAR widget should show a % (not blank or "NaN%").

---

## Step 7 — Adaptive session from generated plan (25 min)

**Where:** Click "Today's Sessions" in nav OR "Today's Sessions" button on dashboard.

**What to do:**
1. You should see the plan sessions from Step 5
2. Click "Start" on the first session
3. Complete it fully (answer all questions)
4. Click "Finish Session"
5. Optionally, start a second session from the plan

**Note:** The difficulty shown next to each session (easy/medium/hard/exam) was set by the adaptive engine based on your prior sessions.

---

## Step 8 — Second batch analysis (15 min)

**Where:** Analysis page.

**What to do:**
1. Run Batch Analysis again
2. This time you have 3+ sessions — the analysis should be richer
3. If any subtopics were weak in 2+ sessions, you'll see "Deep Drill Observations" with specific error patterns

**Expected:** More detailed insights now. Weak question types (statement_based, match_pairs, etc.) flagged if applicable.

---

## Step 9 — Explore remaining pages (10 min)

| Page | What to check |
|------|--------------|
| Tracker | Subject bars filled, gaps list below 75%, SAR score showing |
| Planner | Generate a new plan, verify sessions reflect updated profile |
| Strategy | Reads current profile, shows exam-day strategy |
| CSAT | Shows "coming soon" message without any file paths exposed |

---

## What "passing" looks like at the end of the simulation

- Dashboard shows actual readiness % (not 0%) with subject bars filled
- Tracker shows at least 2 subjects with scores
- Attestation result shows no "NaN%" — clean numbers
- Analysis shows subject-level insights with specific subtopics
- Plan generates sessions matching your weak subjects
- No blank screens or "undefined" text anywhere
- Quiz generation works reliably on first click (no ECONNRESET)

---

## Troubleshooting during simulation

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Quiz generation fails | Backend crashed or slow network | Wait 5s, retry once |
| "No plan for today" on Session page | Plan not generated yet | Do Step 5 first |
| Analysis shows blank | No sessions since last sync | Complete at least 1 diagnostic first |
| Tracker shows 0% everywhere | Analysis not run yet | Do Step 4 |
| Attestation shows "NaN%" | Old frontend cache | Hard-refresh the page (Cmd+Shift+R) |
| Backend stops responding | Uvicorn crashed | `! lsof -ti :8000 \| xargs kill -9; cd "..." && python3 -m uvicorn server:app --host 0.0.0.0 --port 8000` |

---

## Quick restart commands (paste in Claude Code if needed)

```bash
# Restart backend
lsof -ti :8000 | xargs kill -9 2>/dev/null
cd "/Users/rahulsingh/Desktop/Claude Projects/Last 10 Day AI powered Preparation/backend"
PATH="/opt/homebrew/bin:$PATH" python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Restart frontend (new terminal)
cd "/Users/rahulsingh/Desktop/Claude Projects/Last 10 Day AI powered Preparation/web"
npm run dev
```
