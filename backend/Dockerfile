# Container image for Devthorium's ("Nyaya Recall") FastAPI backend, for deploying to
# Google Cloud Run. Scaffolding only -- does not build or deploy anything by itself. See
# ../docs/migration/03_gcp_cloud_run_vercel_deploy.md for the exact commands Rahul runs
# himself.
#
# Build context is the REPO ROOT, not backend/ -- server.py adds ../scripts to sys.path
# and imports batch_analyse/plan_generator/priority_scorer/score_engine/self_attestation
# from there (verified via grep across backend/*.py, backend/routes/*.py), so scripts/
# must be present in the image alongside backend/. Build with:
#   docker build -f backend/Dockerfile -t nyaya-recall-backend .
#
# requirements.txt here is a NEW, minimal file (backend/requirements.txt) -- there was no
# backend-specific requirements file before this; scripts/requirements.txt is the
# ingestion pipeline's file (chromadb + sentence-transformers + torch + pdfplumber +
# pytesseract + ...) and pulling all of that into the always-on API service's image would
# be a multi-GB image for packages the API process never imports. Verified by grepping
# every import in backend/**/*.py and the 5 scripts/ modules it actually imports at
# runtime (batch_analyse, plan_generator, priority_scorer, score_engine,
# self_attestation, db_helper): none of them import torch/sentence_transformers/
# pdfplumber/pytesseract/pdf2image/docx/bs4 -- those are only used by the separate
# ingestion scripts (ingest.py, ingest_pyq.py, ...), which never run inside this
# container. If a future backend route starts importing an ingestion-only module, this
# file needs a matching addition -- it will fail loudly at import time (ModuleNotFoundError),
# not silently.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY scripts/ scripts/

# data/ (upsc.db, prep_profile.json, etc.) and backend/vector_store/ (Chroma) are
# intentionally NOT copied in -- see .dockerignore. On Cloud Run these paths are GCS
# FUSE volume mounts (see the deploy doc); locally they're the repo's own directories.

ENV PORT=8000
EXPOSE 8000

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
