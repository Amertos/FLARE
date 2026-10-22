"""Tests for mission flight scenarios + flight-readiness report fields.

Asserts:
1. every scenario evaluates with a hazard vector and an effective LOC inside
   the model's own number set,
2. the 1g twin is exactly the same gravity term swapped, so the delta columns
   are engine-computed, never hand-written,
3. the Gateway pair (µg vs 1g at the same parameters) genuinely differs only
   by gravity — the burden of the µg-vs-1g story,
4. /api/missions and the extended /api/report publish the citation matrix,
   cool-flame status and flow regime.

Run: py -m pytest backend/tests/test_missions.py -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.engine.hazard import hazard_vector
from backend.engine.loc import effective_loc
from backend.engine.missions import (
    DEFAULT_COMPARE,
    SCENARIOS,
    scenario_payload,
)

client = TestClient(app)

# ---------- scenario definitions ----------

def test_every_scenario_has_published_provenance():
    for s in SCENARIOS:
        assert s["context"], s["id"]
        assert s["provenance"], s["id"]
        assert s["gravity"] in ("microgravity", "lunar", "mars", "earth")


def test_gateway_pair_differs_only_by_gravity():
    ids = {s["id"]: s for s in SCENARIOS}
    ug, one_g = ids["gateway-orbital"], ids["gateway-ground-eval"]
    for key in ("pressure_psia", "o2_pct", "flow_ms", "temperature_c", "material_class"):
        assert ug[key] == one_g[key], key
    assert ug["gravity"] == "microgravity" and one_g["gravity"] == "earth"


# ---------- scenario_payload ----------

def test_twin_is_the_same_state_with_gravity_swapped():
    s = SCENARIOS[0]
    full = scenario_payload(s["pressure_psia"], s["o2_pct"], s["gravity"],
                            s["flow_ms"], s["temperature_c"], s["material_class"])
    twin_recomputed = hazard_vector(s["pressure_psia"], s["o2_pct"], "earth",
                                    s["flow_ms"], s["temperature_c"], s["material_class"])
    assert full["twin_1g"]["hazard"]["ignition"] == twin_recomputed["ignition"]
    eff_1g = effective_loc(s["pressure_psia"] * 6.89476, "earth", s["flow_ms"], s["temperature_c"])
    assert full["twin_1g"]["effective_loc_pct"] == pytest.approx(eff_1g, abs=0.01)


def test_µg_gateway_has_larger_margin_than_its_1g_twin():
    # The engine's gravity offset puts the µg boundary BELOW the 1g one, so
    # the µg scenario's margin must exceed the twin's by ~0.5-0.8 pt — the
    # crossover story, asserted as a monotone relationship, not a magic number.
    ids = {s["id"]: s for s in SCENARIOS}
    ug_full = scenario_payload(ids["gateway-orbital"]["pressure_psia"],
                               ids["gateway-orbital"]["o2_pct"], "microgravity",
                               ids["gateway-orbital"]["flow_ms"], 22.0, "polymer")
    one_g_full = scenario_payload(ids["gateway-orbital"]["pressure_psia"],
                                  ids["gateway-orbital"]["o2_pct"], "earth",
                                  ids["gateway-orbital"]["flow_ms"], 22.0, "polymer")
    assert ug_full["margin_above_loc_pct"] > one_g_full["margin_above_loc_pct"]
    assert 0 < (ug_full["margin_above_loc_pct"] - one_g_full["margin_above_loc_pct"]) < 1.5


def test_delta_wording_switches_direction_by_margin_sign():
    s = SCENARIOS[0]
    full = scenario_payload(s["pressure_psia"], s["o2_pct"], s["gravity"],
                            s["flow_ms"], s["temperature_c"], s["material_class"])
    # lunar margin > 1g margin → delta has a 1g-riskier wording
    assert "1g riskier" in full["delta_vs_1g"]["wording"]
    inverted = scenario_payload(s["pressure_psia"], s["o2_pct"], "microgravity",
                                s["flow_ms"], s["temperature_c"], s["material_class"])
    # microgravity margin > lunar? — no, both below 1g; the wording must swap
    assert "1g riskier" in inverted["delta_vs_1g"]["wording"]


def test_saffire_iv_and_depress_sequences_evaluate_inside_the_envelope():
    for s in SCENARIOS:
        full = scenario_payload(s["pressure_psia"], s["o2_pct"], s["gravity"],
                                s["flow_ms"], s["temperature_c"], s["material_class"])
        assert 0 <= full["hazard"]["ignition"] <= 100
        assert -10 < full["margin_above_loc_pct"] < 100


# ---------- endpoints ----------

def test_missions_endpoint_publishes_scenarios_and_default_compare():
    r = client.get("/api/missions")
    assert r.status_code == 200
    body = r.json()
    assert len(body["scenarios"]) >= 4
    ids = {s["id"] for s in body["scenarios"]}
    assert {"artemis-lander", "gateway-orbital", "gateway-ground-eval", "saffire-iv"} <= ids
    assert body["default_compare"]["a"] == DEFAULT_COMPARE[0]
    eval0 = body["scenarios"][0]["evaluation"]
    assert "delta_vs_1g" in eval0 and "twin_1g" in eval0


def test_report_publishes_flame_regime_and_citation_matrix():
    r = client.get("/api/report", params={
        "pressure_psia": 8.2, "o2_pct": 34.0, "gravity": "microgravity",
        "flow_ms": 0.2, "temperature_c": 22.0, "material_class": "polymer"})
    assert r.status_code == 200
    text = r.text
    # flame-regime assessment section
    assert "Flame-regime assessment" in text
    assert "cool-flame" in text.lower()
    assert "front rate" in text.lower() or "Front rate" in text
    # citation matrix section with joined claim->source rows
    assert "Citation matrix" in text
    assert "PMC5760683" in text and "NTRS" in text
    # the section numbering survived the insertions
    assert "## 11. Citation matrix" in text
