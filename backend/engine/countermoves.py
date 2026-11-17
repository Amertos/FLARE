"""Fire-safety levers ("countermoves") for one atmosphere state.

The challenge question is not only "how does flame behave in microgravity" but
"how do we reduce the fire risk of future missions". This module answers the
second half from the same engine the rest of the product uses -- no new model,
no new claims beyond what loc.py/hazard.py already state. Four levers:

  1. cool the cabin toward the 22 degC reference       (temperature offset)
  2. substitute a lower-representative-risk material   (thickness factor)
  3. reduce forced airflow in microgravity            (flow penalty)
  4. trade O2 fraction down to the crew-safe floor    (crew band)

Every lever reports before/after ENGINE output (never a hand-written number),
and every lever carries an epistemic label naming which dossier-backed
quantity produced its effect, so the screen cannot claim more than the model
does. What is NOT engine-modelled is stated as not-applicable instead of
invented (e.g. the flow lever in 1g, where buoyancy supplies transport).

Pure functions. Deterministic. No I/O.
"""
from __future__ import annotations

from typing import Final

from .hazard import (
    PO2_CREW_SAFE_BAND_PSIA,
    THICKNESS_FACTOR_BY_MATERIAL,
    hazard_vector,
    thickness_factor_for,
)
from .loc import (
    TEMP_OFFSET_CAP_PCT,
    TEMP_REFERENCE_C,
    TEMP_SENSITIVITY_PCT_PER_K,
)

# Target settings a lever drives toward. Constants are declared, not hidden in
# the arithmetic: the screen and the tests read them.
COOL_TARGET_C: Final[float] = 18.0      # the UI's own temperature slider floor
FLOW_SUPPRESSION_MS: Final[float] = 0.05  # below the transport-suppression band
_EPS: Final[float] = 1e-9

# Epistemic labels. Each names the dossier-backed quantity a lever acts on:
# a cited direction with a bounded fit magnitude is stated as exactly that,
# and the crew band is labelled as the model construct it is (dossier §4.7
# L5/L6). These strings are rendered verbatim on the screen.
EVIDENCE_TEMPERATURE: Final[str] = (
    "Direction of effect physical (surface temperature governs ignition); "
    f"magnitude {TEMP_OFFSET_CAP_PCT:+.1f} pt/K, capped +/-{TEMP_OFFSET_CAP_PCT:.0f} pt "
    "-- a bounded fit choice, not a measurement (dossier §4.5, limitation L5)."
)
EVIDENCE_MATERIAL: Final[str] = (
    "Representative thickness factor per class -- a bounded fit choice "
    "(dossier §4.5, limitation L5); BASS-II tested fuel thickness/geometry "
    "as explicit variables (NTRS 20210011385)."
)
EVIDENCE_FLOW: Final[str] = (
    "BASS-II near-limit behaviour: in microgravity, reducing forced flow "
    "below ~0.25 m/s degrades O2 transport and raises the effective LOC "
    "(dossier §4.5); BASS-II-04 self-extinguish at 0.1 m/s is the shipped "
    "engine's own reproduced case."
)
EVIDENCE_O2: Final[str] = (
    f"Crew-safe pO2 floor {PO2_CREW_SAFE_BAND_PSIA[0]:.1f} psia is a conservative "
    "planning band chosen by this project -- a model construct, NOT a NASA "
    "requirement (limitation L6)."
)


def countermoves_payload(
    pressure_psia: float,
    o2_pct: float,
    gravity: str,
    flow_ms: float,
    temperature_c: float,
    material_class: str,
) -> dict:
    """Ranked engine-computed fire-safety levers for one atmosphere state.

    Returns { inputs, baseline, levers, notes }. `levers` is the fixed set of
    four (applicable or not, so the screen can say why one is missing);
    `ranked_ids` orders the applicable ones by engine-predicted drop in the
    ignition index, the most transparent ranking the model supports.
    """
    vec = hazard_vector(pressure_psia, o2_pct, gravity, flow_ms,
                        temperature_c, material_class)
    baseline = _summary(vec)

    levers = [
        _lever_temperature(pressure_psia, o2_pct, gravity, flow_ms,
                           temperature_c, material_class, baseline),
        _lever_material(pressure_psia, o2_pct, gravity, flow_ms,
                        temperature_c, material_class, baseline),
        _lever_flow(pressure_psia, o2_pct, gravity, flow_ms,
                    temperature_c, material_class, baseline),
        _lever_o2(pressure_psia, o2_pct, gravity, flow_ms,
                  temperature_c, material_class, baseline),
    ]
    applicable = [l for l in levers if l["applicable"]]
    # Rank by how far the engine says the lever lowers the ignition index
    # (most negative delta first); ties broken by the margin drop. The
    # criterion is published here, not hidden in the UI arithmetic.
    ranked_ids = [
        l["id"] for l in
        sorted(applicable, key=lambda l: (l["delta"]["ignition"],
                                          l["delta"]["margin_above_loc_pct"]))
    ]

    return {
        "inputs": {
            "pressure_psia": pressure_psia,
            "o2_pct": o2_pct,
            "gravity": gravity,
            "flow_ms": flow_ms,
            "temperature_c": temperature_c,
            "material_class": material_class,
        },
        "baseline": baseline,
        "levers": levers,
        "ranked_ids": ranked_ids,
        "notes": [
            "Every before/after figure is computed by the same engine the "
            "trade-space map uses; the ranking is by predicted drop in the "
            "ignition index, then by the margin drop.",
            "Levers act on the FLARE model's own inputs -- they are planning "
            "collateral choices a designer gates on, not equipment "
            "recommendations or operational commands.",
        ]
    }


def _summary(vec: dict) -> dict:
    """Comparable projection of a hazard vector onto the lever report."""
    return {
        "ignition": vec["ignition"],
        "spread": vec["spread"],
        "persistence": vec["persistence"],
        "heat_release": vec["heat_release"],
        "extinction_margin": vec["extinction_margin"],
        "margin_above_loc_pct": vec["margin_above_loc_pct"],
        "crew": vec["crew"],
    }


def _delta(before: dict, after: dict) -> dict:
    # Spread is included beside ignition because the material-class lever acts
    # on the representative thickness factor, which enters the engine through
    # the SPREAD path (F_s -> F_p, F_b), not through the O2 margin: without it
    # that lever would report a zero change while the vector really moves.
    return {
        "ignition": round(after["ignition"] - before["ignition"], 1),
        "spread": round(after["spread"] - before["spread"], 1),
        "margin_above_loc_pct": round(
            after["margin_above_loc_pct"] - before["margin_above_loc_pct"], 2),
    }


def _lever_shape(
    *,
    id: str,
    title: str,
    action: str,
    applicable: bool,
    before: dict,
    after: dict | None,
    evidence: str,
    note: str,
) -> dict:
    if after is not None:
        return {
            "id": id, "title": title, "action": action,
            "applicable": True, "before": before, "after": after,
            "delta": _delta(before, after),
            "evidence_label": evidence, "note": note,
        }
    # Not-applicable levers still carry before/after equal and delta 0 rather
    # than omitting fields, so the screen renders a stable schema for the set.
    return {
        "id": id, "title": title, "action": action,
        "applicable": False, "before": before, "after": before,
        "delta": {"ignition": 0.0, "spread": 0.0, "margin_above_loc_pct": 0.0},
        "evidence_label": evidence, "note": note,
    }


def _lever_temperature(
    pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
    material_class, baseline,
) -> dict:
    if temperature_c <= COOL_TARGET_C + _EPS:
        return _lever_shape(
            id="cool_cabin",
            title="Cool the cabin toward the reference temperature",
            action=f"Cabin is at {temperature_c:.1f} °C, at or below the "
                   f"{COOL_TARGET_C:.1f} °C evaluated floor. No further "
                   "engine-modelled effect on this lever.",
            applicable=False,
            before=baseline, after=None,
            evidence=EVIDENCE_TEMPERATURE,
            note=f"Cooling shifts the boundary by {TEMP_SENSITIVITY_PCT_PER_K:+.1f} "
                 "pt of O2 per K of temperature -- capped, so it can never "
                 "dominate the pressure term.",
        )
    vec = hazard_vector(pressure_psia, o2_pct, gravity, flow_ms,
                        COOL_TARGET_C, material_class)
    after = _summary(vec)
    return _lever_shape(
        id="cool_cabin",
        title="Cool the cabin toward the reference temperature",
        action=f"Cool from {temperature_c:.1f} °C toward {COOL_TARGET_C:.1f} °C "
               "(the 22 °C dossier reference is where every figure in the "
               "validation dossier is drawn; 18 °C is the UI's own slider floor).",
        applicable=True,
        before=baseline, after=after,
        evidence=EVIDENCE_TEMPERATURE,
        note="A warmer cabin lowers the effective LOC (the boundary moves down); "
             "cooling moves it back up. Effect is capped at "
             f"+/-{TEMP_OFFSET_CAP_PCT:.0f} pt of O2.",
    )


def _lever_material(
    pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
    material_class, baseline,
) -> dict:
    # The engine carries one representative thickness factor per class; the
    # safest alternative is the class whose ignition index comes out lowest
    # for THIS state. Computed per class, never a hand-written ranking.
    candidates: list[dict] = []
    for cls, factor in sorted(THICKNESS_FACTOR_BY_MATERIAL.items(),
                              key=lambda kv: kv[1]):
        vec = hazard_vector(pressure_psia, o2_pct, gravity, flow_ms,
                            temperature_c, cls)
        candidates.append({
            "material_class": cls,
            "thickness_factor": factor,
            "ignition": vec["ignition"],
            "spread": vec["spread"],
            "margin_above_loc_pct": vec["margin_above_loc_pct"],
        })
    best = min(candidates, key=lambda c: (c["ignition"], c["spread"]))
    if best["material_class"] == material_class:
        return _lever_shape(
            id="material_substitution",
            title="Substitute a lower-representative-risk material class",
            action=f"{material_class} is already the "
                   "lowest-representative-risk class at this state "
                   "(engine-computed, not a table lookup).",
            applicable=False,
            before=baseline, after=None,
            evidence=EVIDENCE_MATERIAL,
            note="The evaluation is per-state: a class with a smaller "
                 "representative thickness factor is not automatically safer "
                 "once the engine's flow conditions are applied.",
        )
    vec = hazard_vector(pressure_psia, o2_pct, gravity, flow_ms,
                        temperature_c, best["material_class"])
    after = _summary(vec)
    table = ", ".join(
        f"{c['material_class']} {c['thickness_factor']:.2f}" for c in candidates
    )
    return _lever_shape(
        id="material_substitution",
        title="Substitute a lower-representative-risk material class",
        action=(f"Substitute {material_class} (representative thickness factor "
                f"{thickness_factor_for(material_class):.2f}) with "
                f"{best['material_class']} "
                f"({best['thickness_factor']:.2f})."),
        applicable=True,
        before=baseline, after=after,
        evidence=EVIDENCE_MATERIAL,
        note=f"Representative factors by class, stated in code: {table}. "
             "The class-factor mapping is a fit choice of this engine, not a "
             "materials-science measurement per material.",
    )


def _lever_flow(
    pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
    material_class, baseline,
) -> dict:
    if gravity != "microgravity":
        return _lever_shape(
            id="reduce_flow",
            title="Reduce forced airflow (burn-zone protocol)",
            action="Not engine-modelled in this gravity regime.",
            applicable=False,
            before=baseline, after=None,
            evidence=EVIDENCE_FLOW,
            note="The flow penalty actuates in microgravity only: in 1g and "
                 "partial-g, buoyancy-driven convection supplies transport "
                 "(dossier §4.5), so reducing forced flow does not raise the "
                 "effective LOC here. Saying this is the honest alternative "
                 "to presenting a 0-delta lever as a recommendation.",
        )
    if flow_ms <= FLOW_SUPPRESSION_MS + _EPS:
        return _lever_shape(
            id="reduce_flow",
            title="Reduce forced airflow (burn-zone protocol)",
            action=f"Flow is at {flow_ms:.2f} m/s, at or below the "
                   f"{FLOW_SUPPRESSION_MS:.2f} m/s suppression band on the "
                   "engine's flow modifier. No further modelled effect.",
            applicable=False,
            before=baseline, after=None,
            evidence=EVIDENCE_FLOW,
            note="This lever is a LOCAL burn-zone measure near the boundary, "
                 "not a design rule for cabin ventilation: sustained forced "
                 "flow is how a spacecraft removes heat, dust and combustion "
                 "aerosols in normal operations.",
        )
    vec = hazard_vector(pressure_psia, o2_pct, gravity, FLOW_SUPPRESSION_MS,
                        temperature_c, material_class)
    after = _summary(vec)
    return _lever_shape(
        id="reduce_flow",
        title="Reduce forced airflow (burn-zone protocol)",
        action=f"Reduce forced flow from {flow_ms:.2f} m/s to "
               f"{FLOW_SUPPRESSION_MS:.2f} m/s in the affected region.",
        applicable=True,
        before=baseline, after=after,
        evidence=EVIDENCE_FLOW,
        note="In microgravity, low forced flow degrades O2 transport to the "
             "flame front -- the effective LOC rises and a marginal flame can "
             "self-extinguish. The magnitude is a bounded fit choice (L5); "
             "the BASS-II-04 check is the shipped engine's confirmable case.",
    )


def _lever_o2(
    pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
    material_class, baseline,
) -> dict:
    po2_min, po2_max = PO2_CREW_SAFE_BAND_PSIA
    o2_floor = 100.0 * po2_min / pressure_psia
    if o2_pct <= o2_floor + _EPS:
        return _lever_shape(
            id="o2_to_crew_floor",
            title=f"Trade O2 fraction down to the crew band floor "
                  f"({po2_min:.1f} psia pO2)",
            action=(f"O2 is already at or below the crew-safe floor for this "
                    f"pressure ({o2_floor:.1f}% at {pressure_psia:.1f} psia). "
                    "Raising total pressure instead is the other side of the "
                    "same trade and is the whole point of the Pareto panel."),
            applicable=False,
            before=baseline, after=None,
            evidence=EVIDENCE_O2,
            note="A lower O2 fraction at the same pressure moves the margin "
                 "below the boundary on the map. The crew band itself is a "
                 "model construct (L6) -- pressure-reduction lower limits and "
                 "O2-toxicity exposure limits are not modelled.",
        )
    o2_after = o2_floor
    vec = hazard_vector(pressure_psia, o2_after, gravity, flow_ms,
                        temperature_c, material_class)
    after = _summary(vec)
    return _lever_shape(
        id="o2_to_crew_floor",
        title=f"Trade O2 fraction down to the crew band floor "
              f"({po2_min:.1f} psia pO2)",
        action=(f"Drop O2 from {o2_pct:.1f}% to {o2_after:.1f}% at "
                f"{pressure_psia:.1f} psia -- the largest O2 reduction the "
                "engine's crew band permits at this pressure. Crew pO2 lands "
                "exactly on the band floor."),
        applicable=True,
        before=baseline, after=after,
        evidence=EVIDENCE_O2,
        note="Presses on the crew band floor (L6, a model construct not a "
             "NASA requirement). The trade it names on the map is the same "
             "one the demo walks through: same crew pO2, different fire "
             "vector.",
    )
