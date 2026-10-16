"""Pareto non-dominated sort (dossier §6 Test 4)."""
from __future__ import annotations


def is_dominated(a: dict, b: dict) -> bool:
    """True if b dominates a on (fire_risk lower-better, eva higher-better)."""
    return (b["fire_risk"] <= a["fire_risk"] and b["eva"] >= a["eva"]
            and (b["fire_risk"] < a["fire_risk"] or b["eva"] > a["eva"]))


def pareto_front(candidates: list[dict]) -> list[dict]:
    """Filter to the non-dominated frontier.

    Each candidate: {id, fire_risk (0-1, lower better), eva (0-1, higher better), ...}.
    """
    return [c for c in candidates if not any(is_dominated(c, o) for o in candidates)]


def weighted_score(candidate: dict, fire_weight: float) -> float:
    """Scalar score for slider ranking: w*fire_safety + (1-w)*eva."""
    fire_safety = 1.0 - candidate["fire_risk"]
    return fire_weight * fire_safety + (1.0 - fire_weight) * candidate["eva"]
