"""Markdown decision memo for one atmosphere state (GET /api/report).

Every figure in the memo comes from the same engine functions every other
endpoint uses; the memo adds no numbers of its own. It exists because a
decision-support tool that cannot hand a reviewer one self-contained page is
not usable in a review: the memo carries the state, the label, the hazard
vector, the boundary, the crew side, the evidence with NTRS links, a
sensitivity sweep, the backtest summary and the limitations list — so the
number and its caveats always travel together.
"""
from __future__ import annotations

from backend.app.methodology import DATA_PROVENANCE, LIMITATIONS
from backend.data import load_experiments
from backend.engine import (
    classify,
    coverage,
    hazard_vector,
    po2_normoxia_pct,
    po2_psia,
    rank_experiments,
)
from backend.engine.backtest import leave_one_out
from backend.engine.flame import CITATIONS as FLAME_CITATIONS
from backend.engine.flame import flame_payload
from backend.engine.loc import (
    P_ENVELOPE_KPA,
    effective_loc,
    epistemic_flag_for_pressure,
    flow_penalty_pct,
    gravity_loc_offset_pct,
    loc_percent,
    temperature_loc_offset_pct,
)
from backend.engine.records import KIND_LABELS, partition, record_kind

PSI_TO_KPA = 6.89476

COMPONENTS = ("ignition", "spread", "persistence", "heat_release", "extinction_margin")

# Sources in the shipped database are not all NTRS documents: two records are
# journal articles (PMC / publisher) and one is a NASA History page. Labelling
# every link "NTRS" would misstate the provenance it is supposed to carry.
SOURCE_LABELS: dict[str, str] = {
    "ntrs": "NTRS",
    "pmc": "PMC",
    "publisher": "journal",
    "nasa-history": "NASA History",
}


def source_label(record: dict) -> str:
    kind = SOURCE_LABELS.get(str(record.get("source_type", "")), "source")
    return f"{kind} {record.get('source_id', '')}".strip()


def build_report(
    pressure_psia: float,
    o2_pct: float,
    gravity: str,
    flow_ms: float,
    temperature_c: float,
    material_class: str,
    generated: str | None = None,
) -> str:
    """Return the memo as Markdown text."""
    exps = load_experiments()
    p_kpa = pressure_psia * PSI_TO_KPA
    vec = hazard_vector(pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
                        material_class)
    label = classify(p_kpa, o2_pct, gravity, material_class, exps)
    cov = coverage(p_kpa, o2_pct, gravity, material_class, exps) * 100.0
    ranked = rank_experiments(p_kpa, o2_pct, gravity, material_class, exps)
    evidence, context = partition(ranked)
    backtest = leave_one_out(exps)
    flame = flame_payload(pressure_psia, o2_pct, gravity, flow_ms, temperature_c,
                          material_class)

    base = loc_percent(p_kpa)
    eff = effective_loc(p_kpa, gravity, flow_ms, temperature_c)
    margin = o2_pct - eff
    flag = epistemic_flag_for_pressure(p_kpa)

    out: list[str] = []
    out.append("# FLARE — Atmosphere Decision Memo")
    out.append("")
    out.append("Fire & Life Atmosphere Risk Explorer · NASA Space Apps Challenge "
               "(\"Flame in Freefall\")")
    if generated:
        out.append(f"Generated: {generated}")
    out.append("")
    out.append("> This memo reports **relative comparison** of one atmosphere against the "
               "NASA microgravity combustion record. It is not an absolute risk assessor "
               "and it issues no operational command (limitation L4).")
    out.append("")

    out.append("## 1. Atmosphere state")
    out.append("")
    out.append("| Parameter | Value |")
    out.append("|---|---|")
    out.append(f"| Total pressure | {pressure_psia:g} psia ({p_kpa:.1f} kPa) |")
    out.append(f"| O2 concentration | {o2_pct:g} % |")
    out.append(f"| Gravity regime | {gravity} |")
    out.append(f"| Forced flow | {flow_ms:g} m/s |")
    out.append(f"| Ambient temperature | {temperature_c:g} °C |")
    out.append(f"| Material class | {material_class} |")
    out.append("")

    out.append("## 2. Evidence status")
    out.append("")
    out.append(f"- **Evidence label: {label}** — computed from the {len(exps)}-record "
               "database at request time.")
    out.append(f"- **Coverage: {cov:.1f}%** (best condition-similarity across the record "
               "set; weighted P 0.35 / O2 0.35 / gravity 0.20 / material class 0.10).")
    out.append(f"- Records nearest this state: {len(evidence)} controlled combustion "
               f"experiments, {len(context)} context records.")
    out.append("")

    out.append("## 3. Fire Hazard Vector (relative, 0-100)")
    out.append("")
    out.append("| Component | Value |")
    out.append("|---|---|")
    for key in COMPONENTS:
        out.append(f"| {key.replace('_', ' ').title()} | {vec[key]:.1f} |")
    out.append("")
    out.append("Persistence and heat release are derived from spread by construction; they "
               "move together with it rather than being independent measurements. "
               "Components support relative comparison of atmospheres only (limitation L4).")
    out.append("")

    out.append("## 4. Flammability boundary")
    out.append("")
    out.append(f"- Ground trend LOC(P) = 15.88 + 200.5/P → **{base:.2f}% O2** at "
               f"{p_kpa:.1f} kPa.")
    out.append(f"- Gravity offset ({gravity}): {gravity_loc_offset_pct(gravity):+.2f} pt")
    out.append(f"- Microgravity flow penalty at {flow_ms:g} m/s: "
               f"{flow_penalty_pct(gravity, flow_ms):+.2f} pt")
    out.append(f"- Ambient-temperature offset at {temperature_c:g} °C: "
               f"{temperature_loc_offset_pct(temperature_c):+.2f} pt")
    out.append(f"- **Effective boundary: {eff:.2f}% O2**; the atmosphere sits "
               f"{margin:+.2f} pt {'above' if margin >= 0 else 'below'} it "
               f"({'spread possible' if margin > 0 else 'no sustained spread predicted'}).")
    out.append(f"- Curve calibration envelope: {P_ENVELOPE_KPA[0]:g}-{P_ENVELOPE_KPA[1]:g} "
               f"kPa → this pressure is **{flag}**.")
    out.append("")

    out.append("## 5. Crew side")
    out.append("")
    out.append(f"- pO2 = {po2_psia(pressure_psia, o2_pct):.2f} psia "
               f"({po2_normoxia_pct(pressure_psia, o2_pct):.1f}% of sea-level normoxia).")
    out.append(f"- Inside the crew-safe planning band pO2 ∈ [2.4, 3.4] psia: "
               f"**{'yes' if vec['crew']['crew_safe'] else 'no'}**. The band is a model "
               "construct of this project, not a NASA requirement (limitation L6).")
    out.append("")

    out.append("## 6. Supporting evidence (controlled experiments, nearest first)")
    out.append("")
    out.append("| Experiment | Mission | Conditions | Verdict | Similarity | Source |")
    out.append("|---|---|---|---|---|---|")
    for e in evidence[:6]:
        out.append(
            f"| {e['experiment_id']} | {e['mission']} | {e['o2_pct']:g}% O2 @ "
            f"{e['pressure_kpa']:g} kPa, {e['gravity']}, {e['flow_ms']:g} m/s | "
            f"{e['verdict']} | {e['similarity'] * 100:.0f}% | [{source_label(e)}]"
            f"({e['source_url']}) |"
        )
    out.append("")
    if context:
        out.append("Context records (no combustion verdict — reported separately so they "
                   "are never read as fire evidence):")
        out.append("")
        for c in context[:3]:
            out.append(f"- `{c['experiment_id']}` ({c['mission']}) — "
                       f"{KIND_LABELS[record_kind(c)]}, similarity "
                       f"{c['similarity'] * 100:.0f}%. [{source_label(c)}]"
                       f"({c['source_url']})")
        out.append("")

    out.append("## 7. Sensitivity of this state")
    out.append("")
    out.append("| Change | Ignition | Spread | Extinction margin | Effective boundary |")
    out.append("|---|---|---|---|---|")
    sweeps = [
        ("Baseline", 0.0, 0.0),
        ("O2 +2 pt", 2.0, 0.0),
        ("O2 -2 pt", -2.0, 0.0),
        ("Flow -0.15 m/s", 0.0, -0.15),
        ("Flow +0.15 m/s", 0.0, 0.15),
        ("Temperature +8 °C", 0.0, None),  # handled below
    ]
    for name, d_o2, d_flow in sweeps:
        if d_flow is None:
            v2 = hazard_vector(pressure_psia, o2_pct, gravity, flow_ms,
                               temperature_c + 8.0, material_class)
            e2 = effective_loc(p_kpa, gravity, flow_ms, temperature_c + 8.0)
        else:
            v2 = hazard_vector(pressure_psia, o2_pct + d_o2, gravity,
                               max(0.0, min(1.0, flow_ms + d_flow)), temperature_c,
                               material_class)
            e2 = effective_loc(p_kpa, gravity, max(0.0, min(1.0, flow_ms + d_flow)),
                               temperature_c)
        out.append(f"| {name} | {v2['ignition']:.1f} | {v2['spread']:.1f} | "
                   f"{v2['extinction_margin']:.1f} | {e2:.2f}% |")
    out.append("")
    out.append("Each row is a full re-evaluation of the deterministic model, not a linear "
               "extrapolation of the baseline row.")
    out.append("")

    out.append("## 8. Model confidence")
    out.append("")
    out.append(f"- Leave-one-out backtest over the seed database: **{backtest['correct']}/"
               f"{backtest['total']} ({backtest['accuracy'] * 100:.1f}%)**, and "
               f"{backtest['accuracy_non_anchor'] * 100:.1f}% on the "
               f"{backtest['total'] - sum(1 for r in backtest['results'] if r['is_fit_anchor'])} "
               "records that are not fit anchors of the curve.")
    misses = [r for r in backtest["results"] if not r["correct"]]
    if misses:
        out.append(f"- Published misses: " + "; ".join(
            f"{r['experiment_id']} (margin {r['margin_pct']:+.2f} pt — "
            f"{r['explanation']})" for r in misses) + ".")
    out.append("- Reproduce with `py -m pytest backend/tests -q` and "
               "`py -m backend.tools.reproduce_dossier_log`.")
    out.append("")

    out.append("## 8. Flame-regime assessment (Freefall Lab quantities)")
    out.append("")
    out.append(f"- Regime: **{flame['regime']['label']}** ({flame['regime']['style']}).")
    out.append(f"- Outcome: **{flame['fate']['label']}** — {flame['fate']['detail']}")
    out.append(f"- Front rate: {flame['front_speed_relative']:.1f}% of the "
               f"{flame['reference']['experiment_id']} anchor (relative units, "
               "never m/s — limitation L4).")
    out.append(f"- Airflow band: {flame['flow_regime']['band']} "
               f"(streamer speed scale {flame['flow_regime']['streamer_speed_scale']}).")
    out.append(f"- Cool-flame phase: {flame['cool_flame_phase']['label']} — "
               f"{flame['cool_flame_phase']['note']}")
    out.append("")

    out.append("## 9. Stated limitations (dossier §4.7)")
    out.append("")
    for lim in LIMITATIONS:
        out.append(f"- **{lim['id']} — {lim['title']}.** {lim['detail']}")
    out.append("")

    out.append("## 10. Load-bearing sources")
    out.append("")
    for prov in DATA_PROVENANCE:
        out.append(f"- {prov['claim']} — {prov['source']}")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 11. Citation matrix (claim → source)")
    out.append("")
    # The full flame/LOC citation set joined to the claims it backs: every
    # quantitative statement in this memo traces to one of these rows.
    out.append("| Claim | Source | Kind |")
    out.append("|---|---|---|")
    for c in FLAME_CITATIONS:
        out.append(f"| {c['claim']} | [{c['source']}]({c['url']}) | {c['kind']} |")
    out.append(f"| LOC(P) ground trend 15.88 + 200.5/P (dossier §4.3) | "
               f"Constellation-era LOC threshold studies; Konno 2023 (J. Fire Sci.); "
               f"He 2021 | peer-reviewed / NASA standard methodology |")
    out.append(f"| Microgravity boundary offset −0.8 pt | Link et al. 2018 (PMC5760683) | "
               f"peer-reviewed |")
    out.append(f"| Partial-g minima near µg value | Ruff, NIST r0200471 | NASA report |")
    out.append("")
    out.append("Full derivations, provenance table and the executed test log: "
               "`docs/SCIENTIFIC-VALIDATION-DOSSIER.md`.")
    out.append("")
    return "\n".join(out)
