"""Question routing and answer composition for /api/ask.

Design rule that governs this module (README design rule 4, dossier §8):

    The engine is deterministic and no language model is called anywhere in
    this build. So a question cannot be *narrated* by a model — but it must
    still *steer* the answer, otherwise the input box is a lie.

How it steers: the question is routed by an explicit, inspectable keyword model
into one of the intents below; the intent selects which engine quantities get
computed and in which order they are reported. Every number in every answer is
produced by the same pure engine functions the rest of the product uses —
nothing is generated, nothing is estimated, and the routing decision is
returned to the client so the user can see why the answer looks the way it
does. An answer therefore always describes *this* atmosphere, and it answers
*this* question as far as the model can. When the question falls outside what
the engine covers, the router says so in `intent: "out_of_scope"` instead of
composing something plausible.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from .backtest import leave_one_out
from .epistemics import classify, coverage
from .hazard import (
    MATERIAL_CLASSES,
    PO2_CREW_SAFE_BAND_PSIA,
    crew_safe,
    hazard_vector,
    po2_normoxia_pct,
    po2_psia,
    thickness_factor_for,
)
from .loc import (
    P_ENVELOPE_KPA,
    TEMP_REFERENCE_C,
    effective_loc,
    epistemic_flag_for_pressure,
    flow_penalty_pct,
    gravity_loc_offset_pct,
    loc_percent,
    temperature_loc_offset_pct,
)
from .records import KIND_EXPERIMENT, KIND_LABELS, partition, record_kind
from .similarity import rank_experiments


@dataclass(frozen=True)
class Atmosphere:
    """The state under discussion — exactly the sliders the user is looking at."""

    pressure_psia: float
    o2_pct: float
    gravity: str
    flow_ms: float
    temperature_c: float
    material_class: str

    @property
    def p_kpa(self) -> float:
        return self.pressure_psia * 6.89476


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------

# (intent -> keyword -> weight). Multi-word phrases are matched as substrings;
# single words are matched on word boundaries so "loc" never fires inside
# "block" and "vs" never fires inside "advised". Weights make an explicit
# phrase ("limiting oxygen concentration") outrank an incidental word.
_KEYWORDS: Final[dict[str, dict[str, float]]] = {
    "loc_boundary": {
        "limiting oxygen concentration": 4.0, "loc": 3.0, "boundary": 2.5,
        "flammability limit": 3.0, "flammable": 2.0, "threshold": 2.0,
        "sustained spread": 2.5, "limit": 1.0,
    },
    "crew_physiology": {
        "po2": 4.0, "partial pressure": 3.0, "hypoxia": 3.5, "normoxia": 3.0,
        "crew": 2.0, "physiolog": 2.5, "oxygen toxicity": 3.0, "breath": 2.0,
        "safe for people": 2.5, "crew safe": 3.0, "alveolar": 3.0,
    },
    "hazard_components": {
        "hazard vector": 4.0, "hazard": 2.5, "component": 2.0, "spread": 1.5,
        "persistence": 2.5, "heat release": 3.0, "extinction": 2.5,
        "ignition index": 3.0, "which risk": 1.5,
    },
    "evidence_coverage": {
        "evidence": 3.0, "coverage": 3.0, "how sure": 3.0, "how confident": 3.0,
        "confidence": 2.5, "data": 1.5, "which experiments": 3.0,
        "support": 1.5, "citation": 2.0, "source": 1.5, "uncertain": 2.5,
    },
    "comparison": {
        "vs": 2.5, "versus": 3.0, "compare": 3.0, "than": 1.5, "difference": 2.0,
        "why is": 1.5, "riskier": 2.5, "more dangerous": 2.5, "safer": 2.5,
        "trade": 1.5, "atmosphere": 0.8,
    },
    "material_effect": {
        "material": 3.0, "polymer": 3.0, "textile": 3.0, "insulation": 3.0,
        "composite": 3.0, "thickness": 3.0, "fabric": 2.0, "foam": 2.0,
        "sample": 1.5,
    },
    "flow_effect": {
        "flow": 3.0, "airflow": 3.5, "ventilation": 3.0, "velocity": 2.0,
        "m/s": 3.0, "fan": 2.5, "air movement": 2.5, "convection": 2.5,
    },
    "temperature_effect": {
        "temperature": 3.5, "temp": 2.5, "thermal": 2.5, "warm": 3.0, "hot": 2.0,
        "cold": 2.0, "cool": 1.5, "celsius": 3.0, "cabin heat": 3.0,
    },
    "pressure_effect": {
        "pressure": 3.0, "psia": 3.0, "kpa": 3.0, "depressur": 3.0,
        "total pressure": 3.5, "altitude": 2.5,
    },
    "validation": {
        "valid": 2.5, "backtest": 4.0, "accuracy": 3.5, "leave-one-out": 4.0,
        "how accurate": 4.0, "were you right": 3.0, "tested": 2.0,
        "trust": 2.0, "wrong": 2.0, "error": 1.5,
    },
    # what_if fires on an explicit conditional. A bare comparative verb
    # ("lower", "raise") is deliberately weak: "why does lower pressure raise
    # the LOC?" is a question about the boundary, not a what-if scenario, and
    # weighting the verbs higher swallowed it.
    "what_if": {
        "what if": 5.0, "what happens if": 5.0, "if we": 3.0, "if i": 2.5,
        "raise": 1.0, "lower": 1.0, "increase": 1.0, "decrease": 1.0,
        "reduce": 1.0, "drop": 1.0,
    },
}

# A question that is plainly outside the engine's scope is routed to
# out_of_scope and answered with a statement of what FLARE does cover, rather
# than with a confident paragraph about the current atmosphere.
_OUT_OF_SCOPE: Final[tuple[str, ...]] = (
    "how many astronauts", "who won", "launch schedule", "launch date",
    "price", "cost", "budget", "mission schedule", "radiation dose",
    "smolder", "smoulder", "smoldering",
    "write me", "write a poem", "poem", "story", "weather", "stock", "joke",
)

_NUM_PCT: Final[re.Pattern[str]] = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)")
_NUM_PSIA: Final[re.Pattern[str]] = re.compile(r"(\d+(?:\.\d+)?)\s*(?:psia|psi)\b")
_NUM_KPA: Final[re.Pattern[str]] = re.compile(r"(\d+(?:\.\d+)?)\s*kpa\b")
_NUM_MS: Final[re.Pattern[str]] = re.compile(r"(\d+(?:\.\d+)?)\s*m/s")


def _hits(question: str, table: dict[str, float]) -> list[str]:
    """Keywords that fire on a question.

    Phrases are matched as substrings; single words are matched as prefixes on a
    word boundary, so "warm" catches "warmer"/"warming" and "valid" catches
    "validation" — a user typing natural language is not typing exact tokens.
    """
    q = question.lower()
    matched = []
    for keyword, _weight in table.items():
        if " " in keyword:
            if keyword in q:
                matched.append(keyword)
        elif re.search(rf"\b{re.escape(keyword)}", q):
            matched.append(keyword)
    return matched


def route(question: str) -> tuple[str, list[str], float]:
    """Return (intent, matched_keywords, share) for a question.

    `share` is the winning intent's score divided by the total score across all
    intents — a routing confidence the UI can show honestly, instead of
    pretending the router is certain when several topics tie.

    Ties are broken by the declaration order of ``_KEYWORDS``, so routing is
    deterministic and a question that genuinely touches two topics always lands
    in the same intent. That intent's answer still reports the other quantity
    (a boundary question reports the pressure effect, and vice versa), so a
    near-tie costs ordering, not information.
    """
    q = (question or "").lower()
    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for intent, table in _KEYWORDS.items():
        hits = _hits(q, table)
        if not hits:
            continue
        scores[intent] = sum(table[k] for k in hits)
        matched[intent] = hits
    if not scores:
        return "general", [], 0.0
    best = max(scores, key=lambda k: (scores[k], -list(_KEYWORDS).index(k)))
    total = sum(scores.values())
    return best, matched[best], round(scores[best] / total, 2) if total else 0.0


def wants_out_of_scope(question: str) -> bool:
    q = (question or "").lower()
    return any(token in q for token in _OUT_OF_SCOPE)


# --------------------------------------------------------------------------
# Answer composition
# --------------------------------------------------------------------------


def _signed(x: float) -> str:
    return f"{x:+.2f}"


def _boundary_line(atm: Atmosphere) -> str:
    base = loc_percent(atm.p_kpa)
    eff = effective_loc(atm.p_kpa, atm.gravity, atm.flow_ms, atm.temperature_c)
    margin = atm.o2_pct - eff
    flag = epistemic_flag_for_pressure(atm.p_kpa)
    return (
        f"At {atm.pressure_psia:g} psia ({atm.p_kpa:.1f} kPa) the ground trend gives a base "
        f"LOC of {base:.2f}% O2; with the {atm.gravity} offset "
        f"({_signed(gravity_loc_offset_pct(atm.gravity))} pt), the flow penalty "
        f"({_signed(flow_penalty_pct(atm.gravity, atm.flow_ms))} pt at {atm.flow_ms:g} m/s) and the "
        f"ambient-temperature offset ({_signed(temperature_loc_offset_pct(atm.temperature_c))} pt at "
        f"{atm.temperature_c:g} °C), the effective boundary is {eff:.2f}% O2. "
        f"The {atm.o2_pct:g}% on the slider sits {_signed(margin)} pt "
        f"{'above' if margin >= 0 else 'below'} it, so sustained spread is "
        f"{'possible' if margin > 0 else 'not supported at this O2'}. "
        f"Curve calibration envelope: {P_ENVELOPE_KPA[0]:g}-{P_ENVELOPE_KPA[1]:g} kPa — "
        f"this state is {flag}."
    )


def _answer_loc(atm: Atmosphere, _exps: list[dict], _ranked: list[dict]) -> list[str]:
    lines = [_boundary_line(atm)]
    bars = ", ".join(
        f"{p:g} psia → {loc_percent(p * 6.89476):.2f}%" for p in (8.2, 10.0, 14.7)
    )
    lines.append(
        f"The published pressure trend (LOC falls as total pressure rises) is what the curve "
        f"encodes: {bars}. A lower cabin pressure raises the O2 concentration a material needs "
        f"before spread is sustained."
    )
    if epistemic_flag_for_pressure(atm.p_kpa) == "EXTRAPOLATED":
        lines.append(
            "This pressure is outside the envelope the curve was fitted in, so the value is "
            "flagged EXTRAPOLATED and the Trade Space map hatches that region instead of "
            "colouring it — no pixel implies a measurement NASA did not make (limitation L2)."
        )
    return lines


def _answer_hazard(atm: Atmosphere, _exps: list[dict], _ranked: list[dict]) -> list[str]:
    vec = hazard_vector(atm.pressure_psia, atm.o2_pct, atm.gravity, atm.flow_ms,
                        atm.temperature_c, atm.material_class)
    comps = [(k.replace("_", " "), vec[k]) for k in
             ("ignition", "spread", "persistence", "heat_release", "extinction_margin")]
    listed = "; ".join(f"{name} {value:.1f}" for name, value in comps)
    top = max(comps, key=lambda kv: kv[1])
    low = min(comps, key=lambda kv: kv[1])
    return [
        f"Fire Hazard Vector for this state: {listed} (all on 0-100, relative comparison only).",
        f"Highest component: {top[0]} at {top[1]:.1f}; lowest: {low[0]} at {low[1]:.1f}. "
        "Ignition is the distance of the O2 fraction above the effective LOC normalized over a "
        f"25-point margin span; spread = ignition × flow factor × thickness factor for the "
        f"'{atm.material_class}' class ({thickness_factor_for(atm.material_class):.2f}); persistence "
        "and heat release are derived from spread by construction, so they move together — they are "
        "not three independent measurements (limitation L4).",
        _boundary_line(atm),
    ]


def _answer_crew(atm: Atmosphere, _exps: list[dict], _ranked: list[dict]) -> list[str]:
    pO2 = po2_psia(atm.pressure_psia, atm.o2_pct)
    norm = po2_normoxia_pct(atm.pressure_psia, atm.o2_pct)
    lo, hi = PO2_CREW_SAFE_BAND_PSIA
    safe = crew_safe(atm.pressure_psia, atm.o2_pct)
    # The classic crew-equivalent pair: 10.0 psia / 30% and 7.5 psia / 40% both
    # give pO2 = 3.00 psia. Both members are evaluated at this state's gravity,
    # flow and temperature so the comparison is like-for-like.
    eff_here = effective_loc(atm.p_kpa, atm.gravity, atm.flow_ms, atm.temperature_c)
    eff_10_30 = effective_loc(10.0 * 6.89476, atm.gravity, atm.flow_ms, atm.temperature_c)
    eff_7_40 = effective_loc(7.5 * 6.89476, atm.gravity, atm.flow_ms, atm.temperature_c)
    return [
        f"Crew side: pO2 = {atm.pressure_psia:g} psia × {atm.o2_pct:g}% = {pO2:.2f} psia, which is "
        f"{norm:.1f}% of sea-level normoxia. The crew-safe band used by this project is "
        f"pO2 ∈ [{lo}, {hi}] psia (about 78-110% normoxia) — this state is "
        f"{'inside' if safe else 'outside'} that band"
        + ("" if safe else
           f" (hypoxia side margin {pO2 - lo:+.2f} psia, toxicity side margin {hi - pO2:+.2f} psia)") + ".",
        f"Fire side: this state sits {_signed(atm.o2_pct - eff_here)} pt against its LOC "
        f"boundary of {eff_here:.2f}%. pO2 and LOC answer different questions, and they can "
        "disagree — the classic pair is 10.0 psia / 30% O2 and 7.5 psia / 40% O2, which both "
        f"give pO2 = 3.00 psia, while their LOC margins are {_signed(30.0 - eff_10_30)} pt and "
        f"{_signed(40.0 - eff_7_40)} pt. Two crew-equivalent atmospheres are not "
        "fire-equivalent.",
        "The band is a stated model construct of this project, not a NASA requirement, and "
        "pressure-reduction lower limits and oxygen-toxicity exposure limits are not modelled "
        "(limitation L6).",
    ]


def _answer_evidence(atm: Atmosphere, exps: list[dict], ranked: list[dict]) -> list[str]:
    label = classify(atm.p_kpa, atm.o2_pct, atm.gravity, atm.material_class, exps)
    cov = coverage(atm.p_kpa, atm.o2_pct, atm.gravity, atm.material_class, exps) * 100.0
    evidence, context = partition(ranked)
    near = [e for e in exps
            if abs(float(e["pressure_kpa"]) - atm.p_kpa) <= 8.0
            and abs(float(e["o2_pct"]) - atm.o2_pct) <= 2.5
            and e.get("gravity") == atm.gravity
            and e.get("material_class") == atm.material_class]
    lines = [
        f"Evidence label: {label}, coverage {cov:.1f}%. The label is computed from the database at "
        "request time from four rules: OBSERVED (a record within ±8 kPa and ±2.5 O2 points in the "
        "same gravity regime and material class), INTERPOLATED (inside the record range but no "
        "direct match), EXTRAPOLATED (outside the record range on an axis), INSUFFICIENT (fewer "
        "than two compatible records).",
        f"Records within tolerance of this atmosphere: {len(near)}."
        + (" They are listed as the key supporting experiments below." if near else
           " The nearest records are listed below; none matches on every axis, which is why the "
           "label is not OBSERVED."),
    ]
    if evidence:
        e = evidence[0]
        lines.append(
            f"Nearest controlled combustion experiment: {e['experiment_id']} ({e['mission']}, "
            f"{e['o2_pct']:g}% O2 @ {e['pressure_kpa']:g} kPa, {e['gravity']}, verdict "
            f"{e['verdict']}), condition similarity {e['similarity'] * 100:.0f}%. Source: "
            f"{e['source_url']}"
        )
    if context:
        c = context[0]
        lines.append(
            f"Nearest record overall: {c['experiment_id']} ({c['mission']}) at "
            f"{c['similarity'] * 100:.0f}% similarity — but it is a "
            f"{KIND_LABELS[record_kind(c)]} and carries no combustion verdict, so it is reported "
            "as context and never counted as fire evidence (dossier §6.1)."
        )
    lines.append(
        f"Coverage is the best condition-similarity across the whole database, weighted "
        f"P 0.35 / O2 0.35 / gravity 0.20 / material class 0.10. The shipped database holds "
        f"{len(exps)} records, of which "
        f"{sum(1 for e in exps if record_kind(e) == KIND_EXPERIMENT)} are controlled combustion "
        "experiments (limitation L7)."
    )
    return lines


def _answer_comparison(atm: Atmosphere, _exps: list[dict], _ranked: list[dict],
                       question: str) -> list[str]:
    pcts = [float(m) for m in _NUM_PCT.findall(question)]
    if len(pcts) >= 2 and pcts[0] != pcts[1]:
        a_p, a_o2, b_p, b_o2 = atm.pressure_psia, pcts[0], atm.pressure_psia, pcts[1]
        head = (f"Comparing the two O2 values named in the question at "
                f"{atm.pressure_psia:g} psia, {atm.gravity}: "
                f"{a_o2:g}% vs {b_o2:g}%.")
    else:
        a_p, a_o2 = 8.2, 34.0
        b_p, b_o2 = atm.pressure_psia, atm.o2_pct
        head = ("No two O2 values were named, so this compares the Exploration Atmosphere "
                "(8.2 psia / 34% O2, NASA's Artemis targeting) with the state on the sliders.")
    a = hazard_vector(a_p, a_o2, atm.gravity, atm.flow_ms, atm.temperature_c,
                      atm.material_class)
    b = hazard_vector(b_p, b_o2, atm.gravity, atm.flow_ms, atm.temperature_c,
                      atm.material_class)
    d_loc = b["effective_loc_pct"] - a["effective_loc_pct"]
    return [
        head,
        f"Ignition {a_o2:g}% @ {a_p:g} psia → {a['ignition']:.1f} vs {b_o2:g}% @ {b_p:g} psia → "
        f"{b['ignition']:.1f} ({_signed(b['ignition'] - a['ignition'])}); spread "
        f"{a['spread']:.1f} vs {b['spread']:.1f} ({_signed(b['spread'] - a['spread'])}); "
        f"extinction margin {a['extinction_margin']:.1f} vs {b['extinction_margin']:.1f}. "
        f"Effective LOC differs by {_signed(d_loc)} pt.",
        f"Crew side: pO2 {po2_psia(a_p, a_o2):.2f} vs {po2_psia(b_p, b_o2):.2f} psia. "
        f"Where the two disagree, the "
        "flammability axis (molar O2 against LOC) is the one that moves fire behaviour, and the "
        "pO2 axis is the one that moves hypoxia risk — that divergence is the whole point of "
        "keeping them on separate axes rather than collapsing them into one risk number.",
    ]


def _answer_material(atm: Atmosphere, _exps: list[dict], _ranked: list[dict]) -> list[str]:
    rows = []
    for cls in MATERIAL_CLASSES:
        v = hazard_vector(atm.pressure_psia, atm.o2_pct, atm.gravity, atm.flow_ms,
                          atm.temperature_c, cls)
        rows.append((cls, thickness_factor_for(cls), v["spread"], v["persistence"]))
    rows.sort(key=lambda r: r[2])
    listed = "; ".join(
        f"{cls} (factor {factor:.2f}) spread {spread:.1f}, persistence {pers:.1f}"
        for cls, factor, spread, pers in rows
    )
    return [
        f"At this atmosphere, spread and persistence by material class: {listed}.",
        "The class enters as a representative thickness factor on spread, and through spread on "
        "persistence and heat release. Ignition is deliberately unaffected by material class: it "
        "is derived from the LOC margin alone (dossier §4.6).",
        "This is a per-class factor, not a chemistry model of a specific material, and it does not "
        "resolve geometry inside a class — the difference between a Saffire panel and a thin "
        "Saffire-II sample card is exactly what it cannot represent (limitation L1).",
    ]


def _answer_flow(atm: Atmosphere, _exps: list[dict], _ranked: list[dict]) -> list[str]:
    lo = max(0.0, atm.flow_ms - 0.15)
    hi = min(1.0, atm.flow_ms + 0.15)
    a = hazard_vector(atm.pressure_psia, atm.o2_pct, atm.gravity, lo, atm.temperature_c,
                      atm.material_class)
    b = hazard_vector(atm.pressure_psia, atm.o2_pct, atm.gravity, atm.flow_ms, atm.temperature_c,
                      atm.material_class)
    c = hazard_vector(atm.pressure_psia, atm.o2_pct, atm.gravity, hi, atm.temperature_c,
                      atm.material_class)
    lines = [
        f"Forced flow {lo:g} → {atm.flow_ms:g} → {hi:g} m/s gives spread "
        f"{a['spread']:.1f} → {b['spread']:.1f} → {c['spread']:.1f} and ignition "
        f"{a['ignition']:.1f} → {b['ignition']:.1f} → {c['ignition']:.1f} "
        f"(ignition moves through the boundary, not through a multiplier on the index)."
    ]
    if atm.gravity == "microgravity":
        lines.append(
            f"In microgravity the flow term is active: the LOC penalty is "
            f"{flow_penalty_pct(atm.gravity, atm.flow_ms):+.2f} pt at this velocity and reaches "
            f"{flow_penalty_pct(atm.gravity, 0.0):+.2f} pt at zero flow, because buoyancy supplies "
            "no oxygen transport — a low flow raises the effective boundary and can push a "
            "near-limit atmosphere to self-extinguish (BASS-II-04: 17% O2 at 0.1 m/s, observed "
            "self-extinguish)."
        )
    else:
        lines.append(
            f"In {atm.gravity} the flow term is identically zero by construction — buoyancy-driven "
            "convection supplies the transport, so changing forced flow leaves the effective "
            "boundary unchanged here. The direction of effect is cited; the magnitude is a bounded "
            "fit choice (limitation L5)."
        )
    return lines


def _answer_temperature(atm: Atmosphere, _exps: list[dict], _ranked: list[dict]) -> list[str]:
    offset = temperature_loc_offset_pct(atm.temperature_c)
    eff = effective_loc(atm.p_kpa, atm.gravity, atm.flow_ms, atm.temperature_c)
    ref = effective_loc(atm.p_kpa, atm.gravity, atm.flow_ms, TEMP_REFERENCE_C)
    hot = hazard_vector(atm.pressure_psia, atm.o2_pct, atm.gravity, atm.flow_ms,
                        min(60.0, atm.temperature_c + 8.0), atm.material_class)
    cold = hazard_vector(atm.pressure_psia, atm.o2_pct, atm.gravity, atm.flow_ms,
                         max(-20.0, atm.temperature_c - 8.0), atm.material_class)
    return [
        f"At {atm.temperature_c:g} °C the ambient-temperature offset on the boundary is "
        f"{_signed(offset)} pt relative to the {TEMP_REFERENCE_C:g} °C reference used by every "
        f"figure in the dossier: effective LOC {ref:.2f}% → {eff:.2f}% O2.",
        f"Because the boundary moves rather than the index being multiplied, the components stay "
        f"inside 0-100 across the slider: ±8 °C around the current value gives ignition "
        f"{cold['ignition']:.1f} (cold) → {hot['ignition']:.1f} (warm) and spread "
        f"{cold['spread']:.1f} → {hot['spread']:.1f}.",
        "Warmer cabin air raises a material's surface temperature and therefore lowers the O2 at "
        "which spread is sustained — that direction is physical. The magnitude (0.1 pt per K, "
        "hard-capped at ±2 pt) is a bounded fit choice, stated in code rather than hidden "
        "(limitation L5).",
    ]


def _answer_pressure(atm: Atmosphere, _exps: list[dict], _ranked: list[dict]) -> list[str]:
    eff = effective_loc(atm.p_kpa, atm.gravity, atm.flow_ms, atm.temperature_c)
    target = atm.o2_pct - (gravity_loc_offset_pct(atm.gravity)
                           + flow_penalty_pct(atm.gravity, atm.flow_ms)
                           + temperature_loc_offset_pct(atm.temperature_c))
    lines = [
        _boundary_line(atm),
        "The curve is monotonic: lowering total pressure raises the O2 fraction a material needs "
        f"before spread is sustained. At the current O2 of {atm.o2_pct:g}%, the boundary "
        f"({eff:.2f}%) is {'below' if eff < atm.o2_pct else 'above'} the slider value.",
    ]
    if target > 15.88:
        p_psia = 200.5 / (target - 15.88) / 6.89476
        flag = epistemic_flag_for_pressure(p_psia * 6.89476)
        lines.append(
            f"Solving the ground trend for this O2 gives the pressure at which the atmosphere "
            f"sits exactly on the boundary: {p_psia:.2f} psia ({p_psia * 6.89476:.1f} kPa). Below "
            f"that pressure the state is on the non-flammable side. That pressure is {flag} "
            "relative to the curve's calibration envelope, so treat it as a model output, not a "
            "measured threshold."
        )
    else:
        lines.append(
            f"At {atm.o2_pct:g}% O2 the effective boundary can no longer be reached by reducing "
            "pressure alone within the modelled trend — the boundary asymptotes to 15.88% O2, so "
            "below that concentration the state is non-flammable at any pressure this model covers."
        )
    return lines


def _answer_validation(_atm: Atmosphere, exps: list[dict], _ranked: list[dict]) -> list[str]:
    v = leave_one_out(exps)
    misses = [r for r in v["results"] if not r["correct"]]
    lines = [
        f"Leave-one-out backtest: {v['correct']} of {v['total']} records classified correctly "
        f"({v['accuracy'] * 100:.1f}%), and {v['accuracy_non_anchor'] * 100:.1f}% on the "
        f"{v['total'] - len([r for r in v['results'] if r['is_fit_anchor']])} records that are not "
        "fit anchors of the LOC curve. Each record is classified from the boundary built without "
        "it; the fits themselves are then re-derived from the shipped anchors.",
        f"The {len(misses)} misses are published with explanations, not hidden: "
        + " ".join(f"{r['experiment_id']} (margin {r['margin_pct']:+.2f} pt)"
                   for r in misses) + ".",
        "Read this as calibration evidence on a 20-record seed database, not as a validation of "
        "operational safety — the anchors are part of the fit, and the whole suite is small "
        "(limitations L5, L7).",
    ]
    return lines


def _answer_what_if(atm: Atmosphere, _exps: list[dict], _ranked: list[dict],
                    question: str) -> list[str]:
    pcts = [float(m) for m in _NUM_PCT.findall(question)]
    flows = [float(m) for m in _NUM_MS.findall(question)]
    d_o2 = 0.0
    d_flow = 0.0
    if pcts:
        d_o2 = pcts[0] if "increase" in question.lower() or "raise" in question.lower() else -pcts[0]
    if flows:
        d_flow = flows[0] - atm.flow_ms
    if d_o2 == 0.0 and d_flow == 0.0:
        d_o2 = 2.0
    before = hazard_vector(atm.pressure_psia, atm.o2_pct, atm.gravity, atm.flow_ms,
                           atm.temperature_c, atm.material_class)
    after = hazard_vector(atm.pressure_psia, atm.o2_pct + d_o2, atm.gravity,
                          max(0.0, min(1.0, atm.flow_ms + d_flow)), atm.temperature_c,
                          atm.material_class)
    worse = (after["ignition"] + after["spread"]) > (before["ignition"] + before["spread"])
    return [
        f"Rerunning the engine with ΔO2 {d_o2:+.1f} pt and Δflow {d_flow:+.2f} m/s "
        f"(no interpolation, the model is re-evaluated): ignition {before['ignition']:.1f} → "
        f"{after['ignition']:.1f}, spread {before['spread']:.1f} → {after['spread']:.1f}, "
        f"persistence {before['persistence']:.1f} → {after['persistence']:.1f}, extinction margin "
        f"{before['extinction_margin']:.1f} → {after['extinction_margin']:.1f}.",
        f"Net effect on this atmosphere: {'WORSE' if worse else 'BETTER OR EQUAL'} on the "
        f"ignition+spread sum. The effective boundary moves "
        f"{_signed(after['effective_loc_pct'] - before['effective_loc_pct'])} pt, and the margin "
        f"above it goes {_signed(before['margin_above_loc_pct'])} → "
        f"{_signed(after['margin_above_loc_pct'])} pt.",
        "Deltas are differences of two full model evaluations, so they inherit every stated "
        "limitation — they rank atmospheres relative to each other, they are not absolute risk.",
    ]


def _answer_general(atm: Atmosphere, _exps: list[dict], ranked: list[dict]) -> list[str]:
    label = classify(atm.p_kpa, atm.o2_pct, atm.gravity, atm.material_class, _exps)
    cov = coverage(atm.p_kpa, atm.o2_pct, atm.gravity, atm.material_class, _exps) * 100.0
    vec = hazard_vector(atm.pressure_psia, atm.o2_pct, atm.gravity, atm.flow_ms,
                        atm.temperature_c, atm.material_class)
    evidence, _context = partition(ranked)
    return [
        _boundary_line(atm),
        f"Evidence classification: {label}; coverage {cov:.1f}% over {len(_exps)} records.",
        f"Fire Hazard Vector: ignition {vec['ignition']}, spread {vec['spread']}, persistence "
        f"{vec['persistence']}, heat release {vec['heat_release']}, extinction margin "
        f"{vec['extinction_margin']}. Crew: pO2 {vec['crew']['po2_psia']} psia "
        f"({vec['crew']['normoxia_pct']}% of sea-level normoxia).",
        "Key supporting experiments: "
        + "; ".join(f"{e['experiment_id']} ({e['mission']}, {e['o2_pct']:g}% O2 @ "
                    f"{e['pressure_kpa']:g} kPa, {e['verdict']})" for e in evidence[:5]),
    ]


def _answer_out_of_scope(atm: Atmosphere, _exps: list[dict], _ranked: list[dict]) -> list[str]:
    return [
        "That question is outside what this engine models, so rather than compose something "
        "plausible this answer states the boundary of the tool.",
        "FLARE answers questions about the interaction of pressure, O2 concentration, gravity "
        "regime, ventilation flow, ambient temperature and material class with (a) the limiting "
        "oxygen concentration boundary for sustained flame spread, (b) a five-component relative "
        "fire hazard vector, (c) crew oxygen partial pressure, (d) the NASA experimental record "
        "behind each of those, and (e) how accurately the model reproduces held-out experiments.",
        f"It does not model smoldering, flame chemistry, spacecraft systems, mission cost, "
        f"timelines or crew scheduling (limitations L1-L7). For the state on the sliders "
        f"({atm.pressure_psia:g} psia / {atm.o2_pct:g}% O2) the boundary question is answerable — "
        "ask about the LOC boundary, the hazard components, crew pO2, airflow or the evidence "
        "behind the numbers.",
    ]


_COMPOSERS = {
    "loc_boundary": _answer_loc,
    "hazard_components": _answer_hazard,
    "crew_physiology": _answer_crew,
    "evidence_coverage": _answer_evidence,
    "comparison": _answer_comparison,
    "material_effect": _answer_material,
    "flow_effect": _answer_flow,
    "temperature_effect": _answer_temperature,
    "pressure_effect": _answer_pressure,
    "validation": _answer_validation,
    "what_if": _answer_what_if,
    "general": _answer_general,
    "out_of_scope": _answer_out_of_scope,
}

# Intents that take the raw question as a third argument (they parse values out
# of it) as opposed to composing purely from the engine state.
_QUESTION_AWARE: Final[frozenset[str]] = frozenset({"comparison", "what_if"})

SUGGESTED_QUESTIONS: Final[dict[str, list[str]]] = {
    "loc_boundary": [
        "What pressure would put this atmosphere exactly on the boundary?",
        "How does gravity change the boundary?",
    ],
    "hazard_components": [
        "Which hazard component is highest, and why?",
        "How confident is the evidence behind this?",
    ],
    "crew_physiology": [
        "Is this atmosphere safe for the crew?",
        "Why is 34% O2 riskier than 30% at the same pO2?",
    ],
    "evidence_coverage": [
        "Which experiments support this atmosphere?",
        "How accurate is the model on held-out experiments?",
    ],
    "comparison": [
        "Compare 8.2 psia / 34% with 7.5 psia / 40%.",
        "What if O2 increases by 2%?",
    ],
    "material_effect": [
        "How does the material class change spread?",
        "Does thickness matter in microgravity?",
    ],
    "flow_effect": [
        "What if airflow drops to 0.05 m/s?",
        "Why does low flow matter only in microgravity?",
    ],
    "temperature_effect": [
        "What does a warmer cabin do to the boundary?",
        "How large is the temperature effect compared with the flow effect?",
    ],
    "pressure_effect": [
        "Why does lower pressure raise the LOC?",
        "What pressure makes this atmosphere non-flammable?",
    ],
    "validation": [
        "Which experiments does the model get wrong?",
        "How many records are in the database?",
    ],
    "what_if": [
        "What if O2 increases by 2%?",
        "What if airflow drops to 0.05 m/s?",
    ],
    "general": [
        "Why is 34% O2 riskier than 28% at the same pressure?",
        "Which experiments support this atmosphere?",
        "What if airflow drops to 0.05 m/s?",
    ],
    "out_of_scope": [
        "What does FLARE model?",
        "Which experiments support this atmosphere?",
    ],
}


def compose(question: str, atmosphere: Atmosphere, experiments: list[dict]) -> dict:
    """Route a question and compose the engine-grounded answer payload."""
    ranked = rank_experiments(atmosphere.p_kpa, atmosphere.o2_pct, atmosphere.gravity,
                              atmosphere.material_class, experiments)
    evidence, context = partition(ranked)

    if wants_out_of_scope(question):
        intent, matched, share = "out_of_scope", [], 1.0
    else:
        intent, matched, share = route(question)

    composer = _COMPOSERS[intent]
    if intent in _QUESTION_AWARE:
        lines = composer(atmosphere, experiments, ranked, question)  # type: ignore[call-arg]
    else:
        lines = composer(atmosphere, experiments, ranked)

    # Only controlled combustion experiments are cited as fire evidence; the
    # rest are returned separately with their kind, so the client can show them
    # as context without ever labelling them "supporting experiments".
    sample = evidence[:5] if intent != "general" else evidence[:5]
    cited = [e["experiment_id"] for e in sample]
    context_ids = [e["experiment_id"] for e in context[:3]]

    return {
        "intent": intent,
        "intent_matched": matched,
        "intent_confidence": share,
        "answer": "\n\n".join(lines),
        "citations": cited,
        "context_citations": context_ids,
        "context_kinds": {c["experiment_id"]: record_kind(c) for c in context[:3]},
        "suggested_questions": SUGGESTED_QUESTIONS.get(intent, SUGGESTED_QUESTIONS["general"]),
        "engine_summary": hazard_vector(
            atmosphere.pressure_psia, atmosphere.o2_pct, atmosphere.gravity,
            atmosphere.flow_ms, atmosphere.temperature_c, atmosphere.material_class,
        ),
    }
