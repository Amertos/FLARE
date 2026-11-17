"""Vercel Python runtime entrypoint.

vercel.json rewrites /api/* to this file; the Python runtime treats the
exported ASGI app as the serverless handler. The import must stay short-paths
because the whole `backend/**` tree is shipped via `includeFiles` — see
vercel.json. No state lives between requests: every endpoint reads
backend/data/experiments.json from the bundled files, which is what makes
serverless hosting work for this product without a database.
"""
from backend.app.main import app
