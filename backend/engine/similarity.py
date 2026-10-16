"""Query-to-experiment similarity (weights validated in dossier §5, §6 Test 5)."""
from __future__ import annotations


def similarity(
    p_kpa_query: float,
    o2_query: float,
    gravity_query: str,
    material_class_query: str,
    experiment: dict,
) -> float:
    """Weighted distance-based similarity in [0, 1].

    Weights: P 0.35, O2 0.35, gravity 0.20, material class 0.10 (dossier §5).
    """
    dp = abs(p_kpa_query - float(experiment["pressure_kpa"])) / 10.0
    do2 = abs(o2_query - float(experiment["o2_pct"])) / 20.0
    dg = 0.0 if gravity_query == experiment.get("gravity", "microgravity") else 1.0
    dm = 0.0 if material_class_query == experiment.get("material_class", "") else 1.0
    return max(0.0, 1.0 - 0.35 * dp - 0.35 * do2 - 0.20 * dg - 0.10 * dm)


def rank_experiments(
    p_kpa: float,
    o2_pct: float,
    gravity: str,
    material_class: str,
    experiments: list[dict],
) -> list[dict]:
    """Return experiments ranked by similarity (nearest conditions first)."""
    scored = []
    for e in experiments:
        s = similarity(p_kpa, o2_pct, gravity, material_class, e)
        scored.append({**e, "similarity": round(s, 3)})
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored
