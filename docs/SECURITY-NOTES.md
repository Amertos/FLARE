# FLARE — security pass (007)

Scope: the shipped artifact — FastAPI service (`backend/app`), pure engine (`backend/engine`),
curated dataset (`backend/data`), React client (`frontend/src`), CI workflow.

This is a read-only, stateless decision-support demo. There is no authentication, no user data,
no database, no file upload, no session and no outbound network call at request time. The
threat model that follows is therefore small, and this document states both what is enforced
and what is deliberately accepted, rather than implying a hardening level the build does not have.

## Attack surface

| Entry point | Methods | Notes |
|---|---|---|
| `/api/scenario`, `/api/tradespace`, `/api/experiments`, `/api/pareto` | GET | Query parameters only |
| `/api/validate`, `/api/methodology`, `/api/health` | GET | No parameters |
| `/api/ask`, `/api/counterfactual` | POST | JSON body, bounded by a Pydantic model |

No endpoint accepts a path, a filename, a URL, a shell string or a free-form identifier that
reaches anything but the in-memory engine. There is no SQL and no filesystem path built from
request input; the dataset path is a module constant (`backend/data/__init__.py`).

## Enforced controls

1. **Closed vocabularies.** `gravity` and `material_class` are `Literal` types, so anything
   outside the four gravity regimes / four material classes is rejected with `422` before the
   engine sees it. An import-time `assert` fails the process if the API vocabulary and the
   engine's `MATERIAL_CLASSES` ever drift apart.
2. **Bounded numerics.** Every numeric parameter and every `Field` carries `ge`/`le` bounds tied
   to the physically meaningful range (dossier §2.1): 1–30 psia, 0–100 % O₂, 0–5 m/s flow,
   −20–60 °C, 0–1 fire weight, ±100 pts Δ O₂. Out-of-range input is `422`, not a clamped value.
3. **Bounded text.** `question` is 3–500 characters; it is never evaluated, interpolated into a
   query, or rendered as markup — it is echoed back in a React text node.
4. **CORS is an allow-list.** Origins are limited to the dev-server origins
   (`http://localhost:5173`, `http://127.0.0.1:5173`), methods to `GET, POST`, and headers to
   `Content-Type` (finding **H1**, fixed — it was `*`).
5. **No server-side error detail.** Unhandled exceptions return Starlette's generic body; no
   traceback, path or environment value is returned to the caller.
6. **No secrets in the repository.** A tracked-file scan for `api_key`/`secret`/`token`/`password`/
   bearer tokens/private keys finds nothing, and there is no LLM client and no key read anywhere
   in the backend. `.gitignore` covers `.env`, logs, `node_modules/` and build output.
7. **No dangerous primitives.** No `eval`, `exec`, `os.system`, `subprocess`, `pickle`,
   `shell=True` or `dangerouslySetInnerHTML` anywhere in tracked source.
8. **CI is least-privilege** (finding **H2**, fixed): `permissions: contents: read`, and no step
   interpolates a pull-request title, branch name or comment body into a shell command.
9. **Dependency posture.** `npm audit` reports 0 vulnerabilities (info/low/moderate/high/critical
   all zero) across the d3/react tree; backend pins exact versions in `backend/requirements.txt`.

## Accepted risks (stated, not hidden)

- **No authentication or authorisation.** Every endpoint is public by design; there is nothing
  user-specific to protect and nothing to write. Adding auth would protect nothing today.
- **No rate limiting.** The service is pure CPU over a 20-record dataset and makes no outbound
  call, so a request cannot amplify or persist. A public deployment behind a real URL should add
  a limiter at the edge; that is a hosting decision, not a property of this code.
- **CORS is not access control.** It restricts browsers only. A non-browser client ignores it.
  The service must not be exposed on an untrusted network expecting CORS to be the control.
- **No transport security.** The demo runs on `127.0.0.1`; TLS is the hosting layer's job.
- **Dependencies are installed into the ambient Python**, not a virtual environment, so
  `py -m pip check` reports conflicts caused by unrelated globally installed packages
  (`spotdl`, `torchvision`). None of them is in `backend/requirements.txt` and none is imported
  by this project. Isolating the project in a venv or `uv` environment is the recommended next
  step if the build is ever run outside this machine.

## What was checked, and how

- Secret/primitive scan: `git ls-files` piped into grep over tracked source (see controls 6 and 7).
- Input validation: `backend/tests/test_engine.py` asserts `422` for unknown material class,
  unknown gravity regime and four out-of-range values, and asserts that an overlong question is
  rejected.
- CORS: a unit test asserts `DELETE` is not an allowed method; a preflight was exercised live
  against the running server and returned only `GET, POST` and `Content-Type`.
- CI: the workflow file was parsed and read end to end; no untrusted input reaches a `run` step.
- Dependencies: `npm audit`, `py -m pip check`.

Re-run these after any change to `backend/app/main.py` or the workflow:

```bash
py -m pytest backend/tests -q
(cd frontend && npm audit)
```
