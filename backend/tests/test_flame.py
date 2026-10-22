"""Tests for the flame-regime module and /api/flame.

These assert the physics the 3D Freefall Lab screen is allowed to show:

1. the regime really flips between microgravity and 1g (no buoyancy → no teardrop),
2. the published low-flow behaviour is reproduced by the shipped flow penalty,
3. the front speed is relative to the Saffire-I reference condition and monotonic
   in oxygen,
4. the microgravity-vs-1g crossover is the engine's own number, and the declared
   reference condition actually exists in the curated database.

Run: py -m pytest backend/tests -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.data import load_experiments
from backend.engine.flame import (
    CITATIONS,
    FATE_SELF_EXTINGUISHING,
    FATE_SUSTAINED,
    MARGINAL_SPREAD_THRESHOLD,
    REFERENCE_EXPERIMENT_ID,
    REFERENCE_FLOW_MS,
    REFERENCE_O2_PCT,
    REFERENCE_PRESSURE_PSIA,
    SHAPE_SPHERICAL,
    SHAPE_TEARDROP,
    crossover_series,
    fate_of,
    flame_payload,
    flame_regime,
    front_speed_relative,
    reference_spread,
)

client = TestClient(app)


# ---------- regime ----------

def test_regime_flips_between_microgravity_and_1g():
    ug = flame_regime("microgravity", 0.2, 43.0)
    one_g = flame_regime("earth", 0.2, 43.0)
    assert ug["shape"] == SHAPE_SPHERICAL
    assert ug["buoyant_convection"] is False
    assert one_g["shape"] == SHAPE_TEARDROP
    assert one_g["buoyant_convection"] is True
    assert "no upward teardrop" in ug["label"]


def test_colour_tendency_follows_the_published_low_flow_behaviour():
    # link et al.: microgravity flame is bluer than the 1g comparison, and
    # bluer still as opposed flow falls
    assert "blue" in flame_regime("microgravity", 0.1, 30.0)["colour_tendency"]
    assert "yellow" in flame_regime("earth", 0.1, 30.0)["colour_tendency"]
    # partial gravity is not microgravity: buoyancy is present (Ruff/NIST note
    # lunar and Mars minima sit near the microgravity value, but the plume is not
    # absent)
    assert flame_regime("lunar", 0.2, 30.0)["buoyant_convection"] is True


def test_regime_carries_its_citations():
    regime = flame_regime("microgravity", 0.2, 43.0)
    assert regime["citations"]
    known = {c["id"] for c in CITATIONS}
    assert set(regime["citations"]) <= known


# ---------- fate ----------

def test_bass_ii_04_conditions_self_extinguish():
    # BASS-II-04 in the database: 17% O2 @ 101.3 kPa (14.69 psia), microgravity,
    # 0.1 m/s -> observed self-extinguish
    payload = flame_payload(101.3 / 6.89476, 17.0, "microgravity", 0.1, 22.0, "textile")
    assert payload["fate"]["code"] == FATE_SELF_EXTINGUISHING
    assert payload["hazard"]["margin_above_loc_pct"] < 0


def test_above_boundary_with_low_spread_is_marginal_not_sustained():
    fatal = fate_of(margin_pct=5.0, spread=MARGINAL_SPREAD_THRESHOLD - 1)
    assert fatal["code"] == "marginal"
    assert fate_of(margin_pct=5.0, spread=60.0)["code"] == FATE_SUSTAINED
    assert fate_of(margin_pct=0.0, spread=90.0)["code"] == FATE_SELF_EXTINGUISHING


# ---------- front speed ----------

def test_reference_condition_is_one_hundred_percent():
    assert front_speed_relative(reference_spread()) == 100.0


def test_front_speed_rises_with_oxygen():
    speeds = [
        front_speed_relative(flame_payload(8.2, o2, "microgravity", 0.2, 22.0, "polymer")
                             ["hazard"]["spread"])
        for o2 in (20.0, 26.0, 32.0, 38.0)
    ]
    assert speeds == sorted(speeds)
    assert speeds[0] < 100.0 < speeds[-1]


def test_reference_experiment_exists_in_the_curated_database():
    # the declared reference constants must describe a record that is actually
    # shipped, otherwise the relative-speed denominator is fiction
    exps = load_experiments()
    record = next(e for e in exps if e["experiment_id"] == REFERENCE_EXPERIMENT_ID)
    assert record["gravity"] == "microgravity"
    assert record["o2_pct"] == pytest.approx(REFERENCE_O2_PCT, abs=0.05)
    # The database stores pressures converted from psia and rounded to 1 dp
    # (14.7 psia -> 101.3 kPa, not 101.353), so the tolerance is the rounding
    # step of the stored value, not the arithmetic.
    assert record["pressure_kpa"] == pytest.approx(REFERENCE_PRESSURE_PSIA * 6.89476, abs=0.1)
    assert record["flow_ms"] == pytest.approx(REFERENCE_FLOW_MS, abs=0.001)


# ---------- crossover ----------

def test_crossover_is_the_engines_own_gravity_offset():
    # full flow: the microgravity boundary sits 0.8 pt below the 1g boundary
    full = crossover_series(8.2, 0.3, 22.0)
    assert full["offset_pt"] == pytest.approx(0.8, abs=0.01)
    assert full["loc_pct"]["microgravity"] < full["loc_pct"]["earth"]
    # at 0.2 m/s the microgravity flow penalty (0.3 pt) eats into that offset,
    # which is why the map's effective LOC for the Exploration Atmosphere is
    # 18.93% and not 18.63%
    partial = crossover_series(8.2, 0.2, 22.0)
    assert partial["offset_pt"] == pytest.approx(0.5, abs=0.01)
    assert partial["loc_pct"]["microgravity"] == pytest.approx(18.93, abs=0.01)


def test_crossover_series_sustains_spread_below_the_1g_limit():
    # At 60 kPa the microgravity boundary is the lower one, so there is a band of
    # O2 where microgravity sustains spread and 1g does not. The band is asserted
    # from the engine's own numbers, NOT from the published observation: the
    # observed µg spread record at 60 kPa sits at 17.0%, below this engine's
    # 18.42% boundary, and is published as a known miss in the backtest (dossier
    # §6 Test 7). Claiming the model reproduces 17% here would be false.
    series = crossover_series(60.0 / 6.89476, 0.3, 22.0)
    ug = series["loc_pct"]["microgravity"]
    one_g = series["loc_pct"]["earth"]
    assert ug < one_g
    assert ug == pytest.approx(18.42, abs=0.02)
    assert one_g == pytest.approx(19.22, abs=0.02)
    band_mid = (ug + one_g) / 2
    assert ug < band_mid < one_g
    assert series["microgravity_sustains_below_1g_at_pct"] == ug
    assert "microgravity" in series["published_finding"]


def test_crossover_series_matches_the_margin_definition():
    series = crossover_series(8.2, 0.2, 22.0)
    for gravity in ("microgravity", "earth"):
        loc = series["loc_pct"][gravity]
        for point in series["series"][gravity][:3]:
            assert point["margin_pct"] == pytest.approx(point["o2_pct"] - loc, abs=0.01)


# ---------- payload and endpoint ----------

def test_payload_publishes_sources_and_notes():
    payload = flame_payload(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer")
    assert payload["citations"]
    assert all(c["url"].startswith("https://") for c in payload["citations"])
    assert any("not a CFD" in n for n in payload["notes"])
    assert payload["reference"]["experiment_id"] == REFERENCE_EXPERIMENT_ID
    assert payload["hazard"]["effective_loc_pct"] == pytest.approx(18.93, abs=0.01)


def test_endpoint_returns_the_payload():
    r = client.get("/api/flame", params={
        "pressure_psia": 8.2, "o2_pct": 34.0, "gravity": "microgravity",
        "flow_ms": 0.2, "temperature_c": 22.0, "material_class": "polymer"})
    assert r.status_code == 200
    body = r.json()
    assert body["regime"]["shape"] == SHAPE_SPHERICAL
    assert body["fate"]["code"] == FATE_SUSTAINED
    assert body["front_speed_relative"] > 0
    assert body["crossover"]["series"]["earth"]


def test_endpoint_reference_condition_reads_one_hundred_percent():
    r = client.get("/api/flame", params={
        "pressure_psia": REFERENCE_PRESSURE_PSIA, "o2_pct": REFERENCE_O2_PCT,
        "gravity": "microgravity", "flow_ms": REFERENCE_FLOW_MS,
        "temperature_c": 22.0, "material_class": "polymer"})
    assert r.json()["front_speed_relative"] == 100.0


def test_endpoint_rejects_out_of_range_input():
    assert client.get("/api/flame", params={"o2_pct": 140}).status_code == 422
    assert client.get("/api/flame", params={"gravity": "jupiter"}).status_code == 422


# ---------- flow-regime bands (presentation only, FL2) ----------

def test_flow_regime_bands_follow_the_bass_ii_low_flow_finding():
    from backend.engine.flame import flow_regime
    # microgravity: height of streamer scale and bands
    assert flow_regime("microgravity", 0.05)["band"] == "near-zero opposed flow"
    assert flow_regime("microgravity", 0.2)["band"] == "low-flow"
    assert flow_regime("microgravity", 0.3)["band"] == "moderate-flow"
    assert flow_regime("microgravity", 0.5)["band"] == "full-flow"
    assert flow_regime("microgravity", 0.5)["streamer_speed_scale"] == 1.0
    assert flow_regime("microgravity", 0.05)["streamer_speed_scale"] == 0.0


def test_flow_regime_returns_no_effect_in_buoyant_gravity():
    from backend.engine.flame import flow_regime
    for g in ("earth", "lunar", "mars"):
        got = flow_regime(g, 0.2)
        assert got["band"] == "buoyancy-dominated"
        assert got["streamer_speed_scale"] == 0.0


def test_cool_flame_phase_gates_on_boundary_and_hot_regime():
    from backend.engine.flame import cool_flame_phase
    below = cool_flame_phase("microgravity", -2.0, "self_extinguishing")
    assert below["possible"] is True
    assert "FL4" in below["citations"] and "FL5" in below["citations"]
    assert "cool-flame" in below["label"].lower()
    # NOT a measurement: the ~700 K figure must stay labelled as simulation
    assert "numerical-simulation" in below["note"]
    hot_sustained = cool_flame_phase("microgravity", 2.0, "sustained")
    assert hot_sustained["possible"] is False
    assert cool_flame_phase("earth", -5.0, "self_extinguishing")["possible"] is False


def test_payload_includes_flow_regime_and_cool_flame_toggle():
    payload = flame_payload(8.2, 15.0, "microgravity", 0.2, 22.0, "polymer")
    assert payload["flow_regime"]["band"] == "low-flow"
    assert payload["cool_flame_phase"]["possible"] is True
    assert any("cool-flame" in n for n in payload["notes"])
    great = flame_payload(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer")
    assert great["cool_flame_phase"]["possible"] is False
