# FLARE — Implementation Plan
Source of truth for build order and scope. Companion to `SCIENTIFIC-VALIDATION-DOSSIER.md`.

## Repository layout
```
docs/                      validation dossier, implementation plan, demo script
backend/
  engine/                  pure science layer (no I/O)
    loc.py                 LOC(P) boundary + gravity/flow modifiers
    hazard.py              Fire Hazard Vector derivation
    epistemics.py          Observed/Interpolated/Extrapolated/Insufficient + coverage
    pareto.py              non-dominated sort
    similarity.py          experiment-to-query similarity ranking
  data/experiments.json    curated seed database (NTRS-referenced records)
  app/main.py              FastAPI: /scenario /evidence /ask /pareto /counterfactual /validate /experiments
  tests/                   engine unit tests (assert dossier values)
frontend/
  src/screens/             TradeSpace, EvidenceExplorer, AIScientist, Validation
  src/api.ts               typed REST client
README.md
```

## Build order (approved plan)
1. **Phase 0 — dossier** (done first): `docs/SCIENTIFIC-VALIDATION-DOSSIER.md`
2. **Phase 1 — engine + tests:** pure Python science layer; unit tests assert the exact values proven in the dossier (LOC anchors, epistemic labels, pO₂, Pareto, similarity, citation verification).
3. **Phase 2 — seed data:** 20-record experiment database, every record NTRS-referenced.
4. **Phase 3 — API:** FastAPI endpoints over the engine + JSON database.
5. **Phase 4 — frontend:** 4 screens, D3 trade-space with LOC boundary, evidence cards, AI chat panel (offline demo mode when no LLM key), validation panel.
6. **Phase 5 — verification:** engine tests green, API smoke-tested, frontend built, live browser check.

## Scope gates
- MVP gate: Trade Space + Evidence Explorer + engine = submittable.
- Stretch (deferred): NTRS auto-ingestion prototype, smoldering mode, multi-module Fire Danger Index.

## Commands
- Backend tests: `py -m pytest backend/tests -q`
- API server: `py -m uvicorn backend.app.main:app --port 8787`
- Frontend dev: `npm run dev` (in `frontend/`), build: `npm run build`
