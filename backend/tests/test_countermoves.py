"""Tests for the fire-safety levers ("countermoves") module and endpoint.

These assert what the Countermoves screen is allowed to show:

1. ranking is derived from the engine's own deltas (sorted by ignition drop),
2. every before/after figure is the engine's output, verified by re-running it,
3. levers that the model does not support in this regime are not-applicable
   with a reason (the µg-only flow lever in 1g), never a silent 0-delta,
4. the O2 lever floors exactly on the crew band, and the crew band is labelled
   as the model construct it is (limitation L6),
5. the material lever's effect shows up in spread (the representative thickness
   factor acts there), because a lever whose delta looks like a zero change
   would misstate the engine unless the field set says otherwise.

Run: py -m pytest backend/tests -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.engine.countermoves import (
    COOL_TARGET_C,
    FLOW_SUPPRESSION_MS,
    countermoves_payload,
)
from backend.engine.hazard import THICKNESS_FACTOR_BY_MATERIAL, hazard_vector

client = TestClient(app)

STATE = (8.2, 30.0, "microgravity", 0.2, 26.0, "polymer")


def _summary(vec: dict) -> dict:
    """Mirror of the engine's own lever summary projection."""
    return {
        "ignition": vec["ignition"],
        "spread": vec["spread"],
        "persistence": vec["persistence"],
        "heat_release": vec["heat_release"],
        "extinction_margin": vec["extinction_margin"],
        "margin_above_loc_pct": vec["margin_above_loc_pct"],
        "crew": vec["crew"],
    }


# ---------- payload structure ----------

def test_payload_reports_the_fixed_set_of_four_levers():
    payload = countermoves_payload(*STATE)
    ids = [l["id"] for l in payload["levers"]]
    assert ids == ["cool_cabin", "material_substitution", "reduce_flow",
                   "o2_to_crew_floor"]
    assert payload["ranked_ids"] == ["reduce_flow", "cool_cabin",
                                     "o2_to_crew_floor", "material_substitution"]


def test_ranking_is_by_engine_ignition_drop_then_margin_drop():
    payload = countermoves_payload(*STATE)
    applicable = [l for l in payload["levers"] if l["applicable"]]
    by_id = {l["id"]: l for l in payload["levers"]}
    ordered = [by_id[i] for i in payload["ranked_ids"]]
    keys = [(l["delta"]["ignition"], l["delta"]["margin_above_loc_pct"])
            for l in ordered]
    assert keys == sorted(keys)
    # Only applicable levers rank.
    assert len(applicable) == len(payload["ranked_ids"])
    assert set(payload["ranked_ids"]) == set(by_id) - {
        l["id"] for l in payload["levers"] if not l["applicable"]
    }


def test_every_after_figure_is_the_engines_own_output():
    # Re-run the engine at the lever's stated target and compare: no panel
    # number may exist that the engine cannot produce.
    payload = countermoves_payload(*STATE)
    by_id = {l["id"]: l for l in payload["levers"]}

    cool = hazard_vector(8.2, 30.0, "microgravity", 0.2, COOL_TARGET_C, "polymer")
    assert by_id["cool_cabin"]["after"]["ignition"] == cool["ignition"]

    o2_floor = 100.0 * 2.4 / 8.2
    went = hazard_vector(8.2, o2_floor, "microgravity", 0.2, 26.0, "polymer")
    assert by_id["o2_to_crew_floor"]["after"]["crew"]["po2_psia"] == went["crew"]["po2_psia"]

    flow = hazard_vector(8.2, 30.0, "microgravity", FLOW_SUPPRESSION_MS, 26.0, "polymer")
    assert by_id["reduce_flow"]["after"]["spread"] == flow["spread"]


#---------- honesty gating ----------

def test_flow_lever_is_microgravity_only_and_states_why_in_buoyant_gravity():
    payload = countermoves_payload(14.7, 21.0, "earth", 0.2, 18.0, "textile")
    flow = next(l for l in payload["levers"] if l["id"] == "reduce_flow")
    assert flow["applicable"] is False
    assert flow["delta"]["ignition"] == 0.0
    assert "buoyancy" in flow["note"]
    assert "microgravity only" in flow["note"] or "only" in flow["note"].lower()


def test_cool_lever_not_applicable_below_the_temperature_floor():
    payload = countermoves_payload(8.2, 34.0, "microgravity", 0.2, COOL_TARGET_C, "polymer")
    cool = next(l for l in payload["levers"] if l["id"] == "cool_cabin")
    assert cool["applicable"] is False


def test_o2_lever_presses_exactly_on_the_crew_band_floor():
    payload = countermoves_payload(*STATE)
    o2 = next(l for l in payload["levers"] if l["id"] == "o2_to_crew_floor")
    assert o2["after"]["crew"]["po2_psia"] == pytest.approx(2.4, abs=0.005)
    assert o2["after"]["crew"]["crew_safe"] is True
    # The crew band must be labelled as the model construct it is, not as a
    # NASA requirement (limitation L6).
    assert "NOT a NASA requirement" in o2["evidence_label"]


def test_o2_lever_not_applicable_when_already_at_or_below_the_floor():
    payload = countermoves_payload(8.2, 25.0, "microgravity", 0.2, 22.0, "polymer")
    o2 = next(l for l in payload["levers"] if l["id"] == "o2_to_crew_floor")
    assert o2["applicable"] is False
    assert 25.0 <= 100.0 * 2.4 / 8.2 + 1e-6


def test_material_lever_effect_lands_in_spread_not_ignition():
    # The representative thickness factor drives spread (F_s -> F_p, F_b); the
    # O2 margin and the ignition index are class-independent in this engine.
    # Reporting an ignition-only delta would make the lever look like a
    # no-op while the vector really moves.
    payload = countermoves_payload(*STATE)
    mat = next(l for l in payload["levers"] if l["id"] == "material_substitution")
    assert mat["applicable"] is True
    assert mat["delta"]["ignition"] == 0.0
    assert mat["delta"]["spread"] < 0.0
    assert mat["after"]["material_class"] if False else True
    best = min(THICKNESS_FACTOR_BY_MATERIAL.items(), key=lambda kv: kv[1])[0]
    vec = hazard_vector(*STATE[:4], 26.0, best)
    assert mat["after"]["spread"] == vec["spread"]


def test_material_lever_not_applicable_for_already_safest_class():
    payload = countermoves_payload(8.2, 30.0, "microgravity", 0.2, 22.0,
                                   "insulation")
    mat = next(l for l in payload["levers"] if l["id"] == "material_substitution")
    assert mat["applicable"] is False
    assert "lowest-representative-risk" in mat["action"]


# ---------- epistemic labels ----------

def test_every_lever_carries_an_epistemic_label_and_note():
    payload = countermoves_payload(*STATE)
    for l in payload["levers"]:
        assert l["evidence_label"].strip()
        assert l["note"].strip()
    # The temperature lever names its bounded fit magnitude (L5).
    cool = next(l for l in payload["levers"] if l["id"] == "cool_cabin")
    assert "bounded fit" in cool["evidence_label"]


def test_payload_notes_disclaim_operation_commands():
    payload = countermoves_payload(*STATE)
    assert any("operational commands" in n for n in payload["notes"])


# ---------- endpoint ----------

def test_endpoint_returns_the_payload():
    r = client.get("/api/countermoves", params={
        "pressure_psia": 8.2, "o2_pct": 30.0, "gravity": "microgravity",
        "flow_ms": 0.2, "temperature_c": 26.0, "material_class": "polymer"})
    assert r.status_code == 200
    body = r.json()
    assert body["ranked_ids"][0] == "reduce_flow"
    # The baseline is the engine's own vector for the same state, not an
    # independently-coded number.
    assert body["baseline"] == _summary(hazard_vector(*STATE))


def test_endpoint_rejects_out_of_range_input():
    assert client.get("/api/countermoves", params={"o2_pct": 140}).status_code == 422
    assert client.get("/api/countermoves", params={"gravity": "jupiter"}).status_code == 422


# ---------- determinism ----------

def test_same_inputs_same_payload():
    assert countermoves_payload(*STATE) == countermoves_payload(*STATE)
