# Deploying Nyaya Recall to Cloud Run + Vercel

**Scaffolding only.** Nothing in this doc or the `infra/cloud-run-scaffold` branch
provisions any GCP/Vercel resource, spends money, or touches DNS. These are the exact
commands Rahul runs himself, in order.

Supersedes `docs/migration/02_infra_architecture.md`'s "Railway + Supabase Postgres"
target architecture for the *hosting* layer specifically — that doc's Supabase Auth design
(JWT, `user_profiles`, RLS) is unaffected and still applies; only "where the FastAPI
service and Next.js app run" changes, from the Railway/Vercel pairing that doc assumed to
Cloud Run/Vercel.

## 0. What changed in code to make this possible

- `backend/Dockerfile` (new) + `backend/requirements.txt` (new, minimal — see the
  Dockerfile's own comment for why it's not `scripts/requirements.txt`).
- `.dockerignore` (new, repo root).
- `web/next.config.ts`: the backend proxy rewrite's destination was hardcoded to
  `http://localhost:8000` — now reads `process.env.BACKEND_API_URL`, defaulting to that
  same localhost value for local dev. Set `BACKEND_API_URL` on Vercel (step 3) to the
  Cloud Run URL from step 2.
- `backend/nyaya_core_client.py` already reads `NYAYA_CORE_API_URL` from env (was already
  configurable, default `http://127.0.0.1:8420`) — set it in step 2 once nyaya-core has a
  real URL. **If nyaya-core is deployed with restricted (IAM) ingress, this client will
  get 403s** — it sends no auth header today. See nyaya-core's own `docs/DEPLOY.md` §4 for
  the full explanation; either build the identity-token auth into this client first, or
  accept `routes/nyaya_pyq_drill.py`'s PFRDA/EPFO drill breaking until it's built.
- `CORS_ORIGINS` (`backend/server.py`) was already env-driven, default
  `http://localhost:3000,http://localhost:3001` — set it in step 2 to the real frontend
  domain.

## Prerequisites

- GCP project + billing account (Rahul's own) with `run.googleapis.com`,
  `artifactregistry.googleapis.com`, `storage.googleapis.com` enabled (see nyaya-core's
  `docs/DEPLOY.md` prerequisites — same one-time steps, same project if you want one bill).
- A Vercel account, linked to the GitHub repo.
- FluxDev.in DNS access (registrar dashboard).
- **Verify current Cloud Run free tier limits/region eligibility at
  cloud.google.com/run/pricing and Vercel Hobby's terms at vercel.com/docs/limits before
  deploying** — both can change; this doc was written 2026-09-18.

## 1. Create the GCS bucket and upload existing data (one-time)

```bash
gcloud storage buckets create gs://nyaya-recall-data --location=asia-south1 --uniform-bucket-level-access

# From the repo root, with the local data/ and vector_store/ as they exist today:
gsutil -m rsync -r data       gs://nyaya-recall-data/data
gsutil -m rsync -r vector_store gs://nyaya-recall-data/vector_store
```

## 2. Deploy the backend to Cloud Run

From the repo root (Dockerfile build context includes `scripts/` — see
`backend/Dockerfile`'s own comment):

```bash
gcloud run deploy nyaya-recall-backend \
  --source . \
  --dockerfile backend/Dockerfile \
  --region asia-south1 \
  --allow-unauthenticated \
  --add-volume=name=data,type=cloud-storage,bucket=nyaya-recall-data \
  --add-volume-mount=volume=data,mount-path=/app/data \
  --set-env-vars="DB_PATH=/app/data/data/upsc.db,CHROMA_PATH=/app/data/vector_store,CORS_ORIGINS=https://recall.fluxdev.in,ANTHROPIC_API_KEY=<key>,SUPABASE_URL=<url>,SUPABASE_ANON_KEY=<key>,SUPABASE_JWT_SECRET=<secret>,NYAYA_CORE_API_URL=<nyaya-core Cloud Run URL, if deployed>,AI_MODEL_FAST=claude-haiku-4-5-20251001,AI_MODEL_SMART=claude-sonnet-4-6" \
  --memory=1Gi \
  --execution-environment=gen2
```

Notes:
- `--allow-unauthenticated` here (unlike nyaya-core) because the frontend's browser-side
  calls need to reach this API directly over the public internet — this service is meant
  to be public, unlike nyaya-core. Real access control for user data is the Supabase JWT
  check in `backend/auth.py`, not network-level restriction.
- `--dockerfile backend/Dockerfile` (not the default `Dockerfile` at repo root, which
  doesn't exist for this repo — `--source .` needs this flag to find it, or use
  `gcloud builds submit --tag <image> -f backend/Dockerfile .` + `gcloud run deploy
  --image <image>` as an alternative two-step flow if `--source`+`--dockerfile` together
  behaves unexpectedly in your `gcloud` version — verify against `gcloud run deploy
  --help` at deploy time, flag syntax has changed across `gcloud` versions before.
- `DB_PATH`/`CHROMA_PATH` above assume the mount path layout from the `gsutil rsync`
  commands in step 1 (`data/data/upsc.db`, `data/vector_store/...` under the bucket root
  as mounted at `/app/data`) — adjust to match whatever prefixes you actually used.
- The deploy prints a URL like `https://nyaya-recall-backend-xxxxx-uc.a.run.app` — this is
  `BACKEND_API_URL` for step 3.
- If `INTERNAL_API_KEY_ARENA` / `INTERNAL_API_KEY_SCRIBE_RBI` are in use (per
  `.env.example`'s note — these need Rahul's explicit approval per
  `backend/routes/internal_arena.py`'s approval note), add them to `--set-env-vars` too.

## 3. Deploy the frontend to Vercel

```bash
cd web
vercel link          # first time only — links this directory to a Vercel project
vercel env add BACKEND_API_URL production        # paste the Cloud Run URL from step 2
vercel env add NEXT_PUBLIC_SUPABASE_URL production
vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY production
vercel --prod
```

Then in the Vercel dashboard → Project → Settings → Domains: add `recall.fluxdev.in`, and
follow Vercel's shown CNAME/A-record instructions in FluxDev.in's registrar DNS settings.
Vercel Hobby is non-commercial-use only per its terms — acceptable for now per the task
this scaffolding was built for, but re-check before this product takes payments.

## 4. Smoke test before treating this as live

1. Open `https://recall.fluxdev.in` → sign in → confirm the dashboard loads (proves
   Supabase auth + the Vercel→Cloud Run proxy rewrite both work).
2. Start a quiz session → confirms ChromaDB (GCS-FUSE-mounted) is readable.
3. If PFRDA/EPFO drill is tested: confirms whether nyaya-core's IAM restriction (if any)
   is blocking it, per the auth note in §0 above.
4. Only then point any *existing* production DNS at the new deployment, keeping Railway
   live until this is verified stable — same "don't cut over until proven" discipline
   Descriptive-exams' `docs/PORTABLE_HOSTING.md` already documents for its own move.
