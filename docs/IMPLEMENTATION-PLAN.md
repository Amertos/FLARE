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
    citations.py           server-side citation verification
  data/experiments.json    curated seed database (20 NTRS-referenced records)
  app/main.py              FastAPI: /api/scenario /api/tradespace /api/experiments
                           /api/ask /api/pareto /api/counterfactual /api/validate
                           /api/methodology /api/health
  app/methodology.py       known limitations + future work + provenance, served to the UI
  tools/                   reproduce_dossier_log.py — regenerates dossier §6
  tests/                   engine + API tests (assert the dossier values)
frontend/
  src/screens/             TradeSpace, EvidenceExplorer, AIScientist, Validation, Methodology
  src/api.ts               typed REST client
LICENSE
README.md
```

## Build order (approved plan)
1. **Phase 0 — dossier** (done first): `docs/SCIENTIFIC-VALIDATION-DOSSIER.md`
2. **Phase 1 — engine + tests:** pure Python science layer; unit tests assert the exact values proven in the dossier (LOC anchors, epistemic labels, pO₂, Pareto, similarity, citation verification).
3. **Phase 2 — seed data:** 20-record experiment database, every record NTRS-referenced.
4. **Phase 3 — API:** FastAPI endpoints over the engine + JSON database.
5. **Phase 4 — frontend** (done): 5 screens — D3 trade-space with LOC boundary and hatched extrapolation regions, evidence cards, engine-grounded answer panel (deterministic; no LLM is called), validation panel, methodology panel.
6. **Phase 5 — verification** (done): engine + API tests green (`py -m pytest backend/tests -q`, 95 tests), dossier §6 log regenerated from the shipped code, API smoke-tested, frontend built, live browser check of every screen.
7. **Phase 6 — security pass** (done): input contract, CORS allow-list, CI least privilege, secret and primitive scans, dependency audit. Two findings fixed; accepted risks stated in [SECURITY-NOTES.md](SECURITY-NOTES.md).
8. **Phase 7 — submission hardening** (done): the items below under "Phase 7", all verified against the running product rather than the build log alone.

## Phase 7 — submission hardening (done)

Work driven by reading the product as a reviewer would, and written up in the dossier
where it changes a claim:

8. **The UI had never been styled.** Every screen is written in Tailwind utility classes
   (`bg-slate-900`, `grid lg:grid-cols-[1fr_340px]`), but Tailwind was not installed and
   `index.css` still carried the Vite starter rules — a 1126 px centred column. The build
   was green and the screens “worked”, which is exactly why the static checks missed it.
   Tailwind v4 is now wired through `@tailwindcss/vite`; the starter CSS is gone.
9. **`/api/ask` did not read the question.** The input box accepted text and the answer
   ignored it — a promise the product could not keep. It now routes the question through an
   explicit keyword model (`engine/intents.py`, 12 intents plus an out-of-scope route) and
   returns the routing decision with the answer. No model is called; the router is inspectable.
10. **A specification record was presented as fire evidence** (dossier §6.1).
    `engine/records.py` classifies every record as `experiment` / `historical` /
    `specification` from its own fields; only `experiment` rows may be cited as supporting
    evidence, and `/api/experiments` labels every row.
11. **The Pareto panel did not exist** although README and the demo script claimed it. It
    now renders, with the weight slider and a deliberate dominated control pair so the
    frontier visibly does work.
12. **The evidence cards showed `NTRS undefined`** — the client read `ntrs_id` while the
    database carries `source_type` / `source_id`. The label is now source-aware (NTRS, PMC,
    journal, NASA History).
13. **Citation chips did nothing** (they were DOM-anchored to another screen). They now
    switch to Evidence and open the cited record.
14. **Decision memo export** (`/api/report`, `app/report.py`): one page carrying the state,
    label, vector, boundary, crew side, cited sources, sensitivity, backtest and limitations.
15. **Shareable state.** The address bar carries the atmosphere and the screen; a state can
    be handed to a reviewer as a link.
16. **Accessibility and honesty pass.** Tabs are a real `tablist`, every slider and select is
    labelled, focus is visible, the map carries a description, and the copy states that no
    language model is called instead of leaving “AI Scientist” to imply one.

17. **Freefall Lab** (`engine/flame.py`, `/api/flame`, `screens/Freefall.tsx`, `viz/`): the
    challenge's own image, made legible and falsifiable — a 3D hazard surface with the LOC ridge
    and the edge of the calibration envelope as a hatched wall, a flame chamber that morphs
    sphere↔teardrop with gravity and self-extinguishes below the boundary, and the µg-vs-1g
    margin crossover. The physics lives in the engine (unit-tested, cited), the visual layer only
    renders its output, three.js loads as its own chunk, and `?no3d=1` degrades the screen to
    numbers. Scope gate met without weakening any earlier claim: the 3D is labelled a schematic
    of published regimes, not a CFD solution (limitation L8).

## Scope gates
- MVP gate: Trade Space + Evidence Explorer + engine = submittable. **Met.**
- Stretch shipped: the Freefall Lab 3D screen (phase 17) — the challenge's visual question,
  answered from the same boundary the rest of the product uses.
- Stretch (deferred, and surfaced in the product's Methodology screen rather than implied away): NTRS auto-ingestion, smoldering mode, multi-module Fire Danger Index.

## Documentation rule

The dossier is the published record, but it must not describe a product that does not exist. Two things keep them aligned:

1. The known-limitations list lives in `backend/app/methodology.py` and is served at `/api/methodology`, so the UI cannot show something the engine does not state. A unit test asserts all eight §4.7 limits are present, including L8 (the 3D screen is a schematic, not a CFD solution).
2. The §6 test log is regenerated by `backend/tools/reproduce_dossier_log.py` against the shipped code. If the published log and the engine ever disagree, the script is the tiebreaker.

## Commands
- Backend tests: `py -m pytest backend/tests -q`
- Regenerate the dossier §6 test log: `py -m backend.tools.reproduce_dossier_log`
- API server: `py -m uvicorn backend.app.main:app --port 8787`
- Frontend dev: `npm run dev` (in `frontend/`), build: `npm run build`
- CI: `.github/workflows/ci.yml` runs the test suite and the frontend build on every push
