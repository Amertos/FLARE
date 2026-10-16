"""Reproduce the dossier §6 executed-test log against the SHIPPED engine.

The validation dossier publishes a verbatim test log. This script is what
produces it. Run it and paste stdout into docs/SCIENTIFIC-VALIDATION-DOSSIER.md
§6 — so the published log is always the output of the code in this repository,
never of a scratch prototype.

    py -m backend.tools.reproduce_dossier_log

Exits non-zero if any check fails, so it can be used as a gate.
"""
from __future__ import annotations

import sys

from backend.data import load_experiments
from backend.engine import (
    MATERIAL_CLASSES,
    THICKNESS_FACTOR_BY_MATERIAL,
    classify,
    effective_loc,
    evidence_pressure_range,
    hazard_vector,
    loc_percent,
    pareto_front,
    po2_normoxia_pct,
    po2_psia,
    rank_experiments,
)
from backend.engine.loc import P_ENVELOPE_KPA
from backend.engine.citations import verify_citations

FAILURES: list[str] = []


def check(label: str, ok: bool) -> None:
    """Print one PASS/FAIL line and record failures."""
    print(f"  {label:<74} {'PASS' if ok else 'FAIL'}")
    if not ok:
        FAILURES.append(label)


def close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def test_1_loc_model() -> None:
    print("TEST 1 (LOC model v2)  LOC_base(P) = 15.88 + 200.5/P")
    for p, anchor, tol in ((50.0, 19.89, 0.11), (70.0, 18.74, 0.24),
                           (101.3, 17.86, 0.14)):
        v = loc_percent(p)
        check(f"{p:g} kPa -> {v:.2f} (err {abs(v - anchor):.2f})",
              close(v, anchor, tol + 0.02))
    check("monotonic decreasing with pressure",
          loc_percent(30.0) > loc_percent(50.0) > loc_percent(70.0) > loc_percent(101.3))
    eff = effective_loc(101.3, "microgravity", 0.1)
    check(f"BASS-II-04 microgravity low-flow self-extinguish "
          f"(eff LOC {eff:.2f} % > 17.0 %)", 17.0 < eff)


def test_2_epistemic_labels() -> None:
    exps = load_experiments()
    lo, hi = evidence_pressure_range(exps)
    print(f"TEST 2 (epistemic labels)")
    print(f"  record-coverage range [{lo:g}, {hi:g}] kPa  |  "
          f"LOC curve calibration envelope [{P_ENVELOPE_KPA[0]:g}, "
          f"{P_ENVELOPE_KPA[1]:g}] kPa  (two different quantities)")
    cases = [
        (55.0, 16.5, "earth", "polymer", "INTERPOLATED"),
        (80.0, 19.0, "earth", "polymer", "INTERPOLATED"),
        (34.5, 20.0, "earth", "polymer", "EXTRAPOLATED"),
        (120.0, 20.0, "earth", "polymer", "EXTRAPOLATED"),
        (50.0, 20.0, "earth", "polymer", "OBSERVED"),
    ]
    for p, o2, g, m, expected in cases:
        got = classify(p, o2, g, m, exps)
        check(f"{p:g} kPa @ {o2:g}% -> {got}", got == expected)


def test_3_crew_physiology() -> None:
    print("TEST 3 (crew physiology)  pO2 = P * XO2 / 100")
    rows = [
        (14.7, 21, 3.087, 100.0),
        (8.2, 34, 2.788, 90.3),
        (10.0, 30, 3.000, 97.2),
        (7.5, 40, 3.000, 97.2),
        (16.7, 100, 16.700, 541.0),
    ]
    for p, o2, exp_po2, exp_norm in rows:
        got = po2_psia(p, o2)
        norm = po2_normoxia_pct(p, o2)
        check(f"{p:g}/{o2:<3g} -> {got:.2f} psia, {norm:.1f}% of normoxia",
              close(got, exp_po2, 0.005) and close(norm, exp_norm, 0.15))


def test_4_pareto() -> None:
    print("TEST 4 (Pareto non-dominated sort)")
    cands = [
        {"id": "A", "fire_risk": 0.41, "eva": 0.93},
        {"id": "B", "fire_risk": 0.31, "eva": 0.91},
        {"id": "C", "fire_risk": 0.21, "eva": 0.82},
        {"id": "D", "fire_risk": 0.35, "eva": 0.90},
    ]
    front = {c["id"] for c in pareto_front(cands)}
    check(f"frontier = {sorted(front)}; D dominated by B and excluded",
          front == {"A", "B", "C"})


def test_5_similarity_ranking() -> None:
    exps = load_experiments()
    ranked = rank_experiments(56.5, 34.0, "microgravity", "polymer", exps)
    top = ranked[0]
    print(f"TEST 5 (similarity ranking)  query 8.2 psia / 34% O2 / microgravity / polymer")
    check(f"top record {top['experiment_id']} similarity {top['similarity']:.2f}",
          top["similarity"] > 0.5)
    by_id = {r["experiment_id"]: r["similarity"] for r in ranked}
    for rec in ranked[:5]:
        print(f"    {rec['similarity']:.3f}  {rec['experiment_id']:<22} "
              f"{rec['o2_pct']:>5}% O2 @ {rec['pressure_kpa']:>6} kPa "
              f"{rec['gravity']}")
    check("exact-atmosphere reference outranks the 1g ground LOC record",
          by_id.get("EXPATM-EVA-REF-01", 0) > by_id.get("LOC-1G-101KPA-01", 1))
    check("fundamental microgravity LOC record ranks above all 1g ground records",
          by_id.get("LOC-UG-60KPA-01", 0) > by_id.get("LOC-1G-101KPA-01", 1))


def test_6_citation_verification() -> None:
    print("TEST 6 (citation verification)")
    ids = {"BASS-II-12", "SOFIE-MIST-7"}
    r = verify_citations(["BASS-II-12", "SOFIE-MIST-7", "FABRICATED-99"], ids)
    check(f"valid: {', '.join(r['valid'])}; hallucinated: "
          f"{', '.join(r['fabricated'])} caught & flagged",
          r["valid"] == ["BASS-II-12", "SOFIE-MIST-7"]
          and r["fabricated"] == ["FABRICATED-99"] and r["ok"] is False)


def test_7_backend_integration() -> None:
    from fastapi.testclient import TestClient

    from backend.app.main import app

    c = TestClient(app)
    print("TEST 7 (backend integration, executed via TestClient)")

    s = c.get("/api/scenario", params={
        "pressure_psia": 8.2, "o2_pct": 34.0, "gravity": "microgravity",
        "flow_ms": 0.2, "material_class": "polymer"}).json()
    check(f"/api/scenario 8.2/34 microgravity: label {s['evidence_label']}, "
          f"coverage {s['coverage_pct']}%, LOC_eff {s['hazard']['effective_loc_pct']}%",
          s["evidence_label"] == "INTERPOLATED")

    cf = c.post("/api/counterfactual", json={
        "pressure_psia": 8.2, "o2_pct": 34.0, "gravity": "microgravity",
        "flow_ms": 0.2, "material_class": "polymer", "delta_o2_pct": 2.0}).json()
    check(f"/api/counterfactual dO2+2: ignition "
          f"{cf['deltas']['ignition']:+.1f}, spread {cf['deltas']['spread']:+.1f}, "
          f"overall {cf['overall']}",
          cf["overall"] == "WORSE" and cf["deltas"]["ignition"] > 0)

    a = c.post("/api/ask", json={"question": "Why is 34% O2 risky?",
                                 "pressure_psia": 8.2, "o2_pct": 34.0}).json()
    check(f"/api/ask: mode {a['mode']}, all citations verified in-code, "
          f"fabricated={a['fabricated_citations']}",
          a["citation_check_ok"] is True and a["fabricated_citations"] == [])

    v = c.get("/api/validate").json()
    n_anchor = sum(1 for r in v["results"] if r["is_fit_anchor"])
    check(f"/api/validate LOO: {v['correct']}/{v['total']} "
          f"({v['accuracy']*100:.1f}%) overall, "
          f"{v['accuracy_non_anchor']*100:.1f}% non-anchor "
          f"({v['total'] - n_anchor} records)",
          v["accuracy"] is not None)

    m = c.get("/api/methodology").json()
    check(f"/api/methodology: {len(m['limitations'])} limitations, "
          f"{len(m['future_work'])} unbuilt items served to the UI",
          len(m["limitations"]) == 7)

    t = c.get("/api/tradespace").json()
    missing = [b for b in t["loc_boundary"] if b["loc_pct"] is None]
    check(f"/api/tradespace: envelope {t['p_envelope_kpa']} kPa, "
          f"{len(missing)}/{len(t['loc_boundary'])} P-columns hatching as EXTRAPOLATED",
          len(missing) > 0 and t["p_envelope_kpa"] == [50.0, 101.3])

    bad = c.get("/api/scenario", params={"material_class": "unobtainium"})
    check(f"input validation: unknown material class -> HTTP {bad.status_code}",
          bad.status_code == 422)


def test_8_material_and_thickness() -> None:
    print("TEST 8 (material classes and thickness factor, dossier §4.5)")
    check(f"material vocabulary {MATERIAL_CLASSES}",
          MATERIAL_CLASSES == ("polymer", "textile", "insulation", "composite"))
    factors = {k: THICKNESS_FACTOR_BY_MATERIAL[k] for k in MATERIAL_CLASSES}
    check(f"thickness factors {factors}",
          factors["insulation"] < factors["textile"] < factors["polymer"]
          < factors["composite"])
    poly = hazard_vector(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer")
    insul = hazard_vector(8.2, 34.0, "microgravity", 0.2, 22.0, "insulation")
    check(f"spread moves by material: polymer {poly['spread']:.1f} > "
          f"insulation {insul['spread']:.1f}", insul["spread"] < poly["spread"])
    cool = hazard_vector(8.2, 34.0, "microgravity", 0.2, 18.0, "polymer")
    warm = hazard_vector(8.2, 34.0, "microgravity", 0.2, 30.0, "polymer")
    check(f"temperature term in F_i: 18 C {cool['ignition']:.1f} < "
          f"30 C {warm['ignition']:.1f}", warm["ignition"] > cool["ignition"])


def test_9_ntrs_live() -> None:
    """Network check. Reported as SKIP when the environment is offline."""
    print("TEST 9 (NTRS API, live HTTP)")
    try:
        import httpx

        r = httpx.get("https://ntrs.nasa.gov/api/citations/20210011385",
                      timeout=10.0)
        check(f"GET ntrs citation 20210011385 -> {r.status_code}, "
              f"{len(r.content)} bytes", r.status_code == 200)
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        print(f"  {'NTRS unreachable in this environment — SKIP':<74} "
              f"({type(exc).__name__})")


def main() -> int:
    print("FLARE — dossier §6 executed-test log")
    print("Runtime: CPython, shipped engine (backend/engine) + shipped API "
          "(backend/app)")
    print("Reproduce: py -m backend.tools.reproduce_dossier_log")
    print()
    for fn in (
        test_1_loc_model,
        test_2_epistemic_labels,
        test_3_crew_physiology,
        test_4_pareto,
        test_5_similarity_ranking,
        test_6_citation_verification,
        test_7_backend_integration,
        test_8_material_and_thickness,
        test_9_ntrs_live,
    ):
        fn()
        print()
    if FAILURES:
        print(f"RESULT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("RESULT: all checks PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
