# FLARE — Fire & Life Atmosphere Risk Explorer

Decision-support system for exploring spacecraft and habitat atmospheres, built for the
**NASA Space Apps Challenge 2026 — "Flame in Freefall"**.

Given an atmosphere state, FLARE answers: *what does NASA's microgravity combustion
experimental record imply about fire behavior and crew physiology, how confident is each
statement, and where does the experimental evidence end?*

## What it does

- **Trade Space** — pressure × O₂ map with the LOC (limiting oxygen concentration)
  flammability boundary, a crew-safe band, and a hatched "no NASA data" extrapolation zone.
- **Evidence Explorer** — experiment cards (Saffire, BASS-II, SoFIE-MIST, …) linked to their
  real NTRS sources.
- **AI Scientist** — retrieval-augmented answers whose citation IDs are verified server-side
  against the database; fabricated citations are dropped, not displayed. Runs offline with no
  LLM key.
- **Validation** — leave-one-out backtest of the engine against NASA's own held-out experiments.
- **Pareto frontier** — fire-safety vs EVA weighting reveals a different optimum; FLARE never
  declares a single "best" atmosphere.
- **Methodology** — the known-limitations list, the work that is deliberately *not* built, the
  model-governance rules and the data-provenance table, served from the engine so the product
  and the written record cannot drift apart.

## Design rules (enforced in code)

1. No single fire-risk number — outputs are a 5-component Fire Hazard Vector.
2. Every output carries an evidence label: Observed / Interpolated / Extrapolated / Insufficient.
3. Every experiment record links to its NTRS source.
4. The engine is deterministic, and **no language model is called anywhere in this build**.
   Answers are composed from engine outputs and database records; every citation ID is verified
   server-side and fabricated ones are flagged rather than shown.
5. The flammability boundary is rendered only where the LOC curve was calibrated. Outside that
   envelope the map is hatched, not coloured, so no pixel implies evidence that does not exist.

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
  app/main.py              FastAPI endpoints
  app/methodology.py       known limitations, future work and provenance served to the UI
  tools/                   reproduce_dossier_log.py — regenerates the published test log
  tests/                   engine + API tests asserting the dossier values
frontend/
  src/screens/             TradeSpace, EvidenceExplorer, AIScientist, Validation, Methodology
  src/api.ts               typed REST client
.github/workflows/ci.yml   tests + dossier log + frontend build on every push
LICENSE                    MIT
```

## Running it

Backend (port 8787):

```bash
py -m pip install -r backend/requirements.txt
py -m uvicorn backend.app.main:app --port 8787
```

Frontend (port 5173):

```bash
cd frontend
npm install
npm run dev        # dev server
npm run build      # production build
```

Tests (42 currently):

```bash
py -m pytest backend/tests -q
```

Regenerate the published test log in [docs/SCIENTIFIC-VALIDATION-DOSSIER.md](docs/SCIENTIFIC-VALIDATION-DOSSIER.md) §6 from the shipped code:

```bash
py -m backend.tools.reproduce_dossier_log
```

CI runs both, plus the frontend build, on every push — see [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Documentation

- [docs/SCIENTIFIC-VALIDATION-DOSSIER.md](docs/SCIENTIFIC-VALIDATION-DOSSIER.md) — full
  derivations, provenance table, and executed test log.
- [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) — build order and scope gates.
- [docs/demo-script.md](docs/demo-script.md) — 4-minute demo script.
- [docs/SECURITY-NOTES.md](docs/SECURITY-NOTES.md) — security pass: surface, enforced
  controls, accepted risks, and how each control was checked.

## Scope

FLARE supports **relative comparison of atmospheres**. It is not an absolute risk assessor and
never issues operational commands.
