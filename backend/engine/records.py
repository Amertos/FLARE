"""Record taxonomy — which database rows are combustion evidence, and which are context.

Why this module exists (dossier §6.1):

    Ranking by condition-distance is correct for answering "what is nearest?",
    but it is the wrong question when the UI labels a result list "key
    supporting experiments". The record nearest a fire query on the Exploration
    Atmosphere is ``EXPATM-EVA-REF-01`` — an atmosphere *specification* that
    carries no combustion verdict at all. Presenting it as fire evidence would
    be a silent overclaim of exactly the kind this project exists to avoid.

So every record is classified from its own fields into one of three kinds, and
only ``experiment`` records may be cited as fire evidence:

  experiment     a controlled combustion test with an outcome verdict (Saffire,
                 BASS-II, SoFIE-MIST, LOC threshold studies, ...)
  historical     a real fire event that was not a controlled experiment
                 (Apollo 1 cabin reference)
  specification  an atmosphere / crew reference with no combustion outcome
                 (Exploration Atmosphere reference)

Classification is derived, never hand-listed per record, and a unit test asserts
that every shipped record maps to one of the three kinds — so adding a record
with a new ``outcome_type`` cannot silently land in the evidence pool.
"""
from __future__ import annotations

from typing import Final

KIND_EXPERIMENT: Final[str] = "experiment"
KIND_HISTORICAL: Final[str] = "historical"
KIND_SPECIFICATION: Final[str] = "specification"
KIND_UNSPECIFIED: Final[str] = "unspecified"

CONTROLLED_OUTCOME_TYPES: Final[frozenset[str]] = frozenset({
    "flame_spread",
    "flammability_limit",
    "heat_release",
    "suppression",
    "ignition_delay",
    "combustion_physics",
})
HISTORICAL_OUTCOME_TYPES: Final[frozenset[str]] = frozenset({"historical_reference"})
SPECIFICATION_OUTCOME_TYPES: Final[frozenset[str]] = frozenset({"crew_reference"})

KIND_LABELS: Final[dict[str, str]] = {
    KIND_EXPERIMENT: "controlled experiment",
    KIND_HISTORICAL: "historical fire event (not a controlled experiment)",
    KIND_SPECIFICATION: "atmosphere specification (no combustion verdict)",
    KIND_UNSPECIFIED: "unclassified",
}


def record_kind(experiment: dict) -> str:
    """Classify one record from its own fields. No I/O, no hand-maintained list."""
    outcome = str(experiment.get("outcome_type", "")).strip()
    if outcome in CONTROLLED_OUTCOME_TYPES:
        return KIND_EXPERIMENT
    if outcome in HISTORICAL_OUTCOME_TYPES:
        return KIND_HISTORICAL
    if outcome in SPECIFICATION_OUTCOME_TYPES:
        return KIND_SPECIFICATION
    if str(experiment.get("verdict", "")).strip() == "n/a":
        return KIND_SPECIFICATION
    return KIND_UNSPECIFIED


def annotate(experiments: list[dict]) -> list[dict]:
    """Return the records with ``record_kind`` and ``record_kind_label`` added."""
    return [
        {**e, "record_kind": record_kind(e), "record_kind_label": KIND_LABELS[record_kind(e)]}
        for e in experiments
    ]


def partition(ranked: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split an already-ranked list into (combustion evidence, context).

    Order is preserved on both sides: the caller keeps nearest-conditions-first
    ranking inside each pool.
    """
    evidence = [e for e in ranked if record_kind(e) == KIND_EXPERIMENT]
    context = [e for e in ranked if record_kind(e) != KIND_EXPERIMENT]
    return evidence, context
