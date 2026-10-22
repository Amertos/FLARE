"""Flame-regime and fire-front quantities for the 3D Freefall Lab screen.

Everything the 3D screen draws is derived here, from the same boundary and
hazard functions the rest of the product uses, so the animation cannot show a
behaviour the published model does not produce. The module also returns the
sources for every qualitative statement the visualisation makes, because the
project's rule is that no claim ships without one (dossier §4.2).

What the visualisation is allowed to claim, and where it comes from:

* **No buoyancy in microgravity → no upward teardrop.** NASA's own visualisation
  contrasts a circular near-zero-gravity flame with a teardrop-shaped Earth
  flame (NASA SVS 11640). Reported as a *regime*, not a prediction: the real
  shape also depends on fuel geometry and imposed ventilation, which this model
  does not resolve (limitation L8).
* **Rounder, bluer, longer as opposed flow falls in microgravity.** BASS-II
  (PMMA, ISS): the microgravity flame was rounder and bluer — lower soot — than
  the 1g comparison, and lowering the opposed flow made it bluer, longer and
  more spherical, extinguishing it at very low flow (Link et al. 2018).
* **No universal "space burns slower".** In the same tests, spread was faster at
  1g at 21% O2 but faster in microgravity below ~19% O2, and microgravity
  sustained spread at ~17% O2 where the 1g comparison could not sustain it at
  ~18% or below. The engine's gravity offset (−0.8 pt) encodes exactly that
  shift, and `crossover()` reports the engine's own crossing point next to the
  published one.
* **Cool flames** were discovered in non-premixed microgravity droplet studies
  (FLEX, 2012): faint and low-temperature. The ~700 K reaction zone quoted in
  the NTRS record is a *model* result, not a measurement — said so explicitly
  wherever it appears.

Front speed is reported in RELATIVE units against the Saffire-I reference
condition in the curated database (its own record, not a hard-coded number):
the model ranks atmospheres, it does not predict an absolute spread rate
(limitation L4).
"""
from __future__ import annotations

from typing import Final

from .hazard import hazard_vector
from .loc import effective_loc

SHAPE_TEARDROP: Final[str] = "teardrop"
SHAPE_SPHERICAL: Final[str] = "spherical"

STYLE_STABLE: Final[str] = "stable"
STYLE_TRANSITIONAL: Final[str] = "transitional"
STYLE_FLICKERING: Final[str] = "flickering"

FATE_SUSTAINED: Final[str] = "sustained"
FATE_MARGINAL: Final[str] = "marginal"
FATE_SELF_EXTINGUISHING: Final[str] = "self_extinguishing"

# Spread index below which a flame is reported as marginal even above the
# boundary: the model's spread component scales ignition by the flow and
# thickness factors, so a small value means the flame front advances only while
# its ignition source is present. Stated as a presentation threshold, not a
# measurement (dossier §4.7 L5/L8).
MARGINAL_SPREAD_THRESHOLD: Final[float] = 20.0

# Reference condition for relative front speed: the Saffire-I record in
# backend/data/experiments.json (largest microgravity flame experiment in the
# curated set). Declared here so the engine stays pure; a test asserts the
# database still holds the matching record.
REFERENCE_EXPERIMENT_ID: Final[str] = "SAFFIRE-I-01"
REFERENCE_PRESSURE_PSIA: Final[float] = 14.7
REFERENCE_O2_PCT: Final[float] = 21.0
REFERENCE_GRAVITY: Final[str] = "microgravity"
REFERENCE_FLOW_MS: Final[float] = 0.2
REFERENCE_TEMPERATURE_C: Final[float] = 22.0
REFERENCE_MATERIAL_CLASS: Final[str] = "polymer"

# Gravity regimes compared on the crossover chart.
CROSSOVER_GRAVITIES: Final[tuple[str, str]] = ("microgravity", "earth")

CITATIONS: Final[list[dict[str, str]]] = [
    {
        "id": "FL1",
        "claim": (
            "Buoyancy-driven flow is absent in microgravity, so a flame has no "
            "upward teardrop shape; NASA contrasts a circular near-zero-gravity "
            "flame with a teardrop-shaped Earth flame."
        ),
        "source": "NASA Scientific Visualization Studio — \"Spherical Flames\" (SVS 11640)",
        "url": "https://svs.gsfc.nasa.gov/11640/",
        "kind": "NASA visualization/explainer (not peer-reviewed)",
    },
    {
        "id": "FL2",
        "claim": (
            "BASS-II (PMMA, ISS): the microgravity flame was rounder and bluer — "
            "lower soot — than at 1g, and lowering the opposed flow made it "
            "bluer, longer and more spherical until it extinguished."
        ),
        "source": "Link et al. 2018, \"The Effect of Gravity on Flame Spread over PMMA Cylinders\", Scientific Reports (PMC5760683)",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5760683/",
        "kind": "peer-reviewed",
    },
    {
        "id": "FL3",
        "claim": (
            "There is no universal \"microgravity burns slower\": in the BASS-II "
            "comparison spread was faster at 1g at 21% O2 but faster in "
            "microgravity below ~19% O2, and microgravity sustained spread at "
            "~17% O2 where the 1g comparison did not."
        ),
        "source": "Link et al. 2018 (PMC5760683)",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5760683/",
        "kind": "peer-reviewed",
    },
    {
        "id": "FL4",
        "claim": (
            "Non-premixed cool flames were first observed in microgravity "
            "droplet studies (FLEX, 2012): faint, low-temperature, persisting "
            "after the visible hot flame goes out."
        ),
        "source": "NASA — \"Cool Flames Created During a First for International Space Station Research\"",
        "url": "https://www.nasa.gov/missions/station/cool-flames-created-during-a-first-for-international-space-station-research/",
        "kind": "NASA article (not peer-reviewed)",
    },
    {
        "id": "FL5",
        "claim": (
            "A ~700 K reaction zone in the non-premixed cool-flame regime "
            "(n-heptane, microgravity) is a MODEL result from a numerical "
            "simulation, not a measured temperature."
        ),
        "source": "NASA NTRS — \"Combustion Characteristics in a Non-Premixed Cool-Flame Regime of n-Heptane in Microgravity\" (20150018397)",
        "url": "https://ntrs.nasa.gov/citations/20150018397",
        "kind": "conference paper, numerical simulation",
    },
]

NOTES: Final[list[str]] = [
    "Regime, not prediction: flame shape also depends on fuel geometry and imposed "
    "ventilation, which this model does not resolve (limitation L8).",
    "Front speed is relative to the Saffire-I reference condition — the model ranks "
    "atmospheres against each other and does not predict an absolute spread rate "
    "(limitation L4).",
    "This is a schematic rendering driven by engine outputs, not a CFD solution "
    "(limitation L8).",
    "Cool-flame and flow-band renderings are qualitative indications placed next to "
    "the published observations (FL4/FL5, FL2) — the model has no cool-flame "
    "chemistry and no CFD, so these layers never change a number.",
]


# Flow-regime presentation bands for the chamber view. They follow the BASS-II
# finding (Link et al. 2018, FL2) that in microgravity a lower opposed flow
# makes the flame bluer, longer and more spherical until it extinguishes; they
# are presentation bands around that finding, NOT new thresholds.
FLOW_BAND_LOW_MS: Final[float] = 0.25
FLOW_BAND_FULL_MS: Final[float] = 0.4


def cool_flame_phase(gravity: str, margin_pct: float, fate_code: str) -> dict:
    """Qualitative cool-flame phase flag for the chamber view (FL4/FL5).

    FLEX (2012) discovered non-premixed cool flames in microgravity droplet
    studies: faint, low-temperature combustion that persists after the visible
    hot flame goes out. This model has no cool-flame chemistry, so the flag is
    a SCHEMATIC indication of where such a phase could occur relative to the
    published observations — it gates a faint ghost render in the chamber and a
    dossier note on the screen. It excludes every state at or below the LOC
    boundary EXCEPT microgravity states where the hot flame is predicted to
    die: those are exactly the regimes where published µg work reports hot-flame
    extinction followed by cool-flame persistence (FL4).
    """
    possible = (gravity == "microgravity" and margin_pct <= 0) or fate_code == "marginal"
    return {
        "possible": bool(possible),
        "label": (
            "cool-flame phase possible (qualitative)" if possible else "not indicated"
        ),
        "note": (
            "Below/at the effective LOC the hot flame is predicted to die. Published "
            "microgravity work found faint, low-temperature cool flames that can "
            "persist after hot-flame extinction (FLEX 2012); the ~700 K reaction zone "
            "reported for the non-premixed cool-flame regime is a numerical-simulation "
            "result, NOT a measurement. This model has no cool-flame chemistry, so this "
            "phase is rendered as a qualitative indication only (FL4/FL5)."
        ) if possible else (
            "No cool-flame phase indicated for this state: the model reports the flame "
            "staying in its hot regime (or the state is not a microgravity one)."
        ),
        "citations": ["FL4", "FL5"] if possible else [],
    }


def flow_regime(gravity: str, flow_ms: float) -> dict:
    """How the imposed airflow is rendered in the chamber (qualitative, FL2).

    BANDS PRESENTATION ONLY: they partition the flow axis into the regimes the
    BASS-II paper describes qualitatively (low opposed flow → bluer, longer,
    more spherical flame; near-zero flow → extinction of the spread); the
    engine's own flow penalty is the quantitative 1.5 pt/0.25 m/s term in
    effective LOC, unchanged.
    """
    if gravity != "microgravity":
        return {
            "band": "buoyancy-dominated",
            "note": (
                "At this gravity buoyant convection supplies the oxidiser transport, "
                "and the imposed flow is a second-order effect in this model. The "
                "µg-vs-1g distinction is the BASS-II comparison, not a low-flow claim "
                "here (FL2)."
            ),
            "streamer_speed_scale": 0.0,
        }
    if flow_ms < 0.2:
        return {
            "band": "near-zero opposed flow",
            "note": (
                "At very low opposed flow in microgravity the published BASS-II flame "
                "was bluer, longer and more spherical, and extinguished below the "
                "lowest tested flows (FL2). The flame is drawn straining against the "
                "flow at this band, and the chamber is near-mixing-free."
            ),
            "streamer_speed_scale": 0.0,
        }
    if flow_ms < FLOW_BAND_LOW_MS:
        return {
            "band": "low-flow",
            "note": (
                "Reduced opposed flow in microgravity: the flame leans downstream "
                "visibly and the effective LOC rises slightly (the 1.5 pt/0.25 m/s "
                "engine term) (FL2)."
            ),
            "streamer_speed_scale": round(min(flow_ms, FLOW_BAND_LOW_MS) / FLOW_BAND_LOW_MS, 2),
        }
    if flow_ms < FLOW_BAND_FULL_MS:
        return {
            "band": "moderate-flow",
            "note": (
                "Moderate opposed flow: close to the reference airflow of the "
                "curated experiments, where the flame shape is the regime chart's "
                "nominal one."
            ),
            "streamer_speed_scale": round(min(flow_ms, 0.5) / 0.5, 2),
        }
    return {
        "band": "full-flow",
        "note": (
            "High opposed flow relative to the curated conditions; the model also "
            "drops the µg flow penalty entirely at ≥ 0.25 m/s."
        ),
        "streamer_speed_scale": 1.0,
    }


def flame_regime(gravity: str, flow_ms: float, spread: float) -> dict:
    """Shape/colour regime for a flame in this state.

    Buoyant convection is present in every regime except microgravity; the
    colour tendency follows the BASS-II finding that the microgravity flame is
    bluer (lower soot) than the 1g comparison and bluer still as opposed flow
    falls.
    """
    buoyant = gravity != "microgravity"
    shape = SHAPE_TEARDROP if buoyant else SHAPE_SPHERICAL
    if buoyant:
        colour = "yellow-orange (soot-radiating)"
        style = STYLE_STABLE if spread >= MARGINAL_SPREAD_THRESHOLD else STYLE_FLICKERING
    else:
        colour = "blue-dominant (low soot)"
        style = STYLE_STABLE if spread >= MARGINAL_SPREAD_THRESHOLD else STYLE_TRANSITIONAL
    return {
        "shape": shape,
        "buoyant_convection": buoyant,
        "colour_tendency": colour,
        "style": style,
        "label": (
            "teardrop — buoyancy dominates"
            if buoyant
            else "spherical — no buoyancy, no upward teardrop"
        ),
        "note": (
            "In microgravity the flame has no buoyant plume to stretch it upward, so the "
            "rendered shape is round; at low opposed flow the published behaviour is a "
            "longer, bluer, more spherical flame (BASS-II)."
            if not buoyant
            else "Buoyancy drives the plume upward and the flame takes the familiar "
                 "teardrop shape; a weak imposed flow barely competes with it (BASS-II)."
        ),
        "citations": ["FL1", "FL2"],
    }


def fate_of(margin_pct: float, spread: float) -> dict:
    """Whether the flame spreads, limps or dies — from boundary margin + spread."""
    if margin_pct <= 0:
        return {
            "code": FATE_SELF_EXTINGUISHING,
            "label": "self-extinguishing",
            "detail": (
                f"Below the effective LOC boundary by {abs(round(margin_pct, 2))} pt, so "
                "sustained spread is not supported at this O2 — the front stalls and dies."
            ),
        }
    if spread < MARGINAL_SPREAD_THRESHOLD:
        return {
            "code": FATE_MARGINAL,
            "label": "ignites, cannot self-sustain",
            "detail": (
                f"Above the boundary by {round(margin_pct, 2)} pt, but the spread index "
                f"({round(spread, 1)}) is below {MARGINAL_SPREAD_THRESHOLD:g}: the model "
                "predicts ignition without a self-sustaining front in this flow."
            ),
        }
    return {
        "code": FATE_SUSTAINED,
        "label": "sustained spread",
        "detail": (
            f"Above the effective LOC boundary by {round(margin_pct, 2)} pt with a spread "
            f"index of {round(spread, 1)}: the front advances across the sample."
        ),
    }


def reference_vector() -> dict:
    """Hazard vector of the Saffire-I reference condition (computed, not stored)."""
    return hazard_vector(
        REFERENCE_PRESSURE_PSIA,
        REFERENCE_O2_PCT,
        REFERENCE_GRAVITY,
        REFERENCE_FLOW_MS,
        REFERENCE_TEMPERATURE_C,
        REFERENCE_MATERIAL_CLASS,
    )


def reference_spread() -> float:
    """Spread index of the Saffire-I reference condition."""
    return float(reference_vector()["spread"])


def front_speed_relative(spread: float) -> float:
    """Front speed as a percentage of the Saffire-I reference condition."""
    ref = reference_spread()
    if ref <= 0:
        return 0.0
    return round(100.0 * spread / ref, 1)


def loc_margin_pct(pressure_psia: float, o2_pct: float, gravity: str,
                   flow_ms: float, temperature_c: float) -> float:
    """Margin of this O2 above the effective LOC boundary, in points."""
    return o2_pct - effective_loc(pressure_psia * 6.89476, gravity, flow_ms, temperature_c)


def crossover_series(pressure_psia: float, flow_ms: float, temperature_c: float,
                     o2_min: float = 14.0, o2_max: float = 40.0,
                     steps: int = 27) -> dict:
    """Margin-vs-O2 series for microgravity and 1g at one pressure.

    The two curves cross where the gravity offset (0.8 pt) is no longer enough
    to matter: above that O2 the 1g margin is larger, below it the microgravity
    margin is — which is the engine's expression of the published BASS-II
    result (spread faster at 1g at 21% O2, faster in microgravity below ~19%).
    """
    step = (o2_max - o2_min) / (steps - 1)
    o2s = [round(o2_min + i * step, 2) for i in range(steps)]
    series: dict[str, list[dict[str, float]]] = {}
    locs: dict[str, float] = {}
    for gravity in CROSSOVER_GRAVITIES:
        loc = effective_loc(pressure_psia * 6.89476, gravity, flow_ms, temperature_c)
        locs[gravity] = round(loc, 2)
        series[gravity] = [
            {"o2_pct": o2, "margin_pct": round(o2 - loc, 2)} for o2 in o2s
        ]
    ug, one_g = CROSSOVER_GRAVITIES
    loc_ug, loc_1g = locs[ug], locs[one_g]
    return {
        "pressure_psia": pressure_psia,
        "o2_pct": o2s,
        "series": series,
        "loc_pct": locs,
        "offset_pt": round(loc_1g - loc_ug, 2),
        "microgravity_sustains_below_1g_at_pct": loc_ug,
        "published_finding": (
            "BASS-II (PMMA, ISS): spread was faster at 1g at 21% O2 but faster in "
            "microgravity below ~19% O2, and microgravity sustained spread at ~17% O2 "
            "where the 1g comparison could not sustain it at 18% or below."
        ),
        "citation": "FL3",
    }


def flame_payload(pressure_psia: float, o2_pct: float, gravity: str, flow_ms: float,
                  temperature_c: float, material_class: str) -> dict:
    """Everything the Freefall Lab screen renders for one atmosphere."""
    vec = hazard_vector(pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
                        material_class)
    spread = float(vec["spread"])
    margin = float(vec["margin_above_loc_pct"])
    regime = flame_regime(gravity, flow_ms, spread)
    fate = fate_of(margin, spread)
    flow = flow_regime(gravity, flow_ms)
    cool = cool_flame_phase(gravity, margin, fate["code"])
    ref = reference_vector()
    ref_spread = float(ref["spread"])
    return {
        "hazard": vec,
        "regime": regime,
        "fate": fate,
        "flow_regime": flow,
        "cool_flame_phase": cool,
        "front_speed_relative": front_speed_relative(spread),
        "reference": {
            "experiment_id": REFERENCE_EXPERIMENT_ID,
            "condition": (
                f"{REFERENCE_PRESSURE_PSIA:g} psia / {REFERENCE_O2_PCT:g}% O2 / "
                f"{REFERENCE_GRAVITY} / {REFERENCE_FLOW_MS:g} m/s / "
                f"{REFERENCE_MATERIAL_CLASS}"
            ),
            "spread_index": round(ref_spread, 1),
            # The anchor is a LOW-rate condition: Saffire-I at 21% O2 sits only
            # ~3 pt above its own LOC boundary in this model. Printing that here
            # keeps "400% of Saffire-I" from reading as "four times the fire"
            # without the context that makes it meaningful.
            "margin_above_loc_pct": ref["margin_above_loc_pct"],
            "note": (
                "Front rate is a percentage of this anchor's spread index — relative "
                "units, never m/s. The anchor itself sits only "
                f"{ref['margin_above_loc_pct']:+.1f} pt above its own LOC boundary, so "
                "100% is a low-rate anchor and higher percentages mean the model places "
                "this atmosphere further up the same spread ordering."
            ),
        },
        "crossover": crossover_series(pressure_psia, flow_ms, temperature_c),
        "citations": CITATIONS,
        "notes": NOTES,
    }
