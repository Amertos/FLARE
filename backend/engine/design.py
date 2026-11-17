"""Atmosphere design search: is there ANY breathable mix below the boundary?

Every other endpoint starts from an atmosphere and reports its hazard. This one
asks the inverse design question that a mission architect actually has to
answer, and that the trade-space map cannot answer by eye:

    For each cabin pressure, what oxygen fraction does the crew need, and is
    that fraction above or below the LOC boundary?

The two constraints move in opposite directions with pressure:

  crew floor   O2_min(P) = 100 * pO2_min / P      falls as 1/P
  fire limit   LOC(P)    = LOC_A + LOC_B / P + offsets   falls as 1/P too

but the crew floor falls FASTER (its numerator is 240 vs LOC_B/kPa = 29.1), so
the floor is above the boundary at low pressure and below it at high pressure.
The two curves cross at exactly one pressure, which can be solved in closed
form because every modifier in loc.py is additive and pressure-independent:

    P* = (100 * pO2_min - LOC_B / KPA_PER_PSIA) / (LOC_A + offsets)

Below P* no breathable atmosphere can stay under the boundary: the cabin air a
crew needs is itself above the concentration that sustains spread. Above P* a
window opens, and its width is the design margin the mission actually has.

This is not a new physical claim -- it is loc.py and hazard.py rearranged. The
module adds no constants beyond the psia<->kPa conversion that the API layer
already uses, and it reports the window's epistemic flag (the upper part of the
window lies outside the calibrated pressure envelope).

Pure functions. Deterministic. No I/O.
"""
from __future__ import annotations

from typing import Final

from .hazard import PO2_CREW_SAFE_BAND_PSIA, hazard_vector
from .loc import (
    LOC_A,
    LOC_B,
    P_ENVELOPE_KPA,
    effective_loc,
    inside_envelope,
    flow_penalty_pct,
    gravity_loc_offset_pct,
    temperature_loc_offset_pct,
)

# Same conversion as backend/app/main.py (PSI_TO_KPA). Kept local so this
# module stays a pure engine unit with no import from the API layer.
KPA_PER_PSIA: Final[float] = 6.89476

# Below this width a "window" is smaller than the model's own stated
# uncertainty band (+/-1.5 pt of margin, dossier §4.7 L3), so it is reported as
# nominal rather than usable. Declared here, read by the tests and the screen.
NOMINAL_WINDOW_PT: Final[float] = 1.5


def crew_floor_o2_pct(pressure_psia: float, pO2_min: float) -> float:
    """O2 fraction (%) that gives the crew the minimum acceptable pO2."""
    return 100.0 * pO2_min / pressure_psia


def crossover_pressure_psia(gravity: str, flow_ms: float, temperature_c: float,
                            pO2_min: float = PO2_CREW_SAFE_BAND_PSIA[0]) -> float | None:
    """Pressure at which the crew floor equals the effective LOC boundary.

    Closed form: both sides are `a + b/P`, so the crossing is
    (100*pO2_min - b) / a. Returns None when the boundary has no positive
    pressure-independent term (then the crew floor is never below it), and
    0.0 when the numerator is non-positive (every pressure is fire-safe).
    """
    a = (LOC_A + gravity_loc_offset_pct(gravity)
         + flow_penalty_pct(gravity, flow_ms)
         + temperature_loc_offset_pct(temperature_c))
    if a <= 0:
        return None
    b = LOC_B / KPA_PER_PSIA
    numerator = 100.0 * pO2_min - b
    if numerator <= 0:
        return 0.0
    return numerator / a


def _row(pressure_psia: float, gravity: str, flow_ms: float, temperature_c: float,
         material_class: str, pO2_min: float, pO2_max: float) -> dict:
    kpa = pressure_psia * KPA_PER_PSIA
    inside = inside_envelope(kpa)
    loc = effective_loc(kpa, gravity, flow_ms, temperature_c)
    floor = crew_floor_o2_pct(pressure_psia, pO2_min)
    ceiling = crew_floor_o2_pct(pressure_psia, pO2_max)
    ceiling = min(100.0, ceiling)
    # Breathable band that is simultaneously below the boundary. Negative width
    # means the crew floor is ABOVE the boundary (fire unavoidable); a positive
    # but tiny width is a nominal window, not a usable one.
    width = min(loc, ceiling) - floor
    ignition_at_floor = hazard_vector(
        pressure_psia, min(floor, 100.0), gravity, flow_ms, temperature_c,
        material_class,
    )["ignition"]
    # Status describes the WINDOW (the design result); `flag` separately says
    # whether the boundary underneath it is interpolated or extrapolated. An
    # earlier pass let "outside_data" overwrite the window status, which hid
    # the fact that a low-pressure row is fire-unavoidable.
    if width <= 0:
        status = "unavoidable_spread"
    elif width < NOMINAL_WINDOW_PT:
        status = "nominal_window"
    else:
        status = "usable_window"
    return {
        "pressure_psia": round(pressure_psia, 3),
        "pressure_kpa": round(kpa, 2),
        "crew_floor_o2_pct": round(floor, 2),
        "crew_ceiling_o2_pct": round(ceiling, 2),
        "loc_pct": round(loc, 2),
        "shortfall_pt": round(max(0.0, floor - loc), 2),
        "window_pt": round(max(0.0, width), 2),
        "ignition_at_floor": round(ignition_at_floor, 1),
        "flag": "INTERPOLATED" if inside else "EXTRAPOLATED",
        "status": status,
    }


def design_search_payload(
    gravity: str,
    flow_ms: float,
    temperature_c: float,
    material_class: str,
    p_min: float = 4.0,
    p_max: float = 16.7,
    steps: int = 25,
    pressure_psia: float | None = None,
    pO2_min: float = PO2_CREW_SAFE_BAND_PSIA[0],
    pO2_max: float = PO2_CREW_SAFE_BAND_PSIA[1],
) -> dict:
    """Per-pressure rows + the crossing pressure + a stated verdict.

    `pressure_psia` (optional) is the state the rest of the console is showing;
    it is added as `current` so the screen can place a marker without
    recomputing anything client-side.
    """
    if p_max <= p_min:
        raise ValueError("p_max must exceed p_min")
    if steps < 2:
        raise ValueError("steps must be at least 2")

    ps = [p_min + (p_max - p_min) * i / (steps - 1) for i in range(steps)]
    rows = [_row(p, gravity, flow_ms, temperature_c, material_class,
                 pO2_min, pO2_max) for p in ps]

    crossing = crossover_pressure_psia(gravity, flow_ms, temperature_c, pO2_min)
    window = None
    if crossing is not None and crossing < p_max:
        lo = max(crossing, p_min)
        window = {"min_psia": round(lo, 3), "max_psia": round(p_max, 3)}
        # How much of that window is inside the pressure envelope the curve was
        # fitted on; the rest is extrapolation and is flagged as such.
        env_lo = P_ENVELOPE_KPA[0] / KPA_PER_PSIA
        env_hi = P_ENVELOPE_KPA[1] / KPA_PER_PSIA
        w_lo, w_hi = max(lo, env_lo), min(p_max, env_hi)
        window["inside_data_psia"] = (
            [round(w_lo, 3), round(w_hi, 3)] if w_hi > w_lo else None
        )

    inside_rows = [r for r in rows if r["flag"] == "INTERPOLATED"]
    pool = inside_rows or rows
    best = max(pool, key=lambda r: r["window_pt"])

    current = None
    if pressure_psia is not None:
        current = _row(pressure_psia, gravity, flow_ms, temperature_c,
                       material_class, pO2_min, pO2_max)

    if crossing is None:
        verdict = "no_fire_limit"
        statement = (
            "The effective boundary has no positive pressure-independent term, "
            "so the crew floor is below it at every pressure: no design conflict."
        )
    elif crossing >= p_max:
        verdict = "no_window_in_range"
        statement = (
            f"No breathable mix stays below the boundary anywhere in "
            f"{p_min:.1f}-{p_max:.1f} psia: the two curves would only cross at "
            f"{crossing:.1f} psia, above the searched range."
        )
    else:
        verdict = "window_exists"
        statement = (
            f"A breathable atmosphere can sit below the boundary only above "
            f"{crossing:.1f} psia (the pressure where the crew floor and the "
            f"effective LOC cross). The widest such window inside the "
            f"calibrated data is {best['window_pt']:.2f} O2 pt at "
            f"{best['pressure_psia']:.1f} psia, against a stated model "
            f"uncertainty of +/-1.5 pt."
        )
        if best["window_pt"] < NOMINAL_WINDOW_PT:
            statement += (
                " That window is narrower than the model's own uncertainty: it "
                "is a nominal result, not a usable design point."
            )

    return {
        "inputs": {
            "gravity": gravity,
            "flow_ms": flow_ms,
            "temperature_c": temperature_c,
            "material_class": material_class,
            "p_min_psia": p_min,
            "p_max_psia": p_max,
            "steps": steps,
            "po2_min_psia": pO2_min,
            "po2_max_psia": pO2_max,
        },
        "rows": rows,
        "crossover_psia": round(crossing, 3) if crossing is not None else None,
        "window": window,
        "best": best,
        "current": current,
        "verdict": verdict,
        "statement": statement,
        "nominal_window_pt": NOMINAL_WINDOW_PT,
        "notes": [
            "Both curves are loc.py rearranged; no new physical constant is "
            "introduced here (dossier §4.3, §4.5).",
            "The window is a model result, not a recommendation: it says which "
            "O2 fractions satisfy two stated constraints, not which atmosphere "
            "a program should fly.",
            "Above the calibrated envelope (P_ENVELOPE_KPA) the LOC curve is "
            "extrapolation and every row carrying it says so.",
        ],
    }
