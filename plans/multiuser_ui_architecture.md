# Nyaya Recall — Multi-User UI Architecture Plan
_Created: 2026-06-15 | Synthesised from: EdTech retention research + Nyaya Scribe audit + current sprint board_

---

## Design North Star

**Core insight from Scribe:** 96% of users completed onboarding, ~0% drilled. The product didn't fail — the path from "I'm set up" to "I'm studying" was broken. Every design decision here fixes that.

**Core insight from EdTech research:** Loss aversion beats reward. Users return to protect a streak, not to gain XP. The heatmap of red subtopic squares creates gap anxiety that pulls users deeper. The quiz experience must be single-card, full-screen, with an ambient timer — not a countdown.

**Design principle:** Every screen has exactly one primary action. No dead ends.

---

## Page Map

```
/ (landing)              — unauthenticated home → 5 demo questions → signup gate
/login                   — Google OAuth + magic link
/onboarding              — exam focus + date + hours → immediate drill
/dashboard               — streak + due badge + heatmap + today's focus
/practice                — subject selector → starts quiz
/quiz/[session_id]       — single-question quiz interface (the core loop)
/pyq                     — PYQ Browser (existing, needs polish)
/pyq/[year]/[subject]    — year+subject drill
/progress                — full heatmap + subtopic analytics
/leaderboard             — daily rank widget
/profile                 — account + subscription + exam date
/pricing                 — freemium vs Pro comparison
```

---

## Screen 1 — Landing (Unauthenticated)

**Goal:** Time-to-first-value under 90 seconds. Show the product before asking for an account.

**Layout (mobile-first, dark bg #0D0D0F):**

```
┌────────────────────────────────────┐
│  NYAYA RECALL                 [Log in]│
├────────────────────────────────────┤
│                                    │
│  "Find your gaps.               │
│   Fix them. Get in."              │
│                                    │
│  [Try 5 free questions →]          │  ← primary CTA, full-width, blue
│                                    │
│  ──────  or  ──────────────        │
│                                    │
│  [Continue with Google]            │
│  [Continue with email]             │
│                                    │
├────────────────────────────────────┤
│  🔴 14 red subtopics in Polity     │  ← social proof: live metric
│  📊 2,847 questions answered today │
│  🔥 Avg streak: 6 days             │
└────────────────────────────────────┘
```

**"Try 5 questions" flow:**
- 5 diagnostic questions, no login required, subject auto-selected (Polity — most popular)
- After Q5: show result card with weak subtopic identified
- Gate: "Save your progress and continue" → Google OAuth or email
- If user dismisses gate: session saved to localStorage, recovered after signup

---

## Screen 2 — Login

Simple. Google OAuth first (one tap), magic link second (email), no password.

```
┌────────────────────────────────────┐
│  ← Back to Nyaya Recall            │
│                                    │
│  Welcome back.                     │
│                                    │
│  [G  Continue with Google]         │
│                                    │
│  ────────  or  ────────────        │
│                                    │
│  [  email@...           ]          │
│  [  Send magic link  →  ]          │
│                                    │
│  No password. No friction.         │
└────────────────────────────────────┘
```

**After login:** Smart routing (same pattern Scribe learned from):
- First-time user → `/onboarding`
- Returning user → `/dashboard`
- Never route returning users to an empty state

---

## Screen 3 — Onboarding (First-time only)

**One screen, 3 questions, then immediate drill. No tours, no carousels.**

```
┌────────────────────────────────────┐
│  Set up takes 60 seconds.          │
│                                    │
│  Which exam?                       │
│  [UPSC CSE] [RAS/RPSC] [BPSC]     │
│  [UPSC IES] [Other state PSC]      │
│                                    │
│  Exam date?                        │
│  [  Pick a date  ▾  ]              │
│                                    │
│  Daily study time?                 │
│  [1 hr] [2 hrs] [3 hrs] [4+ hrs]  │
│                                    │
│  [Start my first drill →]          │
│                                    │
│  Your first diagnostic is ready.   │
└────────────────────────────────────┘
```

**On submit:**
- Creates `prep_config.json` with exam date, hours, exam type
- Redirects directly to `/quiz/[new_session_id]` — first diagnostic
- Dashboard is built passively as user completes sessions
- `?welcome=1` banner fires on first return to dashboard (not during quiz)

**Critical anti-pattern avoided:** Do NOT redirect to `/dashboard` after onboarding. There is nothing on the dashboard yet. Go straight to the product.

---

## Screen 4 — Dashboard (The Daily Return Screen)

This is the screen users see every return visit. It must answer: "Where am I?" and "What do I do right now?"

**Layout:**

```
┌────────────────────────────────────┐
│  Good evening, Rahul.       🔔     │
│  🔥 12-day streak · 47 due today   │  ← streak + due count, always visible
│                                    │
│  ┌─────────────────────────────┐   │
│  │  TODAY'S FOCUS              │   │
│  │  [⚡ Start Today's Drill →] │   │  ← ONE primary CTA
│  │  Polity · 12 q · ~18 min   │   │
│  └─────────────────────────────┘   │
│                                    │
│  YOUR READINESS                    │
│  ┌──┬──┬──┬──┬──┬──┬──┬──┐        │
│  │Po│Ec│Ge│MH│AH│En│ST│CA│        │  ← 8 subject blocks
│  ├──┴──┴──┴──┴──┴──┴──┴──┤        │
│  │  [heatmap grid below]  │        │
│  └────────────────────────┘        │
│                                    │
│  PYQ BROWSER    PRACTICE    MORE   │  ← bottom nav
└────────────────────────────────────┘
```

**Streak + Due Count (top bar):**
- Streak number in 🔥 orange — taps into loss aversion
- "47 due today" in red — creates urgency from Anki's review queue model
- Clicking "47 due" goes straight to quiz, pre-filtered to due questions
- Push notification at 9PM: "Don't lose your 12-day streak" (if no session today)

**Today's Focus card:**
- AI-selected: weakest subtopic by score × PYQ weight
- Shows: subject, estimated questions, estimated time
- Single button: "Start Today's Drill →"
- This is the only CTA that matters on the dashboard

**Heatmap Grid (the gap anxiety engine):**
- 8 subjects, each showing a mini grid of subtopic squares
- Each square = 1 subtopic, colour-coded:
  - `#374151` — Untested (grey)
  - `#EF4444` — Weak (red, score < 40%)
  - `#F59E0B` — Partial (amber, 40–70%)
  - `#22C55E` — Strong (green, > 70%)
- Clicking any subject expands to full subtopic grid
- Free: subject-level grid visible. Pro: subtopic drill-down + weakness rank list

```
Polity (12 subtopics)
[ ][ ][ ][ ][ ][ ]
[■][■][□][□][□][□]     ■ = weak/partial  □ = untested  ■ = strong
```

**Mobile (< 600px):**
- Streak + due count = sticky top bar
- Today's Focus card = full width below
- Heatmap = horizontal scroll, one subject row at a time
- Bottom nav: Home | Practice | PYQs | Progress | Profile

---

## Screen 5 — Quiz Interface (The Core Loop)

This is where users spend 80% of their time. It must be frictionless, single-focus, and habit-forming.

**Single question, full screen, no scroll:**

```
┌────────────────────────────────────┐
│  Polity · Q 4/10      ──────────▸  │  ← thin ambient timer bar, filling
│                                    │
│  Which of the following            │
│  statements about the              │
│  Preamble is/are correct?          │
│                                    │
│  1. The Preamble is not            │
│     enforceable in court...        │
│  2. It was amended by the          │
│     42nd Amendment...              │
│                                    │
│  How confident are you?            │
│  [Sure] [Unsure] [Guessing]        │  ← confidence rating BEFORE options
│                                    │
│  A  Only 1                         │
│  B  Only 2               ← tapped │  ← selected, not yet submitted
│  C  Both 1 and 2                   │
│  D  Neither                        │
│                                    │
│  [Submit Answer →]                 │
└────────────────────────────────────┘
```

**After submit — inline result card (no navigation):**

```
┌────────────────────────────────────┐
│  Polity · Q 4/10      ──────────▸  │
│                                    │
│  ✓ Correct · 14 sec               │  ← green if right, red if wrong
│                                    │
│  Both statements are correct.      │  ← 2-line explanation (free tier)
│  Statement 1: The Preamble is      │
│  not justiciable (Berubari case)   │
│  Statement 2: "Socialist",         │
│  "Secular" added by 42nd...        │
│                                    │
│  [🔒 Full analysis — Pro]          │  ← upgrade teaser if Pro not subscribed
│  • Why each wrong option is wrong  │
│  • Memory hook                     │
│  • Asked in 2019 Prelims (Q.47)    │
│                                    │
│  [Next Question →]                 │
└────────────────────────────────────┘
```

**10-question pause screen (retention = chunking):**
```
┌────────────────────────────────────┐
│  ✓ 10 questions done               │
│                                    │
│  Score this set: 7/10 · 70%        │
│  Avg time: 18 sec/question         │
│  Streak within session: 4 ✓        │
│                                    │
│  Weak spot: Preamble (0/2)         │
│  Strong: Fundamental Rights (3/3)  │
│                                    │
│  [Continue — 10 more →]            │
│  [Save & Exit]                     │
└────────────────────────────────────┘
```

**End-of-session summary:**

```
┌────────────────────────────────────┐
│  Session complete 🎉               │
│                                    │
│  Polity  ·  20 questions           │
│  Score: 14/20  ·  70%             │
│  Time: 6 min 12 sec                │
│  🔥 Streak protected!              │
│                                    │
│  NEEDS REVIEW (3)                  │
│  • Preamble amendments     0/2 ✗   │
│  • Emergency provisions    1/3 ✗   │
│  • Directive Principles    1/2 ✗   │
│                                    │
│  [Drill weak topics now →]         │
│  [Back to dashboard]               │
└────────────────────────────────────┘
```

**Timer rule:** Thin progress bar, left to right, fills over 90 seconds. No countdown number shown. Post-session shows "avg X sec/question." This gives UPSC-relevant time pressure data without inducing panic.

**Confidence signal usage:** `Sure/Unsure/Guess` stored per answer. The algorithm increases review frequency for `Sure + Wrong` pairs (overconfidence is a prelims killer). This is shown back to the user weekly: "You were 'Sure' on 8 questions you got wrong — these are your dangerous blind spots."

---

## Screen 6 — Progress / Analytics

**Free tier view:**
- Subject-level scores only (8 bar charts)
- Total questions attempted, streak calendar
- "14 red subtopics in Polity — upgrade to see which ones"

**Pro tier view:**

```
┌────────────────────────────────────┐
│  YOUR READINESS MAP                │
│                                    │
│  POLITY  (38% ready)               │
│  [full 41-subtopic heatmap grid]   │
│                                    │
│  Highest risk subtopics:           │
│  🔴 Emergency Provisions  (0%)     │
│  🔴 Preamble amendments   (14%)    │
│  🟠 DPSP                  (42%)    │
│                                    │
│  STUDY QUEUE (AI-ranked)           │
│  1. Emergency Provisions    [Drill]│
│  2. Preamble amendments     [Drill]│
│  3. 42nd Amendment          [Drill]│
│                                    │
│  Session history ▾                 │
└────────────────────────────────────┘
```

**Overconfidence Report (Pro, shown weekly):**
- "8 questions where you said 'Sure' but got wrong"
- Lists them as a drill set
- This is a unique insight no competitor offers

---

## Screen 7 — PYQ Browser (Existing, UI polish only)

Keep the year → subject → topic drill-down. Add:
- Free: answer revealed, no explanation
- Pro: full explanation card after each answer
- Upgrade teaser: "See why each wrong option is wrong — Recall Pro"
- Show PYQ frequency badge on subtopic squares in progress heatmap

---

## Screen 8 — Leaderboard (Social Hook)

Competitive UPSC aspirants are the core demographic. Even a small leaderboard matters.

```
┌────────────────────────────────────┐
│  TODAY'S LEADERBOARD               │
│                                    │
│  #1  Priya_IAS       142 q  🔥28   │
│  #2  Aditya_Delhi     98 q  🔥14   │
│  #3  Neha_Rajasthan   87 q  🔥7    │
│  ──────────────────────────        │
│  #47 You               23 q  🔥12  │
│                                    │
│  Questions answered today          │
│  [Try to crack top 10 →]           │
└────────────────────────────────────┘
```

- Ranking by: questions answered today (free metric, not score — avoids cheating incentive)
- Show user's own rank always (even if #847)
- Weekly rank resets every Monday morning (Sunday night urgency)
- First leaderboard launch can be simple: just top 10 + your rank

---

## Freemium Gate Architecture

**Free tier gets:**
- All PYQ Browser questions (answer revealed, no explanation)
- 10 adaptive questions/day per subject (AI-generated)
- Subject-level score bars
- Streak + daily rank
- Session summary (score + which topics were weak)

**Pro gate triggers (show at these exact moments, not randomly):**
1. After session end: "See the full explanation for the 6 you got wrong" (when 1+ wrong)
2. In progress page: subtopic heatmap is blurred below subject level, "See all 41 subtopics"
3. In PYQ Browser: after each answer, explanation card is locked
4. After overconfidence detected: "'Sure' on 3 wrong answers — see your blind spot report"

**Gate UI principle from Scribe:** Show exactly what's locked and what it costs. No invisible walls.

```
┌────────────────────────────────────┐
│  🔒 Pro Analysis                   │
│                                    │
│  • Why option B is wrong           │
│    (not just what's correct)       │
│  • Memory hook for this fact       │
│  • This appeared in Prelims 2019   │
│                                    │
│  ₹3,999/year · ₹333/month         │
│  [Unlock Recall Pro →]             │
│                                    │
│  Or: share with 3 friends          │
│  for 7 days free                   │
└────────────────────────────────────┘
```

---

## Navigation Architecture

**Desktop sidebar (≥ 768px):**
```
NYAYA RECALL
─────────────
🏠 Dashboard
⚡ Practice
📚 PYQ Browser
📊 Progress
🏆 Leaderboard
─────────────
👤 Profile
💎 Go Pro
```

**Mobile bottom nav (< 768px):**
```
[🏠 Home] [⚡ Practice] [📚 PYQs] [📊 Progress] [👤 Profile]
```
- ⚡ Practice = most-used, centre position, slightly larger icon
- FAB-style "Start Drill" button stays persistent over bottom nav when user hasn't drilled today
- After first session of the day: FAB disappears (goal met)

---

## Retention Hooks Summary

| Hook | Where | Mechanism |
|------|-------|-----------|
| 🔥 Streak counter | Top of dashboard, every screen | Loss aversion — "don't break the chain" |
| 🔴 Due count badge | Dashboard top bar | Anki-style urgency — visible debt |
| Heatmap red squares | Dashboard + Progress | Gap anxiety → pulls into drill |
| 10-question pause | Mid-session | Chunking — natural stop without abandoning |
| Overconfidence report | Weekly, Pro | Unique insight no competitor has |
| Leaderboard rank | Dashboard widget | Competitive UPSC aspirant psychology |
| 9PM push notification | If no session today | "Don't lose your streak" — proven by Duolingo |
| Session streak | Within quiz | Mini-streaks ("4 in a row ✓") create flow |
| Sunday night rank reset | Leaderboard | Weekly urgency spike |

---

## Design System

**Extend the existing dark theme, don't replace it.**

| Token | Value | Use |
|-------|-------|-----|
| `bg-base` | `#0D0D0F` | Main background |
| `bg-card` | `#111827` | Card backgrounds |
| `border` | `#1F2937` | All card borders |
| `text-primary` | `#F9FAFB` | Headings |
| `text-muted` | `#6B7280` | Secondary text |
| `accent-blue` | `#3B82F6` | Primary CTAs, links |
| `accent-green` | `#22C55E` | Correct, strong, streak |
| `accent-amber` | `#F59E0B` | Partial, in-progress |
| `accent-red` | `#EF4444` | Weak, wrong, due count |
| `accent-orange` | `#F97316` | Streak fire, urgency |

**Component additions needed (on top of current Tailwind):**
- `<HeatmapGrid>` — 205 squares (8 subjects), colour-coded, clickable
- `<StreakBadge>` — fire emoji + number, pulse animation when streak at risk
- `<DueBadge>` — red pill with count, clicks to quiz
- `<ConfidenceSelector>` — Sure/Unsure/Guess, 3 equal-width buttons
- `<AmbientTimer>` — thin horizontal bar, 0→100% fill over 90 sec, no number
- `<PauseScreen>` — mid-session stats modal, not a page navigation
- `<GateCta>` — lock icon + what's behind it + price, used in 4 places
- `<LeaderboardRow>` — rank + username + count + streak, highlight own row

---

## Implementation Sequence

Phase 1 (Sprint 4, ~3 days) — Core retention loop:
1. Dashboard redesign: streak + due count + heatmap grid + today's focus card
2. Quiz interface: confidence selector + ambient timer + inline result card + 10Q pause
3. End-of-session summary with drill-weak-topics CTA
4. Bottom nav mobile restructure

Phase 2 (Sprint 5, ~2 days) — Acquisition:
1. Landing page: 5-question demo + signup gate
2. Onboarding: 3-question form → immediate drill redirect
3. Smart routing after login (by exam focus)

Phase 3 (Sprint 6, ~2 days) — Retention:
1. Streak counter + push notifications
2. Leaderboard (basic: today's questions answered)
3. Overconfidence report (weekly, Pro)

Phase 4 (Sprint 7, ~2 days) — Monetisation:
1. Pro gate UI at 4 trigger points
2. `/pricing` page
3. Upgrade flow (Razorpay — starts Sprint 4 KYC)

---

## Confirmed Decisions (2026-06-15)

1. **Leaderboard: FREE** — social growth hook; Pro gets weekly rank history + subject sub-leaderboards.

2. **Question source: pre-built question bank** — no per-user AI calls for standard practice. See `plans/question_bank_architecture.md` for full schema and serving algorithm. AI generation is a last-resort fallback only for subtopics with < 5 questions in bank.

3. **Streak shield: adaptive, user-controlled.** Default = 1 miss/week grace. User can set 0 (strict mode) or 2 (lenient) from Profile → Accountability settings. Weekly reset every Monday. NOT hardcoded — stored in `streak_config` table per user.

4. **Usernames: auto-generated handles (editable).** Format: `[adjective][upsc_term][number]` e.g. `SwiftPolity_42`, `BoldEconomy_07`. Editable in Profile. Shown on leaderboard, not real name.
