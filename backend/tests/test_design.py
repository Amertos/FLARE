"""Tests for the inverse design search (backend/engine/design.py).

The claim this module makes is narrow and checkable: the crew's oxygen floor
and the LOC boundary are both `a + b/P`, so they cross once, and everything the
screen shows follows from loc.py. These tests pin the crossing, the two
constraint values at known pressures, and the honesty flags (nominal window,
extrapolated rows) rather than the presentation.

Run: py -m pytest backend/tests -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.engine.design import (
    NOMINAL_WINDOW_PT,
    crew_floor_o2_pct,
    crossover_pressure_psia,
    design_search_payload,
)
from backend.engine.hazard import hazard_vector
from backend.engine.loc import effective_loc

client = TestClient(app)


def _row_at(data: dict, pressure: float) -> dict:
    return min(data["rows"], key=lambda r: abs(r["pressure_psia"] - pressure))


# The 25-step grid from 4.0 to 16.7 psia does not land on 8.2, so the statements
# about named pressures read the `current` row, which is computed at exactly the
# requested pressure by the same code path as the rest of the rows.
def _search(pressure: float, **kw) -> dict:
    return design_search_payload("microgravity", 0.2, 22.0, "polymer",
                                 pressure_psia=pressure, **kw)


# ---------- The two curves ----------

def test_crew_floor_is_partial_pressure_floor():
    # 2.4 psia of O2 in an 8.2 psia cabin needs 29.27% O2.
    assert crew_floor_o2_pct(8.2, 2.4) == pytest.approx(29.268, abs=0.01)
    assert crew_floor_o2_pct(14.7, 2.4) == pytest.approx(16.327, abs=0.01)
    # Doubling pressure halves the fraction needed.
    assert crew_floor_o2_pct(16.4, 2.4) == pytest.approx(
        crew_floor_o2_pct(8.2, 2.4) / 2, abs=0.01
    )


def test_crossover_closed_form_matches_solved_value():
    # (100*2.4 - 200.5/6.89476) / (15.88 - 0.8 + 0.3) at 22 degC, 0.2 m/s.
    assert crossover_pressure_psia("microgravity", 0.2, 22.0) == pytest.approx(
        13.71, abs=0.02
    )
    # Buoyant regimes have a higher boundary, so the crossing comes earlier.
    assert crossover_pressure_psia("earth", 0.2, 22.0) < \
        crossover_pressure_psia("microgravity", 0.2, 22.0)


def test_crossover_row_actually_has_zero_shortfall():
    p_star = crossover_pressure_psia("microgravity", 0.2, 22.0)
    loc = effective_loc(p_star * 6.89476, "microgravity", 0.2, 22.0)
    assert loc == pytest.approx(crew_floor_o2_pct(p_star, 2.4), abs=1e-9)


# ---------- Per-pressure rows ----------

def test_exploration_atmosphere_is_above_the_boundary():
    row = _search(8.2)["current"]
    # 29.27% crew floor vs 18.93% effective LOC: the fire margin is unavoidable.
    assert row["crew_floor_o2_pct"] == pytest.approx(29.27, abs=0.01)
    assert row["loc_pct"] == pytest.approx(18.93, abs=0.01)
    assert row["shortfall_pt"] == pytest.approx(10.34, abs=0.02)
    assert row["window_pt"] == 0.0
    assert row["status"] == "unavoidable_spread"


def test_one_atmosphere_window_is_nominal_not_usable():
    row = _search(14.7)["current"]
    assert row["window_pt"] == pytest.approx(1.03, abs=0.02)
    assert row["window_pt"] < NOMINAL_WINDOW_PT
    assert row["status"] == "nominal_window"


def test_window_widens_with_pressure():
    data = design_search_payload("microgravity", 0.2, 22.0, "polymer", steps=40)
    widths = [r["window_pt"] for r in data["rows"]]
    assert widths == sorted(widths)


def test_rows_never_count_an_unbreathable_mix_as_safe():
    """Above the crew ceiling there is no oxygen to trade away; the window must
    still be bounded by the pO2 ceiling, not just by the boundary."""
    data = design_search_payload("microgravity", 0.2, 22.0, "polymer")
    for r in data["rows"]:
        assert r["window_pt"] == pytest.approx(
            max(0.0, min(r["loc_pct"], r["crew_ceiling_o2_pct"])
                - r["crew_floor_o2_pct"]),
            abs=0.02,
        )


def test_ignition_at_floor_uses_the_engine_hazard_vector():
    row = _search(8.2)["current"]
    expected = hazard_vector(8.2, row["crew_floor_o2_pct"], "microgravity",
                             0.2, 22.0, "polymer")["ignition"]
    assert row["ignition_at_floor"] == pytest.approx(expected, abs=0.2)


# ---------- Verdict and epistemics ----------

def test_verdict_names_the_crossing_pressure():
    data = design_search_payload("microgravity", 0.2, 22.0, "polymer")
    assert data["verdict"] == "window_exists"
    assert data["window"]["min_psia"] == pytest.approx(data["crossover_psia"], abs=0.01)
    assert str(round(data["crossover_psia"], 1)) in data["statement"]


def test_station_air_is_not_labelled_extrapolation():
    # 14.7 psia converts to 101.353 kPa, 0.05 kPa above the published 101.3 kPa
    # anchor: within one UI step, so the row must read as interpolated.
    row = _search(14.7)["current"]
    assert row["flag"] == "INTERPOLATED"
    assert row["status"] == "nominal_window"


def test_window_is_flagged_where_the_curve_is_extrapolated():
    data = design_search_payload("microgravity", 0.2, 22.0, "polymer")
    # Envelope is 50-101.3 kPa = 7.25-14.69 psia, so the window above 14.69
    # psia is extrapolation; the payload must say which part is calibrated.
    lo, hi = data["window"]["inside_data_psia"]
    assert lo == pytest.approx(data["window"]["min_psia"], abs=0.02)
    assert hi == pytest.approx(101.3 / 6.89476, abs=0.02)
    assert _row_at(data, 16.0)["flag"] == "EXTRAPOLATED"


def test_narrow_range_reports_no_window_instead_of_a_fake_one():
    data = design_search_payload("microgravity", 0.2, 22.0, "polymer",
                                 p_min=4.0, p_max=10.0)
    assert data["verdict"] == "no_window_in_range"
    assert data["window"] is None
    assert all(r["window_pt"] == 0.0 for r in data["rows"])


# ---------- Endpoint ----------

def test_endpoint_returns_rows_and_current_state():
    r = client.get("/api/design-search?gravity=microgravity&pressure_psia=8.2")
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 25
    assert body["current"]["pressure_psia"] == 8.2
    assert body["current"]["shortfall_pt"] > 10.0
    assert body["crossover_psia"] == pytest.approx(13.71, abs=0.02)


def test_endpoint_rejects_inverted_range():
    r = client.get("/api/design-search?p_min=15&p_max=10")
    assert r.status_code == 422


def test_endpoint_rejects_unknown_gravity():
    r = client.get("/api/design-search?gravity=jupiter")
    assert r.status_code == 422
