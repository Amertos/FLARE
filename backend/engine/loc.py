"""FLARE engine — LOC(P) boundary with gravity and flow modifiers.

Derived and validated in docs/SCIENTIFIC-VALIDATION-DOSSIER.md §4 (model v2).
Pure functions only: no I/O, no state.

Model v2 (physics-consistent):
  LOC_base(P) = LOC_A + LOC_B / P      [1g ground trend; LOC DECREASES as P increases]
  LOC_eff(P, g, v) = LOC_base(P) + gravity_offset(g) * flow_modifier(v)
"""
from __future__ import annotations

from typing import Final

# Least-squares fit to ground (1g) LOC-vs-pressure anchors for PMMA-class
# materials (dossier §4.3 v2): (50 kPa, 20%), (70 kPa, 18.5%), (101.3 kPa, 18%).
# Max anchor error 0.25 pt; dLOC/dP < 0 as published.
LOC_A: Final[float] = 15.88   # %
LOC_B: Final[float] = 200.5   # %·kPa

GRAVITY_LABELS: Final[dict[str, str]] = {
    "microgravity": "Microgravity (~0 g)",
    "lunar": "Lunar surface (0.165 g)",
    "mars": "Mars surface (0.38 g)",
    "earth": "Earth (1 g)",
}

# Gravity offsets (pts of O2) relative to the 1g ground trend (dossier §4.5):
# Link 2018: microgravity sustains spread ~1 pt lower than 1g; Ruff (NIST):
# lunar/Mars minima are near the microgravity value. Fit choices are stated
# here per dossier limitation #5.
GRAVITY_OFFSET_PCT: Final[dict[str, float]] = {
    "microgravity": -0.8,
    "lunar": -0.75,
    "mars": -0.7,
    "earth": 0.0,
}

# Ambient-temperature offset on the LOC boundary (pts of O2 per degC), relative
# to the 22 degC reference of every figure in the dossier. Ignition of a solid
# is governed by its SURFACE temperature: a warmer cabin raises the surface
# temperature and therefore lowers the O2 concentration at which spread is
# sustained. The direction of effect is physical; the magnitude (0.1 pt/K, hard
# capped at +/-2 pt) is a bounded fit choice stated here, exactly like the flow
# penalty, per dossier §4.7 L5.
#
# Earlier builds instead multiplied the ignition index by 2**((T-22)/10), which
# drove components past the 100 they are presented as and saturated most of the
# trade-space map above ~24 degC (measured: 39% of cells pinned at 30 degC).
# Temperature now shifts the boundary, so every component stays inside 0-100 and
# the map keeps its dynamic range.
TEMP_REFERENCE_C: Final[float] = 22.0
TEMP_SENSITIVITY_PCT_PER_K: Final[float] = 0.1
TEMP_OFFSET_CAP_PCT: Final[float] = 2.0

# Calibration envelope of the LOC CURVE on the pressure axis (kPa): the range
# over which LOC(P) was fitted to 1g ground anchors. Outside it the curve is
# flagged EXTRAPOLATED and the map hatches the region rather than colouring it.
#
# This is a statement about the curve, not about the database: the record set
# reaches 115.1 kPa because of the Apollo 1 historical reference, which is not
# a controlled LOC measurement. The record-coverage range is a separate
# quantity -- see engine.epistemics.evidence_pressure_range.
P_ENVELOPE_KPA: Final[tuple[float, float]] = (50.0, 101.3)


def loc_percent(p_kpa: float) -> float:
    """1g-ground LOC in % O2 as a function of total pressure in kPa."""
    if p_kpa <= 0:
        raise ValueError("pressure must be positive")
    return LOC_A + LOC_B / p_kpa


def flow_penalty_pct(gravity: str, flow_ms: float) -> float:
    """Additive LOC penalty (pts) from reduced forced airflow.

    Direction of effect from BASS-II near-limit behavior (dossier §4.5):
    in MICROGRAVITY at near-limit O2, reducing forced flow below ~0.25 m/s
    degrades oxygen transport and RAISES the effective LOC (spread becomes
    harder to sustain). In 1g/partial-g, buoyancy-driven convection supplies
    transport, so the penalty is negligible. Magnitude is a bounded fit
    choice stated here (dossier §4.7 #5). BASS-II-04 check: 17% O2 @ 0.1 m/s
    µg -> penalty 0.9 pt -> predicts self-extinguish (observed).
    """
    if gravity != "microgravity":
        return 0.0
    if flow_ms >= 0.25:
        return 0.0
    return 1.5 * max(0.0, (0.25 - flow_ms) / 0.25)


def gravity_loc_offset_pct(gravity: str) -> float:
    """Additive LOC offset by gravity regime (dossier §4.5)."""
    return GRAVITY_OFFSET_PCT[gravity]


def temperature_loc_offset_pct(temperature_c: float) -> float:
    """Additive LOC offset (pts) from ambient temperature (dossier §4.7 L5).

    Negative above the 22 degC reference (warmer -> lower effective LOC) and
    capped, so the modifier can never dominate the pressure term.
    """
    raw = -TEMP_SENSITIVITY_PCT_PER_K * (temperature_c - TEMP_REFERENCE_C)
    return max(-TEMP_OFFSET_CAP_PCT, min(TEMP_OFFSET_CAP_PCT, raw))


def effective_loc(p_kpa: float, gravity: str, flow_ms: float = 0.2,
                  temperature_c: float = TEMP_REFERENCE_C) -> float:
    """Effective LOC % = ground trend + gravity + flow + temperature offsets.

    Every modifier is additive on the boundary, so the returned value stays a
    single O2 percentage and the derived hazard indices cannot leave 0-100.
    """
    return (loc_percent(p_kpa) + gravity_loc_offset_pct(gravity)
            + flow_penalty_pct(gravity, flow_ms)
            + temperature_loc_offset_pct(temperature_c))


def epistemic_flag_for_pressure(p_kpa: float) -> str:
    """Whether the LOC value at this pressure is inside the data envelope."""
    lo, hi = P_ENVELOPE_KPA
    if p_kpa < lo or p_kpa > hi:
        return "EXTRAPOLATED"
    return "INTERPOLATED"
