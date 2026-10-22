"""Mission flight scenarios — real-hardware presets the Freefall Lab renders.

Each scenario is a state the engine fully evaluates (hazard vector, effective
LOC, margin, crew side) PLUS a 1 g ground-lab twin evaluated at the same
pressure/O2/flow/material but at earth gravity, and the DELTAS between them.
The twin exists to answer the question a NASA test engineer asks first:
"if I run this condition on the ground bench tomorrow, what does the orbital
environment change?" — drift computed by the engine, never hand-written.

Scenario definitions carry published one-line provenance notes; the fire
quantities are computed from the same hazard functions as everything else.
"""
from __future__ import annotations

from typing import Any, Final

from .hazard import hazard_vector
from .loc import effective_loc

# Presentation thresholds for the delta-column wordings (relative comparison,
# per L4 — nothing here claims an absolute risk).
SPREAD_DELTA_BAND: Final[float] = 5.0
LOC_DELTA_BAND: Final[float] = 0.3

SCENARIOS: Final[list[dict[str, Any]]] = [
    {
        "id": "artemis-lander",
        "name": "Artemis Lunar Lander — pressurised cabin",
        "gravity": "lunar",
        "pressure_psia": 8.2,
        "o2_pct": 34.0,
        "flow_ms": 0.2,
        "temperature_c": 22.0,
        "material_class": "polymer",
        "context": (
            "Moon-landing cabin at the Exploration Atmosphere (8.2 psia / 34% O2). "
            "0.165 g: buoyant transport is weak but present, per Ruff/NIST the "
            "flammability minimum sits near the microgravity value."
        ),
        "provenance": "Exploration Atmosphere: NTRS 20260002050 (ICES-2026-324)· partial-g minima: Ruff, NIST r0200471",
    },
    {
        "id": "gateway-ground-eval",
        "name": "Gateway/EAM — ground bench evaluation",
        "gravity": "earth",
        "pressure_psia": 8.2,
        "o2_pct": 34.0,
        "flow_ms": 0.3,
        "temperature_c": 22.0,
        "material_class": "polymer",
        "context": (
            "The same Exploration Atmosphere evaluated at 1 g on a test bench — "
            "this is the flight-scenario TWIN a ground campaign would actually run, "
            "so its delta against an orbital scenario isolates the gravity effect."
        ),
        "provenance": "Exploration Atmosphere: NTRS 20260002050· 1g LOC trend: ground LOC anchors (dossier §4.3)",
    },
    {
        "id": "gateway-orbital",
        "name": "Gateway — microgravity transit (unpressurised test)",
        "gravity": "microgravity",
        "pressure_psia": 8.2,
        "o2_pct": 34.0,
        "flow_ms": 0.3,
        "temperature_c": 22.0,
        "material_class": "polymer",
        "context": (
            "Same cabin state as the Gateway ground twin but in orbital freefall: "
            "no buoyant transport, the microgravity flow penalty applies, and the "
            "µg-vs-1g boundary offset (−0.8 pt) moves the flammability limit."
        ),
        "provenance": "Exploration Atmosphere: NTRS 20260002050· µg offset: Link et al. 2018 (PMC5760683)",
    },
    {
        "id": "saffire-iv",
        "name": "SAFFIRE-IV — high-pressure payload bay (µg)",
        "gravity": "microgravity",
        "pressure_psia": 14.7,
        "o2_pct": 21.0,
        "flow_ms": 0.2,
        "temperature_c": 22.0,
        "material_class": "composite",
        "context": (
            "SAFFIRE-IV flew deliberate upflow experiments (0–0.6 m/s) at cabin "
            "pressure and oxygen at 12.7 mm PMMA-class samples: the largest "
            "purpose-made microgravity fire dataset. This preset sits at the "
            "SAFFIRE-IV nominal condition with the composite thickness factor."
        ),
        "provenance": "SAFFIRE IV: sphere-based fire tolerance and upflow tests, NASA GRC (CASIS/SAFFIRE series)",
    },
    {
        "id": "iss-depress",
        "name": "ISS — depressurisation sequence (early segment)",
        "gravity": "microgravity",
        "pressure_psia": 10.0,
        "o2_pct": 30.0,
        "flow_ms": 0.2,
        "temperature_c": 22.0,
        "material_class": "textile",
        "context": (
            "The depressurisation path toward the Exploration Atmosphere passes "
            "through exactly this 10.0 psia / 30% O2 segment: equal crew pO2, "
            "HIGHER molar O2 delivered to a flame by diffusion (dossier §3.2), "
            "and low forced flow during the transition."
        ),
        "provenance": "pO2-equivalence trade: dossier §3.2 · µg flow penalty: BASS-II (PMC5760683)",
    },
]

# The canonical A/B pair for the compare panel: a µg scenario and its 1g twin
# at the same non-gravity parameters.
DEFAULT_COMPARE: Final[tuple[str, str]] = ("gateway-orbital", "gateway-ground-eval")


def scenario_payload(pressure_psia: float, o2_pct: float, gravity: str,
                     flow_ms: float, temperature_c: float,
                     material_class: str) -> dict[str, Any]:
    """Full evaluation of one preset for the /api/missions endpoint."""
    vec = hazard_vector(pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
                        material_class)
    eff = effective_loc(pressure_psia * 6.89476, gravity, flow_ms, temperature_c)
    margin = o2_pct - eff
    twin = hazard_vector(pressure_psia, o2_pct, "earth", flow_ms, temperature_c,
                         material_class)
    eff_1g = effective_loc(pressure_psia * 6.89476, "earth", flow_ms, temperature_c)
    margin_1g = o2_pct - eff_1g

    def _word(delta: float, unit: str, smaller_is_riskier: bool = False) -> str:
        """Wording for a delta. margin: larger in 1g = riskier in flight."""
        magnitude = "negligible" if abs(delta) < LOC_DELTA_BAND else "material"
        direction_first = "1g riskier" if smaller_is_riskier == (delta >= 0) else "flight riskier"
        return f"{direction_first} ({magnitude}): {delta:+.2f} {unit}"

    return {
        "inputs": {
            "pressure_psia": pressure_psia,
            "o2_pct": o2_pct,
            "gravity": gravity,
            "flow_ms": flow_ms,
            "temperature_c": temperature_c,
            "material_class": material_class,
        },
        "hazard": vec,
        "effective_loc_pct": round(eff, 2),
        "margin_above_loc_pct": round(margin, 2),
        # 1g TWIN at the same non-gravity parameters: the real-world delta the
        # brief asked for, computed from the same engine (never hand-written).
        "twin_1g": {
            "gravity": "earth",
            "hazard": twin,
            "effective_loc_pct": round(eff_1g, 2),
            "margin_above_loc_pct": round(margin_1g, 2),
        },
        "delta_vs_1g": {
            # Positive means the 1g twin is further from the boundary than
            # flight mode — i.e. flight mode is closer to sustained spread.
            "margin_pt": round(margin_1g - margin, 2),
            "ignition": round(vec["ignition"] - twin["ignition"], 1),
            "spread": round(vec["spread"] - twin["spread"], 1),
            "wording": _word(margin_1g - margin, "pt"),
        },
    }


def missions_payload() -> dict[str, Any]:
    """All presets, fully evaluated, for the mission-scenario picker."""
    out = []
    for s in SCENARIOS:
        full = scenario_payload(s["pressure_psia"], s["o2_pct"], s["gravity"],
                                s["flow_ms"], s["temperature_c"],
                                s["material_class"])
        out.append({
            "id": s["id"],
            "name": s["name"],
            "gravity": s["gravity"],
            "pressure_psia": s["pressure_psia"],
            "o2_pct": s["o2_pct"],
            "flow_ms": s["flow_ms"],
            "temperature_c": s["temperature_c"],
            "material_class": s["material_class"],
            "context": s["context"],
            "provenance": s["provenance"],
            "evaluation": full,
        })
    return {
        "scenarios": out,
        "default_compare": {
            "a": DEFAULT_COMPARE[0],
            "b": DEFAULT_COMPARE[1],
        },
        "note": (
            "Every fire quantity is computed by the same engine functions as "
            "/api/scenario and /api/flame; the presets only fix the inputs. "
            "The cleaner of the two provenance strings is shown verbatim in the UI."
        ),
    }
