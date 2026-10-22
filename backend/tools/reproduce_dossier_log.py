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

import pytest

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

    routed = c.post("/api/ask", json={
        "question": "What if airflow drops to 0.05 m/s?", "pressure_psia": 8.2,
        "o2_pct": 34.0}).json()
    check(f"/api/ask question routing: flow question -> intent "
          f"{routed['intent']!r}, confidence {routed['intent_confidence']}",
          routed["intent"] == "flow_effect" and routed["intent_matched"])
    check("answer text is steered by the question (differs from a crew question)",
          routed["answer"] != a["answer"])

    oos = c.post("/api/ask", json={
        "question": "Write me a poem about Mars", "pressure_psia": 8.2,
        "o2_pct": 34.0}).json()
    check(f"/api/ask out-of-scope question is declared, not narrated "
          f"(intent {oos['intent']!r})", oos["intent"] == "out_of_scope")

    ev = c.get("/api/experiments", params={"pressure_psia": 8.2,
                                           "o2_pct": 34.0}).json()
    kinds = {e["record_kind"] for e in ev["results"]}
    ctx = routed["context_citations"]
    check(f"/api/experiments record kinds {sorted(kinds)}; "
          f"{ev['evidence_count']} experiments + {ev['context_count']} context",
          kinds <= {"experiment", "historical", "specification"}
          and ev["evidence_count"] + ev["context_count"] == ev["count"])
    check(f"/api/ask cites only controlled experiments; context carries "
          f"{ctx} separately",
          "EXPATM-EVA-REF-01" in ctx
          and "EXPATM-EVA-REF-01" not in routed["citations"])

    memo = c.get("/api/report", params={"pressure_psia": 8.2, "o2_pct": 34.0,
                                        "download": "true"})
    check(f"/api/report decision memo: {len(memo.text)} chars markdown, "
          f"{len(memo.text.splitlines())} lines, attachment header set",
          memo.status_code == 200 and "attachment" in memo.headers.get(
              "content-disposition", "")
          and "Stated limitations" in memo.text
          and "Load-bearing sources" in memo.text)

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
          len(m["limitations"]) == 8)

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
    check(f"temperature moves the boundary, not a multiplier: ignition "
          f"18 C {cool['ignition']:.1f} < 30 C {warm['ignition']:.1f}, "
          f"LOC_eff {cool['effective_loc_pct']:.2f} > {warm['effective_loc_pct']:.2f}",
          warm["ignition"] > cool["ignition"]
          and warm["effective_loc_pct"] < cool["effective_loc_pct"])


def test_10_record_taxonomy() -> None:
    """The §6.1 open item, closed: specification and historical records are
    labelled as such and can never be cited as combustion evidence."""
    from backend.engine.intents import Atmosphere, compose
    from backend.engine.records import (
        KIND_EXPERIMENT, KIND_HISTORICAL, KIND_SPECIFICATION, KIND_UNSPECIFIED,
        partition, record_kind,
    )

    print("TEST 10 (record taxonomy — dossier §6.1, closed)")
    exps = load_experiments()
    k = {e["experiment_id"]: record_kind(e) for e in exps}
    check(f"every record classified: {len(k)} records, no unclassified row",
          KIND_UNSPECIFIED not in set(k.values()))
    check(f"APOLLO1-CABIN-REF-01 -> {k['APOLLO1-CABIN-REF-01']!r} (real fire, not a"
          f" controlled experiment)",
          k["APOLLO1-CABIN-REF-01"] == KIND_HISTORICAL)
    check(f"EXPATM-EVA-REF-01 -> {k['EXPATM-EVA-REF-01']!r} (atmosphere spec, no"
          f" combustion verdict)", k["EXPATM-EVA-REF-01"] == KIND_SPECIFICATION)
    ranked = rank_experiments(56.5, 34.0, "microgravity", "polymer", exps)
    evidence, context = partition(ranked)
    check(f"nearest record overall is {ranked[0]['experiment_id']} "
          f"({k[ranked[0]['experiment_id']]}), but the nearest controlled "
          f"experiment is {evidence[0]['experiment_id']}",
          ranked[0]["experiment_id"] != evidence[0]["experiment_id"])
    result = compose("Which experiments support this atmosphere?",
                     Atmosphere(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer"),
                     exps)
    check("answer cites only controlled experiments; the spec record is context "
          f"({', '.join(result['context_citations'])})",
          all(k[c] == KIND_EXPERIMENT for c in result["citations"])
          and "EXPATM-EVA-REF-01" in result["context_citations"])


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


def test_11_flame_regime_and_crossover() -> None:
    """The figures the 3D Freefall Lab screen renders (dossier §4.2.1, L8)."""
    from backend.engine.flame import (
        FATE_SELF_EXTINGUISHING,
        REFERENCE_EXPERIMENT_ID,
        crossover_series,
        flame_payload,
        flame_regime,
        front_speed_relative,
        reference_spread,
    )

    print("TEST 11 (flame regime + ug-vs-1g crossover — Freefall Lab, dossier §4.2.1)")
    ug = flame_regime("microgravity", 0.2, 43.0)
    one_g = flame_regime("earth", 0.2, 43.0)
    check(f"regime flips: microgravity -> {ug['shape']} (buoyant_convection "
          f"{ug['buoyant_convection']}), 1g -> {one_g['shape']}",
          ug["shape"] == "spherical" and ug["buoyant_convection"] is False
          and one_g["shape"] == "teardrop" and one_g["buoyant_convection"] is True)
    check(f"colour tendency: microgravity {ug['colour_tendency']!r} vs 1g "
          f"{one_g['colour_tendency']!r} (BASS-II)",
          "blue" in ug["colour_tendency"] and "yellow" in one_g["colour_tendency"])

    bass = flame_payload(101.3 / 6.89476, 17.0, "microgravity", 0.1, 22.0, "textile")
    check(f"BASS-II-04 (17% O2 @ 0.1 m/s, ug) -> {bass['fate']['label']} "
          f"(margin {bass['hazard']['margin_above_loc_pct']:+.2f} pt)",
          bass["fate"]["code"] == FATE_SELF_EXTINGUISHING)

    ref = reference_spread()
    check(f"front speed is relative to {REFERENCE_EXPERIMENT_ID} "
          f"(spread index {ref:.1f} -> {front_speed_relative(ref):.1f}%)",
          front_speed_relative(ref) == 100.0)

    full = crossover_series(8.2, 0.3, 22.0)
    partial = crossover_series(8.2, 0.2, 22.0)
    check(f"ug boundary sits below 1g: 8.2 psia full flow LOC_ug "
          f"{full['loc_pct']['microgravity']:.2f}% < LOC_1g "
          f"{full['loc_pct']['earth']:.2f}% (offset {full['offset_pt']:.2f} pt)",
          full["offset_pt"] > 0
          and full["loc_pct"]["microgravity"] < full["loc_pct"]["earth"])
    check(f"microgravity flow penalty eats into that offset at 0.2 m/s: "
          f"offset {partial['offset_pt']:.2f} pt, LOC_ug "
          f"{partial['loc_pct']['microgravity']:.2f}%",
          partial["loc_pct"]["microgravity"] == pytest.approx(18.93, abs=0.01))
    band = crossover_series(60.0 / 6.89476, 0.3, 22.0)
    check(f"60 kPa: ug sustains spread where 1g does not (band "
          f"{band['loc_pct']['microgravity']:.2f}-{band['loc_pct']['earth']:.2f}% O2); "
          f"the observed 17% ug record stays a published miss",
          band["loc_pct"]["microgravity"] < band["loc_pct"]["earth"])

    from fastapi.testclient import TestClient

    from backend.app.main import app

    c = TestClient(app)
    f = c.get("/api/flame", params={"pressure_psia": 8.2, "o2_pct": 34.0,
                                   "gravity": "microgravity"}).json()
    check(f"/api/flame: regime {f['regime']['shape']}, fate {f['fate']['label']}, "
          f"front {f['front_speed_relative']}%, {len(f['citations'])} citations "
          f"with URLs, {len(f['notes'])} stated notes",
          all(x["url"].startswith("https://") for x in f["citations"])
          and any("not a CFD" in n for n in f["notes"]))

    # --- flow-regime bands + cool-flame phase (presentation layers, FL2/FL4/FL5)
    fr = flame_payload(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer")["flow_regime"]
    check(f"flow band at 0.2 m/s ug -> {fr['band']!r} "
          f"(streamer scale {fr['streamer_speed_scale']})",
          fr["band"] == "low-flow" and 0.0 < fr["streamer_speed_scale"] <= 1.0)
    cool_on = flame_payload(8.2, 15.0, "microgravity", 0.2, 22.0, "polymer")["cool_flame_phase"]
    cool_off = flame_payload(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer")["cool_flame_phase"]
    cool_1g = flame_payload(8.2, 15.0, "earth", 0.2, 22.0, "polymer")["cool_flame_phase"]
    check(f"cool-flame phase: ug sub-LOC -> {cool_on['label']}, sustained hot -> "
          f"{cool_off['label']}, 1g sub-LOC -> {cool_1g['label']}",
          cool_on["possible"] is True and cool_on["citations"] == ["FL4", "FL5"]
          and cool_off["possible"] is False and cool_1g["possible"] is False
          and "numerical-simulation" in cool_on["note"])


def test_12_mission_scenarios_and_briefing() -> None:
    """Mission flight scenarios + flight-readiness briefing (dossier §4.2.2)."""
    from backend.engine.missions import DEFAULT_COMPARE, SCENARIOS, scenario_payload

    print("TEST 12 (mission scenarios + 1g delta + briefing, dossier §4.2.2)")
    check(f"{len(SCENARIOS)} presets, every one carries provenance + context",
          all(s["provenance"] and s["context"] for s in SCENARIOS))
    ids = {s["id"]: s for s in SCENARIOS}
    pair_keys = ("pressure_psia", "o2_pct", "flow_ms", "temperature_c",
                 "material_class")
    check("Gateway µg/1g pair differs ONLY by gravity",
          all(ids["gateway-orbital"][k] == ids["gateway-ground-eval"][k] for k in pair_keys)
          and ids["gateway-orbital"]["gravity"] == "microgravity"
          and ids["gateway-ground-eval"]["gravity"] == "earth")

    ug = scenario_payload(8.2, 34.0, "microgravity", 0.3, 22.0, "polymer")
    one = scenario_payload(8.2, 34.0, "earth", 0.3, 22.0, "polymer")
    d = ug["margin_above_loc_pct"] - one["margin_above_loc_pct"]
    check(f"µg Gateway margin exceeds its 1g twin by {d:.2f} pt (0 < d < 1.5)",
          0 < d < 1.5)
    check(f"delta wording: {ug['delta_vs_1g']['wording']!r}",
          "1g riskier" in ug["delta_vs_1g"]["wording"])

    from fastapi.testclient import TestClient

    from backend.app.main import app

    c = TestClient(app)
    m = c.get("/api/missions").json()
    check(f"/api/missions: {len(m['scenarios'])} scenarios, "
          f"default compare {m['default_compare']['a']} vs {m['default_compare']['b']}",
          len(m["scenarios"]) >= 4 and m["default_compare"]["a"] == DEFAULT_COMPARE[0])
    rep = c.get("/api/report", params={"pressure_psia": 8.2, "o2_pct": 34.0,
                                       "gravity": "microgravity"}).text
    check("/api/report briefing: flame-regime + cool-flame + citation matrix "
          "sections present (§8-§11)",
          "Flame-regime assessment" in rep and "Citation matrix" in rep
          and "PMC5760683" in rep)


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
        test_10_record_taxonomy,
        test_11_flame_regime_and_crossover,
        test_12_mission_scenarios_and_briefing,
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
