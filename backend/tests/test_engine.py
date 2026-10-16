"""Engine unit tests — assert the exact values proven in
docs/SCIENTIFIC-VALIDATION-DOSSIER.md §6 (executed test log).

Run: py -m pytest backend/tests -q
"""
from __future__ import annotations

import math

import pytest

from backend.engine import (
    LOC_A,
    LOC_B,
    classify,
    coverage,
    effective_loc,
    hazard_vector,
    loc_percent,
    pareto_front,
    po2_normoxia_pct,
    po2_psia,
    rank_experiments,
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
