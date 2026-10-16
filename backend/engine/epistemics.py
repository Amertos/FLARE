"""Epistemic classification and evidence coverage (dossier §5)."""
from __future__ import annotations

from typing import Final

from .similarity import similarity

P_TOL_KPA: Final[float] = 8.0     # pressure-axis tolerance (dossier §5, tested)
O2_TOL_PCT: Final[float] = 2.5
MIN_NEARBY: Final[int] = 2        # below this -> INSUFFICIENT
P_WEIGHT_MAX: Final[float] = 10.0
O2_WEIGHT_MAX: Final[float] = 20.0

G_WEIGHT: Final[float] = 0.20
M_WEIGHT: Final[float] = 0.10
P_WEIGHT: Final[float] = 0.35
O2_WEIGHT: Final[float] = 0.35


def evidence_pressure_range(experiments: list[dict]) -> tuple[float, float]:
    """Pressure range actually covered by the record set (kPa).

    Deliberately NOT the same quantity as ``loc.P_ENVELOPE_KPA`` (50-101.3
    kPa), and the two are reported separately wherever both are relevant:

      * "is the LOC *curve* calibrated here?"  -> ``loc.P_ENVELOPE_KPA``
      * "is there any *record* near here?"     -> this range

    The record set reaches 115.1 kPa only because of the Apollo 1 historical
    reference, which is not a controlled LOC measurement; the LOC curve was
    never calibrated there. Collapsing the two into one number would either
    overstate the curve's validity or hide Apollo 1 from the evidence view.
    """
    if not experiments:
        return (0.0, 0.0)
    return (
        min(float(e["pressure_kpa"]) for e in experiments),
        max(float(e["pressure_kpa"]) for e in experiments),
    )


def coverage(p_kpa: float, o2_pct: float, gravity: str, material_class: str,
             experiments: list[dict]) -> float:
    """Evidence coverage in [0,1]: best similarity across the record set."""
    if not experiments:
        return 0.0
    return max(similarity(p_kpa, o2_pct, gravity, material_class, e) for e in experiments)


def classify(p_kpa: float, o2_pct: float, gravity: str, material_class: str,
             experiments: list[dict]) -> str:
    """Observed / Interpolated / Extrapolated / Insufficient (dossier §5 rules)."""
    if not experiments:
        return "INSUFFICIENT"
    nearby = [
        e for e in experiments
        if abs(float(e["pressure_kpa"]) - p_kpa) <= P_TOL_KPA
        and abs(float(e["o2_pct"]) - o2_pct) <= O2_TOL_PCT
        and e.get("gravity", "microgravity") == gravity
        and e.get("material_class", "") == material_class
    ]
    if len(nearby) >= 1:
        return "OBSERVED"
    lo, hi = evidence_pressure_range(experiments)
    inside = lo <= p_kpa <= hi
    if len(nearby) < MIN_NEARBY and inside:
        return "INTERPOLATED"
    if not inside:
        return "EXTRAPOLATED"
    return "INSUFFICIENT"
