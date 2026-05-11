---
Feature: Remote Access — Use the app from any network, any device
Status: Planned
Priority: Medium (not needed for 10-day sprint, high value post-exam)
Trigger: User needs phone access outside home WiFi (library, coaching, travel)
---

## Problem

Currently the app only works when the phone is on the same WiFi as the Mac.
Outside that network (4G, office WiFi, coaching centre) — nothing loads.

---

## Options compared

### Option 1 — Tailscale (RECOMMENDED)
**What it is:** A free personal VPN that connects your devices privately over the internet.
Install it on your Mac and phone. They form a private network. Your phone can always reach
your Mac — from anywhere, any network — as if they were on the same WiFi.

| | |
|--|--|
| Cost | Free (personal use, up to 3 devices) |
| Setup time | 10 minutes |
| Speed | Excellent — direct peer-to-peer when possible |
| Works on | iOS, Android, Mac, Windows |
| Complexity | Zero — install, sign in, done |
| Code changes needed | None |

**How it works in plain English:**
Tailscale gives your Mac a permanent private IP (like `100.x.x.x`).
Your phone always finds your Mac at that IP, regardless of which network either is on.
You open `http://100.x.x.x:3000` on your phone instead of `192.168.x.x:3000`.

**Limitation:** Your Mac must be awake and running the servers. Lid-closed = offline.

---

### Option 2 — Cloudflare Tunnel
Exposes the app to the public internet via a Cloudflare proxy URL (e.g. `https://upsc-xyz.trycloudflare.com`).
Free, no account needed for temporary tunnels.

| | |
|--|--|
| Cost | Free |
| Setup | 5 minutes per session (URL changes each time unless you have an account) |
| Speed | Good (adds ~50ms latency through Cloudflare) |
| Security | Public URL — anyone with the link can access your app and data |

Not recommended — your personal prep data (sessions, profile, attestation results) would be
on a public URL. Wrong tradeoff.

---

### Option 3 — Deploy to a VPS (cloud server)
Host the entire app on a cheap server (DigitalOcean, Hetzner, Railway).
Proper remote access, always on, no Mac dependency.

| | |
|--|--|
| Cost | $5–12/month |
| Setup | 2–4 hours (Docker, nginx, SSL, cloud DB) |
| Speed | Fast, always available |
| Complexity | Significant — DevOps work for your friend |

**Post-exam recommendation:** If this project grows into something real (multi-user, public),
this is the right path. The codebase is already structured for it — SQLite → Postgres is
one config change, ChromaDB → hosted vector DB is one client swap.

**Not for the 10-day sprint.**

---

## Recommendation

**Now (10-day sprint):** Tailscale. 10-minute setup, zero cost, zero code changes.

**Post-exam if project grows:** VPS deployment. Budget 1 weekend, delegate to friend.

---

## Tailscale setup steps (when ready)

**On Mac:**
1. Download Tailscale from tailscale.com
2. Sign in with Google/GitHub
3. Note your Mac's Tailscale IP (shows in menu bar, starts with `100.`)

**On phone:**
1. Install Tailscale app (iOS/Android)
2. Sign in with the same account
3. Enable Tailscale

**Access the app:**
- Open `http://100.X.X.X:3000` on phone (use your Mac's Tailscale IP)
- Everything works — same WiFi or 4G, anywhere in India

**One small code change needed:**
The backend currently has CORS set to `allow_origins=["*"]` — already open.
No changes needed.

---

## What changes if we go VPS later

- `data/prep_profile.json` + `data/study_plan.json` → move into DB (2 new tables)
- SQLite → PostgreSQL (one connection string change in `.env`)
- ChromaDB local → Qdrant cloud or Pinecone (one client swap in `scripts/embedder.py`)
- Add nginx reverse proxy in front of FastAPI
- Add SSL via Let's Encrypt (free)
- `user_id = 'user_1'` → proper JWT auth (biggest lift, ~1 day of work for friend)

---

## Merge condition
Build Tailscale setup after exam (post May 20).
VPS deployment: plan separately when/if project goes multi-user.
