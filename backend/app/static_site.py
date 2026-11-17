"""Serve the built React console from the same process as the API.

Production hosting for FLARE is one process on one origin: uvicorn serves
``/api/*`` from FastAPI and every other path from the built frontend. That is
what makes the demo deployable to any Python host — Render, Railway, Fly, a
container, a VM — with no second service, no CORS and one URL to share, and it
is what ``make demo`` runs locally.

The mount is added only when a build exists, so the test suite and an API-only
run (``py -m uvicorn backend.app.main:app`` without a build) are unaffected.
Set ``FLARE_STATIC_DIR`` to point at a build somewhere else.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# backend/app/static_site.py -> repository root -> frontend/dist
DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def dist_dir() -> Path | None:
    """The build directory to serve, or None when there is no build."""
    raw = os.environ.get("FLARE_STATIC_DIR")
    candidate = Path(raw).expanduser().resolve() if raw else DEFAULT_DIST
    return candidate if (candidate / "index.html").is_file() else None


def mount_static_site(app: FastAPI) -> Path | None:
    """Mount the built UI at ``/``. Call this AFTER every API route.

    Starlette matches routes in registration order, so a mount at ``/`` placed
    last cannot shadow ``/api/*``; StaticFiles already refuses path traversal
    and serves ``index.html`` for the root path (``html=True``).
    """
    dist = dist_dir()
    if dist is None:
        return None
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
    return dist
