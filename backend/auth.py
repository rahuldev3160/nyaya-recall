"""JWT auth middleware for Supabase. Swap _get_user_id() Depends() stubs for Depends(get_current_user) when ready."""
from __future__ import annotations
import os

import jwt
from fastapi import Header, HTTPException

# TODO: set in .env when Supabase project created (supabase.com → Settings → API → JWT Secret)
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


def get_current_user(authorization: str = Header(...)) -> str:
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(status_code=503, detail="Auth not configured — SUPABASE_JWT_SECRET missing from .env")
    try:
        token = authorization.removeprefix("Bearer ").strip()
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload["sub"]  # Supabase UUID — use as user_id throughout
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
