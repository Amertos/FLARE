"""Engine unit tests — assert the exact values proven in
docs/SCIENTIFIC-VALIDATION-DOSSIER.md §6 (executed test log).

Run: py -m pytest backend/tests -q
"""
from __future__ import annotations

import math

import pytest

from backend.app.methodology import (
    DATA_PROVENANCE,
    FUTURE_WORK,
    GOVERNANCE,
    LIMITATIONS,
)
from backend.engine import (
    LOC_A,
    LOC_B,
    MATERIAL_CLASSES,
    THICKNESS_FACTOR_BY_MATERIAL,
    classify,
    coverage,
    effective_loc,
    hazard_vector,
    loc_percent,
    pareto_front,
    po2_normoxia_pct,
    po2_psia,
    rank_experiments,
    thickness_factor_for,
    weighted_score,
)
from backend.engine.citations import verify_citations
from backend.data import load_experiments


# ---------- Test 1: LOC model (dossier §6 Test 1) ----------

def test_loc_constants_match_dossier_v2():
    assert math.isclose(LOC_A, 15.88, abs_tol=1e-9)
    assert math.isclose(LOC_B, 200.5, abs_tol=1e-9)


def test_loc_ground_anchors():
    # 1g ground anchors of the v2 fit (max error 0.25 pt)
    assert math.isclose(loc_percent(50.0), 19.89, abs_tol=0.26)   # ~20
    assert math.isclose(loc_percent(70.0), 18.74, abs_tol=0.26)   # ~18.5
    assert math.isclose(loc_percent(101.3), 17.86, abs_tol=0.26)  # ~18


def test_loc_microgravity_offset():
    # µg offset ~-0.8 pt at full flow: 60 kPa base 19.22 -> eff ~18.42
    eff = effective_loc(60.0, "microgravity", 0.25)
    assert loc_percent(60.0) - eff == pytest.approx(0.8, abs=0.05)


def test_microgravity_low_flow_raises_loc():
    # BASS-II-04 physics check: low flow in µg RAISES effective LOC
    full = effective_loc(101.3, "microgravity", 0.25)
    low = effective_loc(101.3, "microgravity", 0.1)
    assert low > full
    # penalty magnitude: 1.5 * (0.25-0.10)/0.25 = 0.9 pt
    assert low - full == pytest.approx(0.9, abs=0.01)
    # 1g has no flow penalty (buoyancy supplies transport)
    assert effective_loc(101.3, "earth", 0.1) == effective_loc(101.3, "earth", 0.25)


def test_bass_ii_04_classification():
    # Observed self-extinguish: 17% O2 @ 101.3 kPa, µg, 0.1 m/s
    # eff LOC = 17.48 (base 18.38) + (-0.8) + 0.9 = 17.58... compute directly:
    eff = effective_loc(101.3, "microgravity", 0.1)
    assert 17.0 < eff  # below boundary -> self-extinguish, as observed


def test_loc_held_out_spread_classification():
    # 19.8% O2 @ 60 kPa observed spread; boundary is 17.0 -> above -> spread
    assert 19.8 > loc_percent(60.0)


def test_loc_monotonic_decreasing_with_pressure():
    # Published trend reproduced: LOC DECREASES as total pressure INCREASES,
    # i.e. LOC is higher at lower pressure (dossier §4.2).
    assert loc_percent(30.0) > loc_percent(50.0) > loc_percent(70.0) > loc_percent(101.3)


def test_effective_loc_extrapolated_flag():
    from backend.engine.loc import epistemic_flag_for_pressure
    assert epistemic_flag_for_pressure(30.0) == "EXTRAPOLATED"
    assert epistemic_flag_for_pressure(120.0) == "EXTRAPOLATED"
    assert epistemic_flag_for_pressure(101.3) == "INTERPOLATED"


# ---------- Test 2: epistemic labels (dossier §6 Test 2) ----------

def test_epistemic_pressure_axis():
    exps = load_experiments()
    # 55 kPa @ 16.5% O2: inside envelope; nearest records (50 kPa/20%,
    # 60 kPa/17% µg) fall outside tolerance on O2 or gravity -> INTERPOLATED
    assert classify(55.0, 16.5, "earth", "polymer", exps) == "INTERPOLATED"
    # 80 kPa @ 19%: inside envelope, no record within tolerance -> INTERPOLATED
    assert classify(80.0, 19.0, "earth", "polymer", exps) == "INTERPOLATED"
    # 34.5 kPa: outside envelope -> EXTRAPOLATED
    assert classify(34.5, 20.0, "earth", "polymer", exps) == "EXTRAPOLATED"
    # 120 kPa: outside envelope -> EXTRAPOLATED
    assert classify(120.0, 20.0, "earth", "polymer", exps) == "EXTRAPOLATED"
    # 50 kPa @ 20%: exactly the LOC-PRESSURE-TREND-02 record -> OBSERVED
    assert classify(50.0, 20.0, "earth", "polymer", exps) == "OBSERVED"


def test_epistemic_observed_on_exact_record():
    exps = load_experiments()
    rec = next(e for e in exps if e["experiment_id"] == "BASS-II-02")
    assert classify(rec["pressure_kpa"], rec["o2_pct"], rec["gravity"],
                    rec["material_class"], exps) == "OBSERVED"


# ---------- Test 3: crew physiology (dossier §6 Test 3) ----------

def test_po2_values():
    assert math.isclose(po2_psia(14.7, 21), 3.087, abs_tol=1e-9)
    assert math.isclose(po2_psia(8.2, 34), 2.788, abs_tol=1e-9)
    assert math.isclose(po2_psia(10.0, 30), 3.0, abs_tol=1e-9)
    assert math.isclose(po2_psia(7.5, 40), 3.0, abs_tol=1e-9)
    assert math.isclose(po2_psia(16.7, 100), 16.7, abs_tol=1e-9)


def test_normoxia_percent():
    assert math.isclose(po2_normoxia_pct(8.2, 34), 90.3, abs_tol=0.2)
    assert math.isclose(po2_normoxia_pct(16.7, 100), 541.0, abs_tol=0.5)


def test_crew_equivalent_not_fire_equivalent():
    # 10/30 and 7.5/40 share pO2 = 3.00 psia, but 7.5/40 sits closer to the
    # fire boundary in molar O2 (dossier §3.2) -> higher fire hazard.
    h1 = hazard_vector(10.0, 30.0, "microgravity", 0.2)
    h2 = hazard_vector(7.5, 40.0, "microgravity", 0.2)
    assert math.isclose(po2_psia(10.0, 30.0), po2_psia(7.5, 40.0), abs_tol=1e-9)
    assert h2["ignition"] > h1["ignition"]


# ---------- Test 4: Pareto (dossier §6 Test 4) ----------

def test_pareto_front():
    cands = [
        {"id": "A", "fire_risk": 0.41, "eva": 0.93},
        {"id": "B", "fire_risk": 0.31, "eva": 0.91},
        {"id": "C", "fire_risk": 0.21, "eva": 0.82},
        {"id": "D", "fire_risk": 0.35, "eva": 0.90},
    ]
    front = pareto_front(cands)
    assert {c["id"] for c in front} == {"A", "B", "C"}


def test_weighted_score_prioritization():
    cands = [
        {"id": "B", "fire_risk": 0.31, "eva": 0.91},
        {"id": "A", "fire_risk": 0.41, "eva": 0.93},
    ]
    # fire safety twice as important as EVA -> B wins
    assert weighted_score(cands[0], 2 / 3) > weighted_score(cands[1], 2 / 3)


# ---------- Test 5: similarity ranking (dossier §6 Test 5) ----------

def test_similarity_ranking_order():
    exps = load_experiments()
    ranked = rank_experiments(56.5, 34.0, "microgravity", "polymer", exps)
    # nearest conditions first: SoFIE-MIST-class record should lead the
    # microgravity polymer records; pure-1g ground records rank lower.
    top = ranked[0]
    assert top["similarity"] > 0.5
    by_id = {r["experiment_id"]: r["similarity"] for r in ranked}
    assert by_id["SOFIE-MIST-REF-01"] > by_id["LOC-1G-101KPA-01"]
    assert by_id["EXPATM-EVA-REF-01"] > by_id["LOC-1G-101KPA-01"]


def test_loc_envelope_and_record_range_are_distinct():
    # Two different questions, deliberately two different numbers:
    #   "is the LOC curve calibrated here?" -> loc.P_ENVELOPE_KPA
    #   "is there any record near here?"    -> evidence_pressure_range
    from backend.engine import evidence_pressure_range
    from backend.engine.loc import P_ENVELOPE_KPA
    exps = load_experiments()
    assert evidence_pressure_range(exps) == (50.0, 115.1)
    assert P_ENVELOPE_KPA == (50.0, 101.3)
    assert evidence_pressure_range(exps)[1] > P_ENVELOPE_KPA[1]


def test_pressure_110_is_interpolated_evidence_but_extrapolated_curve():
    # 110 kPa sits inside the record range (Apollo 1 reaches 115.1 kPa) but
    # outside the curve's calibration envelope. The two labels must disagree,
    # and the map must hatch the curve while the evidence view still lists the
    # records.
    from backend.engine.loc import epistemic_flag_for_pressure
    exps = load_experiments()
    assert classify(110.0, 20.0, "earth", "polymer", exps) == "INTERPOLATED"
    assert epistemic_flag_for_pressure(110.0) == "EXTRAPOLATED"


def test_coverage_bounds():
    exps = load_experiments()
    c = coverage(56.5, 34.0, "microgravity", "polymer", exps)
    assert 0.0 <= c <= 1.0
    assert c > 0.5


# ---------- Test 6: citation verification (dossier §6 Test 6) ----------

def test_citation_verification():
    ids = {"BASS-II-12", "SOFIE-MIST-7"}
    r = verify_citations(["BASS-II-12", "SOFIE-MIST-7", "FABRICATED-99"], ids)
    assert r["valid"] == ["BASS-II-12", "SOFIE-MIST-7"]
    assert r["fabricated"] == ["FABRICATED-99"]
    assert r["ok"] is False


def test_citation_verification_clean():
    ids = set(e["experiment_id"] for e in load_experiments())
    r = verify_citations(["BASS-II-01", "SAFFIRE-IV-01"], ids)
    assert r["ok"] is True


# ---------- Engine behavior sanity (dossier §4.5) ----------

def test_microgravity_low_flow_suppresses_spread():
    # Same atmosphere; low flow in µg -> lower spread tendency AND higher LOC
    hi_flow = hazard_vector(8.2, 30.0, "microgravity", 0.3)
    lo_flow = hazard_vector(8.2, 30.0, "microgravity", 0.05)
    assert lo_flow["spread"] < hi_flow["spread"]
    assert lo_flow["effective_loc_pct"] > hi_flow["effective_loc_pct"]


def test_counterfactual_dO2_responsive():
    # +2% O2 must move the vector (no saturation at mid-range margins)
    b = hazard_vector(8.2, 34.0, "microgravity", 0.2)
    a = hazard_vector(8.2, 36.0, "microgravity", 0.2)
    assert a["ignition"] - b["ignition"] > 2.0


def test_apollo1_regime_is_extreme():
    h = hazard_vector(16.7, 100.0, "earth", 0.0)
    assert h["ignition"] == pytest.approx(100.0, abs=0.5)
    assert h["crew"]["normoxia_pct"] > 500


def test_below_boundary_near_zero_ignition():
    # 12% O2 at 101.3 kPa is well below LOC (21%) -> tiny ignition tendency
    h = hazard_vector(14.7, 12.0, "earth", 0.2)
    assert h["ignition"] < 5.0


# ---------- Test 8: material classes and the thickness factor (dossier §4.5) ----------

def test_material_vocabulary_covers_dossier():
    # dossier §2.1 declares exactly these four classes; the API vocabulary is
    # asserted against this tuple at import time.
    assert MATERIAL_CLASSES == ("polymer", "textile", "insulation", "composite")


def test_thickness_factor_per_material():
    assert set(THICKNESS_FACTOR_BY_MATERIAL) == set(MATERIAL_CLASSES)
    assert thickness_factor_for("polymer") == 1.0
    assert thickness_factor_for("textile") < 1.0
    assert thickness_factor_for("insulation") < thickness_factor_for("textile")
    assert thickness_factor_for("composite") > 1.0
    # an unknown class degrades to the neutral factor, never to zero
    assert thickness_factor_for("unobtainium") == 1.0


def test_material_class_changes_hazard_vector():
    # F_s carries the thickness factor, and F_p/F_b inherit it; F_i must NOT
    # depend on it (dossier §4.6 derives ignition from LOC margin only).
    poly = hazard_vector(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer")
    insul = hazard_vector(8.2, 34.0, "microgravity", 0.2, 22.0, "insulation")
    comp = hazard_vector(8.2, 34.0, "microgravity", 0.2, 22.0, "composite")
    assert insul["spread"] < poly["spread"] < comp["spread"]
    assert insul["persistence"] < comp["persistence"]
    assert poly["ignition"] == insul["ignition"] == comp["ignition"]


def test_polymer_default_matches_previous_behaviour():
    # The derived thickness factor for the default class must be 1.0 so that
    # every figure proven in dossier §6 is unchanged by this wiring.
    assert hazard_vector(8.2, 34.0, "microgravity", 0.2) == hazard_vector(
        8.2, 34.0, "microgravity", 0.2, 22.0, "polymer", 1.0
    )


# ---------- Test 9: product-side claims (dossier §4.7, §8) ----------

def test_methodology_covers_all_dossier_47_limits():
    # dossier §8 states the §4.7 known-limitations list ships in the product UI.
    # This is the assertion that keeps that claim true.
    assert {lim["id"] for lim in LIMITATIONS} == {f"L{i}" for i in range(1, 8)}
    assert all(lim["title"].strip() and lim["detail"].strip() for lim in LIMITATIONS)


def test_methodology_declares_the_llm_layer_unbuilt():
    unbuilt = next(f for f in FUTURE_WORK if f["id"] == "F4")
    assert "NOT" in unbuilt["detail"]


def test_governance_and_provenance_are_stated():
    assert len(GOVERNANCE) >= 5
    assert len(DATA_PROVENANCE) >= 7


# ---------- Test 10: API contract and input validation ----------

def _client():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    return TestClient(app)


def test_api_rejects_unknown_material_class():
    r = _client().get("/api/scenario", params={"material_class": "unobtainium"})
    assert r.status_code == 422


def test_api_rejects_unknown_gravity_regime():
    r = _client().get("/api/scenario", params={"gravity": "jupiter"})
    assert r.status_code == 422


def test_api_rejects_out_of_range_inputs():
    c = _client()
    assert c.get("/api/scenario", params={"o2_pct": 500}).status_code == 422
    assert c.get("/api/scenario", params={"pressure_psia": 0}).status_code == 422
    assert c.get("/api/scenario", params={"temperature_c": -273}).status_code == 422
    assert c.get("/api/tradespace", params={"flow_ms": 99}).status_code == 422


def test_api_temperature_reaches_the_engine():
    # The temperature term in F_i (dossier §4.6) must be reachable from the API.
    c = _client()
    cool = c.get("/api/scenario", params={"temperature_c": 18}).json()
    warm = c.get("/api/scenario", params={"temperature_c": 30}).json()
    assert cool["inputs"]["temperature_c"] == 18.0
    assert warm["hazard"]["ignition"] > cool["hazard"]["ignition"]


def test_api_tradespace_reports_the_coverage_envelope():
    body = _client().get("/api/tradespace").json()
    assert body["p_envelope_kpa"] == [50.0, 101.3]
    # Outside the envelope the boundary value is null: the map hatches the
    # region instead of colouring it (dossier §4.7 L2).
    below = [b for b in body["loc_boundary"]
             if b["p_psia"] < 50.0 / 6.89476]
    assert below
    assert all(b["loc_pct"] is None for b in below)
    assert all(b["flag"] == "EXTRAPOLATED" for b in below)
    inside = [b for b in body["loc_boundary"]
              if 50.0 / 6.89476 <= b["p_psia"] <= 101.3 / 6.89476]
    assert inside and all(b["loc_pct"] is not None for b in inside)


def test_api_ask_is_deterministic_and_verifies_citations():
    r = _client().post("/api/ask", json={
        "question": "Why is 34% O2 riskier than 28%?",
        "pressure_psia": 8.2, "o2_pct": 34.0,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "offline-deterministic"
    assert body["citation_check_ok"] is True
    assert body["fabricated_citations"] == []


def test_api_ask_echoes_question_and_honours_temperature():
    # /api/ask takes the same atmosphere state as /api/scenario, temperature
    # included, and returns the question it was given so the client can show
    # what was recorded. The answer itself is composed from the engine, not
    # parsed from the question (dossier §4.7 F4).
    c = _client()
    q = "Why is 34% O2 riskier than 28%?"
    base = {"question": q, "pressure_psia": 8.2, "o2_pct": 34.0}
    cool = c.post("/api/ask", json={**base, "temperature_c": 18}).json()
    warm = c.post("/api/ask", json={**base, "temperature_c": 30}).json()
    assert cool["question"] == q
    assert warm["engine_summary"]["ignition"] > cool["engine_summary"]["ignition"]


def test_api_ask_rejects_overlong_question():
    r = _client().post("/api/ask", json={"question": "x" * 501})
    assert r.status_code == 422


def test_api_methodology_matches_the_module():
    body = _client().get("/api/methodology").json()
    assert len(body["limitations"]) == len(LIMITATIONS)
    assert len(body["future_work"]) == len(FUTURE_WORK)


def test_api_cors_does_not_allow_arbitrary_methods():
    r = _client().options("/api/ask", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "DELETE",
    })
    assert "DELETE" not in r.headers.get("access-control-allow-methods", "")
