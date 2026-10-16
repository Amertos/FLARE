"""Fire Hazard Vector derivation (dossier §2.2, §3, §4.6).

Pure functions. Deterministic. Every output is a function of the state only.
"""
from __future__ import annotations

from typing import Final

from .loc import effective_loc

SEA_LEVEL_PO2_PSIA: Final[float] = 14.7 * 0.21  # 3.087 psia (dossier §3.1)
PO2_CREW_SAFE_BAND_PSIA: Final[tuple[float, float]] = (2.4, 3.4)  # dossier §3.4


def po2_psia(pressure_psia: float, o2_pct: float) -> float:
    """Oxygen partial pressure in psia (definitional; dossier §3.1)."""
    return pressure_psia * o2_pct / 100.0


def po2_normoxia_pct(pressure_psia: float, o2_pct: float) -> float:
    return 100.0 * po2_psia(pressure_psia, o2_pct) / SEA_LEVEL_PO2_PSIA


def crew_safe(pressure_psia: float, o2_pct: float) -> bool:
    lo, hi = PO2_CREW_SAFE_BAND_PSIA
    return lo <= po2_psia(pressure_psia, o2_pct) <= hi


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def hazard_vector(
    pressure_psia: float,
    o2_pct: float,
    gravity: str,
    flow_ms: float = 0.2,
    temperature_c: float = 22.0,
    material_class: str = "polymer",
    thickness_factor: float = 1.0,
) -> dict:
    """Compute the 5-component Fire Hazard Vector + crew side (dossier §4.6).

    Returns dict with ignition, spread, persistence, heat_release,
    extinction_margin (0-100) and crew block (pO2, normoxia %, safe flag).
    """
    p_kpa = pressure_psia * 6.89476
    loc_eff = effective_loc(p_kpa, gravity, flow_ms)
    margin_pct = o2_pct - loc_eff  # >0 above boundary (more flammable)

    # Ignition: normalized margin above effective LOC (dossier §4.6), plus a
    # small Arrhenius-scaled temperature term referenced to 22 C.
    # Normalization: 25 pts of margin spans the useful range so mid-range
    # counterfactuals remain responsive (saturation only at extreme margins).
    arr = 2.0 ** ((temperature_c - 22.0) / 10.0)  # doubles per +10 C
    fi = _clamp01(margin_pct / 25.0) * 100.0 * arr
    # Below-boundary ignition tendency is near-zero but not exactly zero
    # (pilot sources exist): small floor scaled by depth below boundary.
    if margin_pct < 0:
        fi = max(0.0, 8.0 + margin_pct * 1.2) * arr

    # Spread: ignition x flow factor (microgravity: low flow suppresses spread,
    # BASS-II; 1g: buoyancy supplies transport, weaker v-dependence).
    if gravity == "microgravity":
        flow_factor = _clamp01(flow_ms / 0.3) * 0.85 + 0.15
    else:
        flow_factor = _clamp01(flow_ms / 0.1) * 0.2 + 0.8
    fs = fi * flow_factor * thickness_factor

    # Persistence: thermal-mass effect via thickness (dossier §4.6).
    fp = fs * _clamp01(0.4 + 0.6 * thickness_factor)

    # Heat release: relative intensity on the BASS-II frame (<100 W glovebox
    # scale; FLARE reports relative, never absolute W for cabin scale).
    fb = fp * 0.9

    # Extinction margin: how far O2 must drop to cross below effective LOC.
    fe = _clamp01(margin_pct / 10.0) * 100.0

    return {
        "ignition": round(fi, 1),
        "spread": round(fs, 1),
        "persistence": round(fp, 1),
        "heat_release": round(fb, 1),
        "extinction_margin": round(fe, 1),
        "crew": {
            "po2_psia": round(po2_psia(pressure_psia, o2_pct), 2),
            "normoxia_pct": round(po2_normoxia_pct(pressure_psia, o2_pct), 1),
            "crew_safe": crew_safe(pressure_psia, o2_pct),
        },
        "effective_loc_pct": round(loc_eff, 2),
        "margin_above_loc_pct": round(margin_pct, 2),
    }
