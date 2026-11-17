"""FLARE API — FastAPI endpoints over the deterministic engine.

Endpoints:
  GET  /api/scenario        hazard vector + evidence for one atmosphere state
  GET  /api/tradespace      P x O2 grid with LOC boundary + coverage layer
  GET  /api/flame           flame regime, fire-front fate and the ug-vs-1g
                            crossover behind the 3D Freefall Lab screen
  GET  /api/experiments     ranked experiments for a query
  POST /api/ask             engine-grounded answer with server-verified citations
                            (deterministic question router; no language model is called)
  GET  /api/pareto          candidate set + Pareto frontier + weighted ranking
  GET  /api/design-search   inverse design: crew O2 floor vs LOC boundary per
                            pressure, crossing pressure solved in closed form
  POST /api/counterfactual  before/after deltas for dO2 / dflow
  GET  /api/validate        leave-out backtest of the engine against the DB
  GET  /api/report          one-page Markdown decision memo for one atmosphere
  GET  /api/methodology     known limitations, future work, provenance
  GET  /api/health
  GET  /                    the built React console (when frontend/dist exists)
"""
from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.data import load_experiments
from backend.engine import (
    hazard_vector,
    loc_percent,
    pareto_front,
    rank_experiments,
    weighted_score,
)
from backend.app.methodology import methodology_payload
from backend.app.report import build_report
from backend.engine.backtest import leave_one_out
from backend.engine.citations import verify_citations
from backend.engine.countermoves import countermoves_payload
from backend.engine.design import design_search_payload
from backend.engine.epistemics import classify, coverage
from backend.engine.flame import flame_payload
from backend.engine.hazard import MATERIAL_CLASSES
from backend.engine.intents import Atmosphere, compose as compose_answer
from backend.engine.missions import missions_payload, scenario_payload
from backend.engine.loc import (
    P_ENVELOPE_KPA,
    epistemic_flag_for_pressure,
    inside_envelope,
)
from backend.engine.records import annotate as annotate_records
from backend.engine.records import partition

app = FastAPI(title="FLARE API", version="1.0.0")
# Extra origins may be appended via the FLARE_CORS_ORIGINS env var
# (comma-separated). The default stays the localhost dev pair; the deployed
# product talks to the API same-origin through api/index.py and needs no CORS.
_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    *(o.strip() for o in os.environ.get("FLARE_CORS_ORIGINS", "").split(",") if o.strip()),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    # The client only ever sends JSON, so the preflight allow-list is narrowed
    # to the one header it needs rather than "*" (security pass, finding H1).
    allow_headers=["Content-Type"],
)

PSI_TO_KPA = 6.89476

# Closed vocabularies. Declaring them as Literal types makes FastAPI reject an
# out-of-set value with a 422 before it can reach the engine, so no unknown
# gravity regime or material class can silently degrade the similarity and
# coverage math (dossier §2.1 lists the four material classes).
Gravity = Literal["microgravity", "lunar", "mars", "earth"]
MaterialClass = Literal["polymer", "textile", "insulation", "composite"]

assert tuple(MATERIAL_CLASSES) == (
    "polymer", "textile", "insulation", "composite"
), "MaterialClass vocabulary drifted from engine MATERIAL_CLASSES"


# Every numeric query parameter is bounded to a physically meaningful range
# (dossier §2.1); a value outside it is a caller error, and FastAPI answers
# 422 rather than feeding it into the model.


def _kpa(pressure_psia: float) -> float:
    return pressure_psia * PSI_TO_KPA


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "experiments": len(load_experiments())}


@app.get("/api/methodology")
def methodology() -> dict[str, Any]:
    """Known limitations, future work, model governance and data provenance.

    The dossier (§8) states that the known-limitations list ships in the
    product UI. This endpoint is the product's single source for it; the
    Methodology screen renders exactly this payload.
    """
    return methodology_payload()


@app.get("/api/missions")
def missions() -> dict[str, Any]:
    """Mission flight scenarios (real-hardware presets), fully evaluated.

    Every entry carries the engine's hazard vector for THE SCENARIO and for a
    1g ground-lab twin at the same non-gravity parameters, plus the deltas —
    the µg-vs-1g risk delta the test engineer asks for, computed by the engine
    rather than hand-written. Preset parameters only; no fire quantity is
    hard-coded here.
    """
    return missions_payload()


@app.get("/api/scenario")
def scenario(
    pressure_psia: float = Query(8.2, ge=1.0, le=30.0),
    o2_pct: float = Query(34.0, ge=0.0, le=100.0),
    gravity: Gravity = "microgravity",
    flow_ms: float = Query(0.2, ge=0.0, le=5.0),
    temperature_c: float = Query(22.0, ge=-20.0, le=60.0),
    material_class: MaterialClass = "polymer",
) -> dict[str, Any]:
    exps = load_experiments()
    vec = hazard_vector(pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
                        material_class)
    label = classify(_kpa(pressure_psia), o2_pct, gravity, material_class, exps)
    cov = coverage(_kpa(pressure_psia), o2_pct, gravity, material_class, exps)
    ranked = annotate_records(
        rank_experiments(_kpa(pressure_psia), o2_pct, gravity, material_class, exps)
    )
    return {
        "inputs": {
            "pressure_psia": pressure_psia,
            "o2_pct": o2_pct,
            "gravity": gravity,
            "flow_ms": flow_ms,
            "temperature_c": temperature_c,
            "material_class": material_class,
        },
        "hazard": vec,
        "evidence_label": label,
        "coverage_pct": round(cov * 100.0, 1),
        "relevant_experiments": ranked[:8],
        "loc": {
            "base_pct": round(loc_percent(_kpa(pressure_psia)), 2),
            "effective_pct": vec["effective_loc_pct"],
            "margin_pct": vec["margin_above_loc_pct"],
            "flag": epistemic_flag_for_pressure(_kpa(pressure_psia)),
        },
    }


@app.get("/api/tradespace")
def tradespace(
    gravity: Gravity = "microgravity",
    flow_ms: float = Query(0.2, ge=0.0, le=5.0),
    temperature_c: float = Query(22.0, ge=-20.0, le=60.0),
    material_class: MaterialClass = "polymer",
    p_min: float = Query(4.0, ge=1.0, le=30.0),
    p_max: float = Query(16.7, ge=1.0, le=30.0),
    o2_min: float = Query(14.0, ge=0.0, le=100.0),
    o2_max: float = Query(45.0, ge=0.0, le=100.0),
) -> dict[str, Any]:
    """P x O2 grid for the heatmap + LOC boundary points."""
    steps_p, steps_o2 = 34, 32
    ps = [p_min + (p_max - p_min) * i / (steps_p - 1) for i in range(steps_p)]
    o2s = [o2_min + (o2_max - o2_min) * i / (steps_o2 - 1) for i in range(steps_o2)]
    grid = []
    for p in ps:
        row = []
        for o2 in o2s:
            vec = hazard_vector(p, o2, gravity, flow_ms, temperature_c, material_class)
            row.append({
                "ignition": vec["ignition"],
                "spread": vec["spread"],
                "persistence": vec["persistence"],
                "heat_release": vec["heat_release"],
                "extinction_margin": vec["extinction_margin"],
                "crew_safe": vec["crew"]["crew_safe"],
            })
        grid.append(row)

    boundary = []
    for p in ps:
        p_kpa = _kpa(p)
        inside = inside_envelope(p_kpa)
        boundary.append({
            "p_psia": round(p, 3),
            "loc_pct": round(loc_percent(p_kpa), 2) if inside else None,
            "flag": "INTERPOLATED" if inside else "EXTRAPOLATED",
        })

    # Comparison grid for the Freefall Lab's 1g ghost surface: the SAME ignition
    # field computed at 1g. Included only when the requested gravity is not 1g
    # itself; it is the µg-vs-1g delta the Freefall Lab is about. Same engine,
    # same modifiers — the only change is the gravity term.
    ghost_grid: list[list[dict[str, Any]]] | None = None
    if gravity != "earth":
        ghost_grid = []
        for p in ps:
            row = []
            for o2 in o2s:
                vec = hazard_vector(p, o2, "earth", flow_ms, temperature_c,
                                    material_class)
                # The ghost surface is drawn BELOW the µg surface, so a viewer
                # sees two translucent sheets and the LOC separation between
                # them; the vertical offset is declared in the UI (\"drawn -2
                # ignition points below\") and is presentation-only.
                row.append({"ignition": vec["ignition"],
                            "height_offset_pct": -2.0})
            ghost_grid.append(row)

    return {
        "p_psia": [round(p, 3) for p in ps],
        "o2_pct": [round(o, 2) for o in o2s],
        "grid": grid,
        "loc_boundary": boundary,
        "ghost_grid_1g": ghost_grid,
        "crew_band": {"po2_min_psia": 2.4, "po2_max_psia": 3.4},
        # Coverage envelope on the P axis. The frontend hatches the region
        # outside it instead of colouring it, so no pixel is coloured where
        # NASA has no measurement (dossier §4.7 L2).
        "p_envelope_kpa": [P_ENVELOPE_KPA[0], P_ENVELOPE_KPA[1]],
    }


@app.get("/api/flame")
def flame(
    pressure_psia: float = Query(8.2, ge=1.0, le=30.0),
    o2_pct: float = Query(34.0, ge=0.0, le=100.0),
    gravity: Gravity = "microgravity",
    flow_ms: float = Query(0.2, ge=0.0, le=5.0),
    temperature_c: float = Query(22.0, ge=-20.0, le=60.0),
    material_class: MaterialClass = "polymer",
) -> dict[str, Any]:
    """Flame regime, front fate and the microgravity-vs-1g crossover.

    Everything the 3D Freefall Lab screen draws comes from here, so the
    animation cannot show a behaviour the published model does not produce.
    The sources for each qualitative statement travel with the payload
    (dossier §4.2), and `front_speed_relative` is in relative units against the
    Saffire-I reference condition rather than m/s.
    """
    return flame_payload(pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
                         material_class)


@app.get("/api/countermoves")
def countermoves(
    pressure_psia: float = Query(8.2, ge=1.0, le=30.0),
    o2_pct: float = Query(34.0, ge=0.0, le=100.0),
    gravity: Gravity = "microgravity",
    flow_ms: float = Query(0.2, ge=0.0, le=5.0),
    temperature_c: float = Query(22.0, ge=-20.0, le=60.0),
    material_class: MaterialClass = "polymer",
) -> dict[str, Any]:
    """Ranked, engine-computed fire-safety levers for one atmosphere state.

    The challenge's second question is "how do we reduce the fire risk". This
    endpoint answers it from the SAME engine the trade-space map uses: every
    lever reports a before/after hazard vector and names the dossier-backed
    quantity that produced its effect, so the panel cannot claim more than
    the model does. A lever the model does not support in this regime is
    returned not-applicable with the reason, never as a 0-delta.
    """
    return countermoves_payload(pressure_psia, o2_pct, gravity, flow_ms,
                                temperature_c, material_class)






@app.get("/api/design-search")
def design_search(
    gravity: Gravity = "microgravity",
    flow_ms: float = Query(0.2, ge=0.0, le=5.0),
    temperature_c: float = Query(22.0, ge=-20.0, le=60.0),
    material_class: MaterialClass = "polymer",
    pressure_psia: float = Query(8.2, ge=1.0, le=30.0),
    p_min: float = Query(4.0, ge=1.0, le=30.0),
    p_max: float = Query(16.7, ge=1.0, le=30.0),
    steps: int = Query(25, ge=2, le=200),
) -> dict[str, Any]:
    """Inverse design: for each cabin pressure, can the crew's O2 floor stay
    below the LOC boundary?

    The trade-space map answers "given this atmosphere, what happens". This
    answers the question a designer starts from: is there ANY atmosphere that
    is both breathable and below the boundary, and if so at what pressure does
    that window open? The crossing is solved in closed form (engine/design.py),
    the rows are the same loc.py/hazard.py functions every other screen uses,
    and the window carries the epistemic flag of the pressure envelope it sits
    in. No recommendation is made: the payload states which mixes satisfy two
    stated constraints, nothing more.
    """
    if p_max <= p_min:
        raise HTTPException(status_code=422, detail="p_max must exceed p_min")
    return design_search_payload(gravity, flow_ms, temperature_c,
                                 material_class, p_min, p_max, steps,
                                 pressure_psia)


@app.get("/api/experiments")
def experiments(
    pressure_psia: float = Query(8.2, ge=1.0, le=30.0),
    o2_pct: float = Query(34.0, ge=0.0, le=100.0),
    gravity: Gravity = "microgravity",
    material_class: MaterialClass = "polymer",
) -> dict[str, Any]:
    exps = load_experiments()
    ranked = rank_experiments(_kpa(pressure_psia), o2_pct, gravity, material_class, exps)
    annotated = annotate_records(ranked)
    evidence, context = partition(annotated)
    return {
        "count": len(annotated),
        "evidence_count": len(evidence),
        "context_count": len(context),
        "results": annotated,
    }


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    pressure_psia: float = Field(8.2, ge=1.0, le=30.0)
    o2_pct: float = Field(34.0, ge=0.0, le=100.0)
    gravity: Gravity = "microgravity"
    flow_ms: float = Field(0.2, ge=0.0, le=5.0)
    temperature_c: float = Field(22.0, ge=-20.0, le=60.0)
    material_class: MaterialClass = "polymer"


@app.post("/api/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    """Evidence-grounded answer that is steered by the question.

    The question is routed by an explicit keyword model (backend/engine/
    intents.py) into an intent, and the intent decides which engine quantities
    are computed and reported. No language model is called: there is no LLM
    client in this build and no API key is read anywhere in the backend, so
    every sentence is composed from engine outputs and database records. The
    routing decision is returned in the payload (`intent`, `intent_matched`,
    `intent_confidence`) so the user can see how the question was understood;
    a question outside the engine's scope is answered as out of scope rather
    than with a confident paragraph about something else.

    Only controlled combustion experiments are cited as supporting evidence;
    specification and historical records are returned separately as context
    (dossier §6.1). Citations are verified against the database in code.
    """
    exps = load_experiments()
    atm = Atmosphere(
        pressure_psia=req.pressure_psia,
        o2_pct=req.o2_pct,
        gravity=req.gravity,
        flow_ms=req.flow_ms,
        temperature_c=req.temperature_c,
        material_class=req.material_class,
    )
    result = compose_answer(req.question, atm, exps)

    ids = {e["experiment_id"] for e in exps}
    check = verify_citations(
        list(result["citations"]) + list(result["context_citations"]), ids
    )

    return {
        "question": req.question,
        "intent": result["intent"],
        "intent_matched": result["intent_matched"],
        "intent_confidence": result["intent_confidence"],
        "answer": result["answer"],
        "citations": result["citations"],
        "context_citations": result["context_citations"],
        "context_kinds": result["context_kinds"],
        "suggested_questions": result["suggested_questions"],
        "fabricated_citations": check["fabricated"],
        "citation_check_ok": check["ok"],
        "engine_summary": result["engine_summary"],
        "mode": "offline-deterministic",
    }


@app.get("/api/pareto")
def pareto(
    fire_weight: float = Query(0.5, ge=0.0, le=1.0),
    gravity: Gravity = "microgravity",
    flow_ms: float = Query(0.2, ge=0.0, le=5.0),
    temperature_c: float = Query(22.0, ge=-20.0, le=60.0),
    material_class: MaterialClass = "polymer",
) -> dict[str, Any]:
    """Candidate atmospheres -> hazard vs crew/EVA benefit -> frontier.

    A-F are the design points a mission architect actually trades (plus the
    Exploration Atmosphere and a 1 atm baseline). G and H are the deliberate
    control pair: the same pressure, 21% vs 28% O2 — the 28% option buys no EVA
    benefit at all and only raises fire hazard, so H is dominated by G and the
    frontier is shown excluding it rather than presenting seven equally valid
    options (dossier §4.7 L4: this is a comparison, not a ranking of winners).
    """
    candidates_def = [
        {"id": "A", "p": 8.2, "o2": 34.0},
        {"id": "B", "p": 9.0, "o2": 31.0},
        {"id": "C", "p": 10.0, "o2": 28.0},
        {"id": "D", "p": 10.5, "o2": 26.0},
        {"id": "E", "p": 7.5, "o2": 40.0},
        {"id": "F", "p": 14.7, "o2": 21.0},
        {"id": "G", "p": 12.0, "o2": 21.0},
        {"id": "H", "p": 12.0, "o2": 28.0},
    ]
    cands = []
    for c in candidates_def:
        vec = hazard_vector(c["p"], c["o2"], gravity, flow_ms, temperature_c,
                            material_class)
        # normalize axes for the frontier: fire_risk lower-better, eva higher-better
        fire_risk = min(1.0, vec["ignition"] / 100.0)
        # EVA benefit: lower cabin pressure -> less prebreathe time (per NASA
        # Exploration Atmosphere rationale), scaled 0-1 across the candidate set.
        eva = max(0.0, min(1.0, (16.0 - c["p"]) / 10.0))
        cands.append({
            **c,
            "fire_risk": round(fire_risk, 3),
            "eva": round(eva, 3),
            "ignition": vec["ignition"],
            "crew_safe": vec["crew"]["crew_safe"],
            "normoxia_pct": vec["crew"]["normoxia_pct"],
        })
    front_ids = {c["id"] for c in pareto_front(cands)}
    for c in cands:
        c["on_frontier"] = c["id"] in front_ids
        c["weighted_score"] = round(weighted_score(c, fire_weight), 3)
    cands.sort(key=lambda c: c["weighted_score"], reverse=True)
    return {"fire_weight": fire_weight, "candidates": cands,
            "recommended": cands[0]["id"] if cands else None}


class CounterfactualRequest(BaseModel):
    pressure_psia: float = Field(8.2, ge=1.0, le=30.0)
    o2_pct: float = Field(34.0, ge=0.0, le=100.0)
    gravity: Gravity = "microgravity"
    flow_ms: float = Field(0.2, ge=0.0, le=5.0)
    temperature_c: float = Field(22.0, ge=-20.0, le=60.0)
    material_class: MaterialClass = "polymer"
    delta_o2_pct: float = Field(0.0, ge=-100.0, le=100.0)
    delta_flow_ms: float = Field(0.0, ge=-5.0, le=5.0)


@app.post("/api/counterfactual")
def counterfactual(req: CounterfactualRequest) -> dict[str, Any]:
    before = hazard_vector(req.pressure_psia, req.o2_pct, req.gravity, req.flow_ms,
                           req.temperature_c, req.material_class)
    after = hazard_vector(req.pressure_psia, req.o2_pct + req.delta_o2_pct,
                          req.gravity, req.flow_ms + req.delta_flow_ms,
                          req.temperature_c, req.material_class)
    keys = ["ignition", "spread", "persistence", "heat_release", "extinction_margin"]
    deltas = {k: round(after[k] - before[k], 1) for k in keys}
    return {
        "before": before,
        "after": after,
        "deltas": deltas,
        "overall": "WORSE" if deltas["ignition"] + deltas["spread"] > 0 else "BETTER",
    }


@app.get("/api/validate")
def validate() -> dict[str, Any]:
    """Leave-out backtest: the engine classifies each DB record's verdict
    (spread vs self-extinguish) from the OTHER records only (leave-one-out).

    Reported with NASA-grade honesty: misses get explanations. Misses on
    records that are FIT ANCHORS of the boundary are expected (the boundary
    was constructed from them — a near-tie classification there is not
    generalization evidence either way). The backtest lives in the engine
    (backend/engine/backtest.py) so the endpoint and the composed answers read
    the same implementation.
    """
    return leave_one_out(load_experiments())


@app.get("/api/report")
def report(
    pressure_psia: float = Query(8.2, ge=1.0, le=30.0),
    o2_pct: float = Query(34.0, ge=0.0, le=100.0),
    gravity: Gravity = "microgravity",
    flow_ms: float = Query(0.2, ge=0.0, le=5.0),
    temperature_c: float = Query(22.0, ge=-20.0, le=60.0),
    material_class: MaterialClass = "polymer",
    download: bool = Query(False),
) -> Response:
    """One-page Markdown decision memo for this atmosphere.

    Every figure comes from the same engine functions the other endpoints use;
    the memo adds no numbers of its own. `download=true` sets a
    Content-Disposition header so the client can save it as a file.
    """
    body = build_report(pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
                        material_class)
    headers = {}
    if download:
        name = (f"flare-memo-{pressure_psia:g}psia-{o2_pct:g}pct-{gravity}-{material_class}.md")
        headers["Content-Disposition"] = f'attachment; filename="{name}"'
    return Response(content=body, media_type="text/markdown; charset=utf-8",
                    headers=headers)


# Last, so every API route above keeps precedence: the built UI is served from
# this same origin (backend/app/static_site.py), which is what lets the demo run
# as ONE process behind ONE URL on any Python host. No-op without a build.
from backend.app.static_site import mount_static_site  # noqa: E402

STATIC_DIR = mount_static_site(app)
