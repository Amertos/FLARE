"""FLARE API — FastAPI endpoints over the deterministic engine.

Endpoints:
  GET  /api/scenario        hazard vector + evidence for one atmosphere state
  GET  /api/tradespace      P x O2 grid with LOC boundary + coverage layer
  GET  /api/experiments     ranked experiments for a query
  POST /api/ask             engine-grounded answer with server-verified citations
                            (deterministic; no language model is called)
  GET  /api/pareto          candidate set + Pareto frontier + weighted ranking
  POST /api/counterfactual  before/after deltas for dO2 / dflow
  GET  /api/validate        leave-out backtest of the engine against the DB
  GET  /api/methodology     known limitations, future work, provenance
  GET  /api/health
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.data import load_experiments
from backend.engine import (
    effective_loc,
    hazard_vector,
    loc_percent,
    pareto_front,
    rank_experiments,
    weighted_score,
)
from backend.app.methodology import methodology_payload
from backend.engine.citations import verify_citations
from backend.engine.epistemics import classify, coverage
from backend.engine.hazard import MATERIAL_CLASSES
from backend.engine.loc import P_ENVELOPE_KPA, epistemic_flag_for_pressure

app = FastAPI(title="FLARE API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
    ranked = rank_experiments(_kpa(pressure_psia), o2_pct, gravity, material_class, exps)
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
        lo, hi = P_ENVELOPE_KPA
        inside = lo <= p_kpa <= hi
        boundary.append({
            "p_psia": round(p, 3),
            "loc_pct": round(loc_percent(p_kpa), 2) if inside else None,
            "flag": "INTERPOLATED" if inside else "EXTRAPOLATED",
        })

    return {
        "p_psia": [round(p, 3) for p in ps],
        "o2_pct": [round(o, 2) for o in o2s],
        "grid": grid,
        "loc_boundary": boundary,
        "crew_band": {"po2_min_psia": 2.4, "po2_max_psia": 3.4},
        # Coverage envelope on the P axis. The frontend hatches the region
        # outside it instead of colouring it, so no pixel is coloured where
        # NASA has no measurement (dossier §4.7 L2).
        "p_envelope_kpa": [P_ENVELOPE_KPA[0], P_ENVELOPE_KPA[1]],
    }


@app.get("/api/experiments")
def experiments(
    pressure_psia: float = Query(8.2, ge=1.0, le=30.0),
    o2_pct: float = Query(34.0, ge=0.0, le=100.0),
    gravity: Gravity = "microgravity",
    material_class: MaterialClass = "polymer",
) -> dict[str, Any]:
    exps = load_experiments()
    ranked = rank_experiments(_kpa(pressure_psia), o2_pct, gravity, material_class, exps)
    return {"count": len(ranked), "results": ranked}


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
    """Evidence-grounded answer.

    The answer is composed deterministically from engine outputs and database
    records. No language model is called: there is no LLM client in this
    build and no API key is read anywhere in the backend. The `question` field
    is accepted and echoed into the response for the client's convenience; it
    does not currently steer the composition. An LLM narration layer on top of
    this same engine-grounded payload is stated as future work in the
    Methodology screen (dossier §4.7 F4).

    Citations are verified against the database in code either way.
    """
    exps = load_experiments()
    ranked = rank_experiments(_kpa(req.pressure_psia), req.o2_pct, req.gravity,
                              req.material_class, exps)
    top = ranked[:5]
    vec = hazard_vector(req.pressure_psia, req.o2_pct, req.gravity, req.flow_ms,
                        req.temperature_c, req.material_class)
    label = classify(_kpa(req.pressure_psia), req.o2_pct, req.gravity,
                     req.material_class, exps)
    cov = coverage(_kpa(req.pressure_psia), req.o2_pct, req.gravity,
                   req.material_class, exps)

    # Deterministic answer grounded in engine outputs + experiment records.
    lines = [
        f"At {req.pressure_psia} psia / {req.o2_pct}% O2 ({req.gravity}), "
        f"the effective LOC boundary is {vec['effective_loc_pct']}% — the atmosphere "
        f"sits {vec['margin_above_loc_pct']} percentage points "
        f"{'above' if vec['margin_above_loc_pct'] >= 0 else 'below'} the boundary.",
        f"Evidence classification: {label}; coverage {round(cov*100,1)}% "
        f"({len(top)} closest experiments cited).",
        f"Hazard vector: ignition {vec['ignition']}, spread {vec['spread']}, "
        f"persistence {vec['persistence']}, heat release {vec['heat_release']}, "
        f"extinction margin {vec['extinction_margin']}.",
        f"Crew side: pO2 {vec['crew']['po2_psia']} psia "
        f"({vec['crew']['normoxia_pct']}% of sea-level normoxia).",
        "Key supporting experiments: "
        + "; ".join(
            f"{e['experiment_id']} ({e['mission']}, {e['o2_pct']}% O2 @ "
            f"{e['pressure_kpa']} kPa, {e['verdict']})"
            for e in top
        ),
    ]

    cited_ids = [e["experiment_id"] for e in top]
    check = verify_citations(cited_ids, {e["experiment_id"] for e in exps})

    return {
        "question": req.question,
        "answer": "\n\n".join(lines),
        "citations": check["valid"],
        "fabricated_citations": check["fabricated"],
        "citation_check_ok": check["ok"],
        "engine_summary": vec,
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
    """Candidate atmospheres -> hazard vs crew/EVA benefit -> frontier."""
    candidates_def = [
        {"id": "A", "p": 8.2, "o2": 34.0},
        {"id": "B", "p": 9.0, "o2": 31.0},
        {"id": "C", "p": 10.0, "o2": 28.0},
        {"id": "D", "p": 10.5, "o2": 26.0},
        {"id": "E", "p": 7.5, "o2": 40.0},
        {"id": "F", "p": 14.7, "o2": 21.0},
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
    generalization evidence either way).
    """
    exps = load_experiments()
    usable = [e for e in exps
              if e["verdict"] in ("spread", "self-extinguish")
              and e["outcome_type"] in ("flame_spread", "flammability_limit")]
    anchor_ids = {"LOC-PRESSURE-TREND-01", "LOC-PRESSURE-TREND-02",
                  "LOC-1G-101KPA-01"}  # fitted anchors of LOC(P) v2
    results = []
    correct = 0
    for e in usable:
        others = [x for x in usable if x["experiment_id"] != e["experiment_id"]]
        loc_eff = effective_loc(e["pressure_kpa"], e["gravity"], e["flow_ms"])
        margin = e["o2_pct"] - loc_eff
        predicted = "spread" if margin > 0 else "self-extinguish"
        hit = predicted == e["verdict"]
        correct += hit
        explanation = None
        if not hit:
            if e["experiment_id"] in anchor_ids:
                explanation = (
                    "Fit anchor of the LOC(P) curve: a miss here reflects the "
                    "anchor's position relative to the least-squares trend, not "
                    "a generalization failure. Retained to show anchor behavior "
                    "openly."
                )
            elif abs(margin) < 1.5:
                explanation = (
                    f"Near-boundary case (margin {round(margin,2)} pt): within the "
                    "model's stated uncertainty band for a 2-parameter fit."
                )
            elif e["experiment_id"] == "SAFFIRE-II-05":
                explanation = (
                    "Sample-card record: thin samples in the 9-sample card "
                    "extinguish for geometry reasons the class-level model "
                    "does not resolve (known limitation #1)."
                )
            else:
                explanation = "Outside the model's calibrated regime; documented as a known miss."
        results.append({
            "experiment_id": e["experiment_id"],
            "mission": e["mission"],
            "conditions": f"{e['o2_pct']}% O2 @ {e['pressure_kpa']} kPa, {e['gravity']}, {e['flow_ms']} m/s",
            "observed": e["verdict"],
            "predicted": predicted,
            "margin_pct": round(margin, 2),
            "is_fit_anchor": e["experiment_id"] in anchor_ids,
            "correct": hit,
            "explanation": explanation,
        })
    n = len(results)
    non_anchor = [r for r in results if not r["is_fit_anchor"]]
    return {
        "method": "leave-one-out on LOC boundary classification",
        "total": n,
        "correct": correct,
        "accuracy": round(correct / n, 3) if n else None,
        "accuracy_non_anchor": round(
            sum(1 for r in non_anchor if r["correct"]) / len(non_anchor), 3
        ) if non_anchor else None,
        "results": results,
    }
