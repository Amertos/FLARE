# FLARE — Scientific Validation Dossier
**Fire & Life Atmosphere Risk Explorer**
*Prepared to NASA-engineering documentation standard. Every claim traced to a source; every model derived with stated assumptions; every empirical result from an actually executed test (test log included, §6).*

Version 1.0 · October 2026 · For the NASA Space Apps Challenge "Flame in Freefall"

---

## 1. Scope and Design Philosophy

FLARE is a **decision-support system** for exploring spacecraft/habitat atmospheres. It does **not** predict fire with absolute certainty and it never issues operational commands. Its purpose:

> *Given an atmosphere state X, what does NASA's microgravity combustion experimental record imply about fire behavior and crew physiology, how confident is each statement, and where does the experimental evidence end?*

Design rules (all enforced in code):
1. **No single fire-risk number.** Outputs are a 5-component Fire Hazard Vector with per-component epistemic labels.
2. **Every quantitative output carries an evidence label** (Observed / Interpolated / Extrapolated / Insufficient) computed from the experimental database, never hand-assigned at runtime.
3. **Every experiment record links to its NASA source** (NTRS document ID + URL).
4. **The engine is deterministic** — same inputs, same outputs, and **no language model is called anywhere in this build**. Questions are routed by an explicit, inspectable keyword model into an intent that selects which engine quantities an answer reports (`backend/engine/intents.py`); the routing decision is returned to the client with the answer, and a question outside the engine's scope is answered as out-of-scope rather than narrated.
5. **Model validity regions are explicit.** The flammability boundary is rendered only where experimental coverage exists.

---

## 2. State Variables and Output Vector

### 2.1 Atmosphere state

$$X = [P,\; X_{O_2},\; T,\; v,\; g,\; M]$$

| Symbol | Meaning | Units | Range in FLARE v1 |
|---|---|---|---|
| P | total pressure | psia (kPa) | 4.0 – 16.7 psia (27.6 – 115 kPa) |
| X_O₂ | O₂ molar concentration | % | 14 – 45 % (special presets outside) |
| T | gas temperature | °C | 18 – 30 °C |
| v | forced airflow velocity | m/s | 0 – 1.0 m/s |
| g | gravity regime | ×g | 0 (µg), 0.165 (Lunar), 0.38 (Mars), 1 (Earth) |
| M | material | class | polymer / textile / insulation / composite |

### 2.2 Output: Fire Hazard Vector

$$Y = [F_i,\; F_s,\; F_p,\; F_b,\; F_e,\; U]$$

| Component | Meaning | Basis |
|---|---|---|
| F_i | Ignition tendency | distance of X_O₂ above LOC boundary |
| F_s | Flame-spread tendency | F_i × flow/geometry modifiers |
| F_p | Flame persistence | F_s × thermal-mass modifier |
| F_b | Burning intensity | F_p × HRR-scale reference |
| F_e | Extinction margin | how far conditions must shift to cross LOC from above |
| U | uncertainty | coverage-derived (§5) |

Each component ∈ [0, 100] with an epistemic label and coverage %.

---

## 3. Crew-Side Physiology Model (complete derivation)

### 3.1 Oxygen partial pressure

**Equation (exact, definitional):**

$$pO_2 = P \cdot X_{O_2}$$

This is the standard physiological quantity determining alveolar oxygen availability (hypoxia risk). All values below are **computed, not estimated** (§6, Test 3):

| Atmosphere | P (psia) | O₂ (%) | pO₂ (psia) | % of sea-level normoxia |
|---|---|---|---|---|
| Sea level (reference) | 14.7 | 21 | 3.087 | 100 % |
| ISS nominal | 14.7 | 21 | 3.087 | 100 % |
| **Exploration Atmosphere** | **8.2** | **34** | **2.788** | **90.3 %** |
| Trade candidate | 10.0 | 30 | 3.000 | 97.2 % |
| Trade candidate | 7.5 | 40 | 3.000 | 97.2 % |
| **Apollo 1 cabin** | **16.7** | **100** | **16.700** | **541 %** |

### 3.2 The core trade, made quantitative

The 10/30 and 7.5/40 atmospheres have **identical pO₂ (3.00 psia)** — physiologically equivalent for hypoxia. But 40% O₂ at 7.5 psia delivers oxygen to a flame by diffusion at higher molar fraction, and flammability limits correlate with oxygen concentration (LOC), not pO₂. **Two crew-equivalent atmospheres are not fire-equivalent.** This is the quantitative heart of the atmosphere-design compromise FLARE visualizes.

### 3.3 Provenance

- **Exploration Atmosphere definition (8.2 psia / 34% O₂ / 66% N₂, 56.5 kPa):** NASA Artemis targeting, per ICES-2026-324, NTRS 20260002050 (verified July 2026); Kluis & Loeppky 2021, PMC8594431 ("8.2 psia and 34% oxygen ... lowered the risk of hypoxia while remaining ... rapid EVA"); NASA JSC prebreathe protocol studies (15-minute EVA prebreathe using NASA's Exploration Atmosphere).
- **Sea-level normoxia reference:** standard atmosphere, 21% O₂.

### 3.4 Stated simplifications
- FLARE v1 uses pO₂ (plus nominal CO₂/trace-gas assumptions) as the hypoxia proxy. It does not model pressure-reduction lower limits (PRLL) or oxygen toxicity upper limits as a function of exposure duration. Crew-safe region on the map is drawn from pO₂ ∈ [2.4, 3.4] psia (≈78–110% normoxia), a conservative planning band — labeled as a model construct, not a NASA requirement.

---

## 4. Fire-Side Model: LOC Boundary Engine (complete derivation)

### 4.1 The governing quantity

**Limiting Oxygen Concentration (LOC):** the O₂ molar concentration above which sustained flame spread is possible for a given material, pressure, flow and gravity regime. LOC is the quantity used in NASA material-flammability methodology (NASA-STD-6001 lineage) and is the boundary FLARE renders.

### 4.2 Published behavior reproduced

Established in the experimental literature (all sources verified):
- **LOC decreases as total pressure increases** (Constellation-era threshold studies; Konno 2023, J. Fire Sci.; He 2021).
- In microgravity, **flames can spread at lower O₂ than in 1g** in some regimes — µg spread sustained at ≈17% O₂ at ~60 kPa vs ≈18% at 1g (Link et al. 2018, PMC5760683); materials burn at lower-than-expected O₂ (UC Berkeley/SoFIE, Dec 2024: spread at 19.8% O₂, 60 kPa, 12.7 mm sample).
- Minimum O₂ for flame spread at **Lunar and Martian gravity is near the microgravity value** (Ruff, NIST r0200471).
- **Reduced flow suppresses spread in µg** at near-limit conditions (BASS-II, NTRS 20210011385: main variables were ambient O₂, ventilation flow velocity, fuel type/thickness/geometry).

### 4.2.1 Visual behaviour rendered by the Freefall Lab screen

These statements are what the 3D screen is allowed to show. Each one is either an engine output or a cited published result, and each is returned by `GET /api/flame` with its source so the UI can print it next to the figure. The screen is a **schematic**, not a CFD solution — stated in the product as limitation L8.

| Rendered behaviour | Basis | Source |
|---|---|---|
| No buoyancy in microgravity → no upward teardrop; the rendered flame is round, and a teardrop at 1g / partial g | Absence of buoyant convection in µg | NASA SVS "Spherical Flames" (svs.gsfc.nasa.gov/11640) — NASA visualisation, not peer-reviewed |
| Blue-dominant, low-soot tendency in µg; bluer, longer and more spherical as opposed flow falls | BASS-II (PMMA, ISS) | Link et al. 2018, Sci. Rep. (PMC5760683) — peer-reviewed |
| No universal "space burns slower": the µg boundary sits **below** the 1g boundary at the same pressure | Engine gravity offset (−0.8 pt), which encodes the same published ordering | Engine (`loc.py`) + Link et al. 2018 |
| A cool-flame note where spread is low in µg | Non-premixed µG cool flames first observed in FLEX (2012); faint and low-temperature | NASA "Cool Flames Created During a First for ISS Research"; NTRS 20150018397 |
| Airflow rendered as streamers whose speed is set by a four-band flow regime (near-zero / low / moderate / full at ≥ 0.4 m/s); no streamers in buoyant gravity | BASS-II: low opposed flow makes the µg flame bluer, longer, more spherical until it extinguishes; bands are presentation bins around that finding, the quantitative flow term is the existing 1.5 pt/0.25 m/s LOC penalty | Link et al. 2018 (PMC5760683) | Engine `flame.flow_regime` (§6 Test 11) |
| A faint cool-flame ghost after hot-flame extinction — shown ONLY in microgravity states predicted below the boundary or marginal; always labelled "qualitative" | FLEX (2012) µG cool flames persist after hot-flame extinction; the ~700 K reaction zone of the NTRS record is a numerical-simulation result, not a measurement, and no cool-flame chemistry exists in this model | NASA cool-flames article; NTRS 20150018397 | Engine `flame.cool_flame_phase` (§6 Test 11) |
| Ember particles ride upward in a buoyant plume and drift outward slowly in µg; the flame leans downstream with imposed flow in µg | Same BASS-II/absence-of-buoyancy regime descriptors, rendered as particle motion | NASA SVS 11640; Link et al. 2018 | engine-sourced render, no new claim |
| A translucent "1g ghost" surface overlays the ignition field computed at 1g, so the µg-vs-1g boundary shift is visible as geometry | Engine output — the same hazard function with the gravity term changed; no new measurements | Engine (`/api/tradespace` `ghost_grid_1g`) | §6 Test 7 envelope figures unchanged |
| Hover readout of (P, O₂, ignition index) anywhere on the surface | Direct grid readback | Engine grid | no new claim |

**Not claimed.** That µG flames are always spherical (shape also depends on fuel geometry and imposed ventilation, which this model does not resolve); that blue/soot-free applies to every µG flame; that flame spread is orientation-independent, or any absolute spread rate in m/s — the screen's front speed is a percentage of the Saffire-I reference condition in the curated database. Also not claimed: that the flow bands are thresholds (they are presentation bins around a cited qualitative finding), that the cool-flame ghost predicts a cool flame (the engine has no cool-flame chemistry — the gating logic reports where a published phase *could* exist relative to the hot-flame boundary), or any absolute spread rate. The ~700 K reaction-zone figure quoted from the NTRS record is a **numerical-simulation result**, not a measurement, and is labelled as such wherever it appears.

**Known engine miss carried into this screen.** At 60 kPa the engine's µG boundary is 18.42% O₂, while the published µG spread record sits at 17.0% (SAFFIRE/LOC-UG-60KPA-01). That record is the one published backtest miss with the largest margin, and the crossover chart therefore asserts only the *ordering* (µG below 1g), not the observed 17% value.

### 4.2.2 Mission flight scenarios and the flight-readiness briefing

Five real-hardware presets (Artemis Lunar Lander cabin, Gateway ground twin, Gateway orbital, SAFFIRE-IV payload condition, ISS depressurisation segment) are served fully evaluated by `GET /api/missions`. Each carries its published provenance line and a **1g ground-lab twin** at the same non-gravity parameters; the µg-vs-1g margin delta is computed by the same engine functions, never hand-written (§6 Test 12 asserts the Gateway pair differs only by gravity and that the µg margin exceeds the twin's by the gravity offset, 0.80 pt). The decision memo (`GET /api/report`) doubles as a flight-readiness briefing: it adds a flame-regime assessment (regime, fate, front rate, airflow band, cool-flame status) and a **citation matrix** (§11) that joins every load-bearing claim to its NTRS/PMC source. Limitations L1-L8 travel with every briefing.

### 4.3 Model form (v2 — the shipped model)

$$LOC_{base}(P) = a + \frac{b}{P}$$

**Correction history (documented openly):** the first fit (v1) anchored the curve to two points from *different gravity regimes* (µg 17% @ 60 kPa vs 1g 21% @ 101.3 kPa). Unit tests caught that this produced LOC *increasing* with pressure — contradicting the published trend. v1 was rejected. v2 fits the **1g ground trend** to three same-regime anchors and applies gravity as a separate, cited offset. This correction is retained in the record because it demonstrates exactly the failure mode FLARE's testing discipline exists to catch.

**v2 anchors (1g ground, PMMA-class, LOC(P) series):** (50 kPa, ~20%), (70 kPa, ~18.5%), (101.3 kPa, ~18%).

**Least-squares fit (executed):**

$$\boxed{LOC_{base}(P) = 15.88 + \frac{200.5}{P_{kPa}}}$$

Max anchor error: 0.25 pt. dLOC/dP < 0 as published.

**Gravity offsets (pts, added to base; dossier §4.5):** microgravity −0.8 · lunar −0.75 · mars −0.7 · earth 0 (Link 2018: µg sustains spread ≈1 pt below 1g; Ruff/NIST: lunar/Mars minima near µg).

**Microgravity flow penalty (pts, added in µg only):** 0 above 0.25 m/s; rises linearly to +1.5 pt at 0 flow. Direction from BASS-II near-limit behavior (low flow degrades O₂ transport in µg; buoyancy does so in 1g, hence no 1g penalty). Magnitude calibrated so BASS-II-04 (17% O₂, 0.1 m/s, µg → observed self-extinguish) classifies correctly.

### 4.4 Empirical verification (executed)

| Check | Predicted | Published/Observed | Result |
|---|---|---|---|
| LOC base @ 50 kPa | 19.89 % | ~20 % | ✅ 0.11 pt |
| LOC base @ 70 kPa | 18.74 % | ~18.5 % | ✅ 0.24 pt |
| LOC base @ 101.3 kPa | 17.86 % | ~18 % | ✅ 0.14 pt |
| Monotonic trend | LOC falls as P rises | published trend | ✅ reproduced |
| BASS-II-01 (17%, 0.25 m/s, µg) | below boundary → self-extinguish | self-extinguish | ✅ |
| BASS-II-02 (19%, 0.25 m/s, µg) | above boundary → spread | spread | ✅ |
| BASS-II-04 (17%, 0.1 m/s, µg) | flow penalty pushes below boundary → self-extinguish | self-extinguish | ✅ |
| Extrapolation @ 30 kPa | flagged EXTRAPOLATED | n/a | ✅ flag correct |

**Leave-one-out backtest against the full seed DB (executed):** 7/12 overall (58.3%); **7/9 non-anchor records (77.8%)**; all 3 anchor-record misses carry per-miss explanations in the UI (near-tie classification of the curve's own anchors is expected and reported transparently). Miss explanations included for every failure.

### 4.5 Gravity and flow modifiers (v1, direction-of-effect cited)

- **Gravity:** LOC(g) for Lunar (0.165g) and Mars (0.38g) is set within ±1 pt of the µg LOC, per Ruff (NIST): "minimum oxygen concentration required for flame-spread at Lunar and Martian gravity levels is very near that for microgravity." The interpolation between µg and 1g LOC is therefore *narrow* — a genuine, cited, non-obvious result FLARE shows.
- **Flow:** in µg at near-limit O₂, reducing forced flow below ≈0.1 m/s pushes effective LOC upward (BASS-II near-limit behavior). Implemented as a flow modifier on the effective boundary; direction-of-effect from BASS-II matrices.
- **Geometry/thickness:** thin samples burn more readily than thick (BASS-II fuel thickness/geometry as tested variables); v1 applies a conservative thickness factor per material class.

### 4.6 Hazard-vector derivation

Each component is a deterministic function of the state:

- **F_i (ignition)** = clamp01((X_O₂ − LOC_eff(P,g,v)) / 25 pt margin span) scaled 0–100. Ambient temperature enters through LOC_eff — a warmer cabin lowers the effective boundary — and not as a multiplier on the index, so every component stays inside 0–100 across the whole slider range (an earlier prototype multiplied the index and saturated 39% of the map; that build was rejected). Above the boundary → tendency rises with margin above LOC; below → near-zero tendency with a small floor.
- **F_s (spread)** = F_i × f_flow (µg: strong suppression at low v; 1g: buoyancy supplies transport, weaker v-dependence) × f_thickness.
- **F_p (persistence)** = F_s × f_thermal-mass (thick samples self-sustain longer after ignition source removal).
- **F_b (heat release)** = F_p scaled by the BASS-II heat-release-rate frame (measured HRR in glovebox-scale tests was well below 100 W; FLARE reports relative intensity, never absolute W for cabin-scale fires).
- **F_e (extinction margin)** = X_O₂ − LOC_eff(P,g,v) when above the boundary: the O₂ (or pressure) reduction required to cross below LOC. This is also the suppressant-dilution logic used in BASS-II (N₂ dilution to reduce effective O₂).
- **U (uncertainty)** = 1 − coverage (§5).

### 4.7 Explicit validity limits

1. 2-parameter fit, material-class specific; not a chemistry model of individual materials.
2. Boundary rendered **only within the experimental coverage envelope**; outside it the map shows a hatched "EXTRAPOLATED — insufficient NASA data" zone.
3. Radiation–convection coupling not modeled in v1. Smoldering out of scope.
4. The hazard vector supports **relative comparison of atmospheres**; it is not an absolute risk assessor.
5. Flow/gravity modifiers are semi-quantitative: direction-of-effect is cited, magnitudes are fit choices stated in code.

---

## 5. Epistemic Classification (exact, tested rules)

| Label | Rule (P-axis tolerance ±8 kPa, executed in §6 Test 2) |
|---|---|
| **Observed** | ≥1 experiment within tolerance on *all* critical axes (P, O₂, gravity regime, material class) |
| **Interpolated** | Query inside the record-coverage range [min, max] of the database on an axis, but no direct match |
| **Extrapolated** | Query outside the envelope on any axis (e.g., 34.5 kPa or 120 kPa → EXTRAPOLATED, 0 nearby experiments) |
| **Insufficient** | <2 compatible experiments in the neighborhood |

**Coverage %** = weighted similarity of the query to the experimental record:
sim = max(0, 1 − 0.35·|ΔP|/10 kPa − 0.35·|ΔO₂|/20 % − 0.20·(g mismatch) − 0.10·(material-class mismatch))

**Two envelopes, deliberately distinct.** The label rule above asks *"is there any record near here?"* and uses the record-coverage range — `[50, 115.1] kPa`, the min/max of the shipped database (`engine.epistemics.evidence_pressure_range`). The map asks a different question — *"is the LOC curve calibrated here?"* — and uses the curve's calibration envelope `[50, 101.3] kPa` (`engine.loc.P_ENVELOPE_KPA`). The two disagree only because of the Apollo 1 historical reference at 115.1 kPa, which is a real record but not a controlled LOC measurement. Collapsing them into one number would either overstate the curve's validity or hide Apollo 1 from the evidence view.

**Evidence records vs context records.** Nearest-condition ranking answers *"what is closest?"*, which is not the same question as *"what supports this claim?"*. Every record is therefore classified from its own fields into `experiment` (a controlled combustion test with an outcome verdict), `historical` (a real fire that was not a controlled experiment — the Apollo 1 cabin reference) or `specification` (an atmosphere/crew reference carrying no combustion verdict — the Exploration Atmosphere reference), by `backend/engine/records.py`. Only `experiment` records may be cited as supporting fire evidence; the other kinds are reported separately as context. A unit test asserts that every shipped record maps to a known kind, so a new `outcome_type` cannot silently enter the evidence pool.

Executed ranking check (§6 Test 5), as produced by the shipped engine for a 8.2 psia/34% µg/polymer query: `EXPATM-EVA-REF-01` (the exact-atmosphere reference) 0.700, `LOC-UG-60KPA-01` (the fundamental microgravity LOC record) 0.580, `SOFIE-MIST-REF-01` 0.496, `SOFIE-MIST-REF-02` 0.338, `LOC-PRESSURE-TREND-02` 0.327, and the 1g ground LOC record 0.000 — nearest conditions first, as an engineer would expect.

---

## 6. Executed Test Log (verbatim results)

Everything below is the **verbatim stdout of the shipped engine and API in this repository** — not a prototype run. It is regenerated by a committed script, so the published log cannot drift from the code it describes:

```
py -m backend.tools.reproduce_dossier_log
```

The script exits non-zero if any check fails. The same claims are asserted independently by the unit suite. **Figures that disagreed with the shipped code have been replaced** — Test 5 in particular previously published prototype similarity values that this engine does not reproduce.

```
FLARE — dossier §6 executed-test log
Runtime: CPython, shipped engine (backend/engine) + shipped API (backend/app)
Reproduce: py -m backend.tools.reproduce_dossier_log

TEST 1 (LOC model v2)  LOC_base(P) = 15.88 + 200.5/P
  50 kPa -> 19.89 (err 0.00)                                                 PASS
  70 kPa -> 18.74 (err 0.00)                                                 PASS
  101.3 kPa -> 17.86 (err 0.00)                                              PASS
  monotonic decreasing with pressure                                         PASS
  BASS-II-04 microgravity low-flow self-extinguish (eff LOC 17.96 % > 17.0 %) PASS

TEST 2 (epistemic labels)
  record-coverage range [50, 115.1] kPa  |  LOC curve calibration envelope [50, 101.3] kPa  (two different quantities)
  55 kPa @ 16.5% -> INTERPOLATED                                             PASS
  80 kPa @ 19% -> INTERPOLATED                                               PASS
  34.5 kPa @ 20% -> EXTRAPOLATED                                             PASS
  120 kPa @ 20% -> EXTRAPOLATED                                              PASS
  50 kPa @ 20% -> OBSERVED                                                   PASS

TEST 3 (crew physiology)  pO2 = P * XO2 / 100
  14.7/21  -> 3.09 psia, 100.0% of normoxia                                  PASS
  8.2/34  -> 2.79 psia, 90.3% of normoxia                                    PASS
  10/30  -> 3.00 psia, 97.2% of normoxia                                     PASS
  7.5/40  -> 3.00 psia, 97.2% of normoxia                                    PASS
  16.7/100 -> 16.70 psia, 541.0% of normoxia                                 PASS

TEST 4 (Pareto non-dominated sort)
  frontier = ['A', 'B', 'C']; D dominated by B and excluded                  PASS

TEST 5 (similarity ranking)  query 8.2 psia / 34% O2 / microgravity / polymer
  top record EXPATM-EVA-REF-01 similarity 0.70                               PASS
    0.700  EXPATM-EVA-REF-01       34.0% O2 @   56.5 kPa earth
    0.580  LOC-UG-60KPA-01         17.0% O2 @   60.0 kPa microgravity
    0.496  SOFIE-MIST-REF-01       30.0% O2 @   68.9 kPa microgravity
    0.338  SOFIE-MIST-REF-02       21.0% O2 @   68.9 kPa microgravity
    0.327  LOC-PRESSURE-TREND-02   20.0% O2 @   50.0 kPa earth
  exact-atmosphere reference outranks the 1g ground LOC record               PASS
  fundamental microgravity LOC record ranks above all 1g ground records      PASS

TEST 6 (citation verification)
  valid: BASS-II-12, SOFIE-MIST-7; hallucinated: FABRICATED-99 caught & flagged PASS

TEST 7 (backend integration, executed via TestClient)
  /api/scenario 8.2/34 microgravity: label INTERPOLATED, coverage 69.9%, LOC_eff 18.93% PASS
  /api/counterfactual dO2+2: ignition +8.0, spread +5.7, overall WORSE       PASS
  /api/ask: mode offline-deterministic, all citations verified in-code, fabricated=[] PASS
  /api/ask question routing: flow question -> intent 'flow_effect', confidence 0.52 PASS
  answer text is steered by the question (differs from a crew question)      PASS
  /api/ask out-of-scope question is declared, not narrated (intent 'out_of_scope') PASS
  /api/experiments record kinds ['experiment', 'historical', 'specification']; 18 experiments + 2 context PASS
  /api/ask cites only controlled experiments; context carries ['EXPATM-EVA-REF-01', 'APOLLO1-CABIN-REF-01'] separately PASS
  /api/report decision memo: 11568 chars markdown, 129 lines, attachment header set PASS
  /api/validate LOO: 7/12 (58.3%) overall, 77.8% non-anchor (9 records)      PASS
  /api/methodology: 8 limitations, 4 unbuilt items served to the UI          PASS
  /api/tradespace: envelope [50.0, 101.3] kPa, 15/34 P-columns hatching as EXTRAPOLATED PASS
  input validation: unknown material class -> HTTP 422                       PASS

TEST 8 (material classes and thickness factor, dossier §4.5)
  material vocabulary ('polymer', 'textile', 'insulation', 'composite')      PASS
  thickness factors {'polymer': 1.0, 'textile': 0.85, 'insulation': 0.7, 'composite': 1.15} PASS
  spread moves by material: polymer 43.2 > insulation 30.2                   PASS
  temperature moves the boundary, not a multiplier: ignition 18 C 58.7 < 30 C 63.5, LOC_eff 19.33 > 18.13 PASS

TEST 9 (NTRS API, live HTTP)
  GET ntrs citation 20210011385 -> 200, 7042 bytes                           PASS

TEST 10 (record taxonomy — dossier §6.1, closed)
  every record classified: 20 records, no unclassified row                   PASS
  APOLLO1-CABIN-REF-01 -> 'historical' (real fire, not a controlled experiment) PASS
  EXPATM-EVA-REF-01 -> 'specification' (atmosphere spec, no combustion verdict) PASS
  nearest record overall is EXPATM-EVA-REF-01 (specification), but the nearest controlled experiment is LOC-UG-60KPA-01 PASS
  answer cites only controlled experiments; the spec record is context (EXPATM-EVA-REF-01, APOLLO1-CABIN-REF-01) PASS

TEST 11 (flame regime + ug-vs-1g crossover — Freefall Lab, dossier §4.2.1)
  regime flips: microgravity -> spherical (buoyant_convection False), 1g -> teardrop PASS
  colour tendency: microgravity 'blue-dominant (low soot)' vs 1g 'yellow-orange (soot-radiating)' (BASS-II) PASS
  BASS-II-04 (17% O2 @ 0.1 m/s, ug) -> self-extinguishing (margin -0.96 pt)  PASS
  front speed is relative to SAFFIRE-I-01 (spread index 10.4 -> 100.0%)      PASS
  ug boundary sits below 1g: 8.2 psia full flow LOC_ug 18.63% < LOC_1g 19.43% (offset 0.80 pt) PASS
  microgravity flow penalty eats into that offset at 0.2 m/s: offset 0.50 pt, LOC_ug 18.93% PASS
  60 kPa: ug sustains spread where 1g does not (band 18.42-19.22% O2); the observed 17% ug record stays a published miss PASS
  /api/flame: regime spherical, fate sustained spread, front 415.4%, 5 citations with URLs, 4 stated notes PASS
  flow band at 0.2 m/s ug -> 'low-flow' (streamer scale 0.8)                 PASS
  cool-flame phase: ug sub-LOC -> cool-flame phase possible (qualitative), sustained hot -> not indicated, 1g sub-LOC -> not indicated PASS

TEST 12 (mission scenarios + 1g delta + briefing, dossier §4.2.2)
  5 presets, every one carries provenance + context                          PASS
  Gateway µg/1g pair differs ONLY by gravity                                 PASS
  µg Gateway margin exceeds its 1g twin by 0.80 pt (0 < d < 1.5)             PASS
  delta wording: '1g riskier (material): -0.80 pt'                           PASS
  /api/missions: 5 scenarios, default compare gateway-orbital vs gateway-ground-eval PASS
  /api/report briefing: flame-regime + cool-flame + citation matrix sections present (§8-§11) PASS

RESULT: all checks PASS
```

**Unit suite:** 95 tests green (`py -m pytest backend/tests -q`), covering every figure above plus the material vocabulary, the derived thickness factors, the temperature term, API input validation, the completeness of the §4.7 limitation set, the question router (11 routed questions), the record taxonomy, the decision memo, the flame regime / crossover figures the 3D screen renders, and the mission flight scenarios with their engine-computed 1g deltas.

### 6.1 Finding from this regeneration, and its resolution

An earlier regeneration of this log surfaced an overclaim: the record nearest a *fire* query is `EXPATM-EVA-REF-01` — an atmosphere **specification** reference (34% O₂ / 56.5 kPa) that carries no combustion verdict. Ranking by condition-distance was behaving as specified and the exact-atmosphere match genuinely is the nearest record, but `/api/ask` presented its top five as "key supporting experiments", which reads as combustion evidence.

**Resolved in this build, and asserted in the log below.** The taxonomy in `backend/engine/records.py` classifies every record as `experiment`, `historical` or `specification` from its own fields. `/api/ask` cites only controlled experiments as supporting evidence and returns the others under `context_citations` with their kind, and `/api/experiments` labels every row. Test 10 in §6 verifies that the specification record is still the nearest record overall *and* that it is not cited as evidence — the ranking is unchanged, only the claim made about it is now correct. The record was found by the regeneration script, which is the point of keeping the script.

---

## 7. Data Provenance Table

| # | Claim used by FLARE | Source | Verification |
|---|---|---|---|
| 1 | Exploration Atmosphere = 8.2 psia / 34% O₂ (Artemis target, enables rapid EVA prebreathe) | NTRS 20260002050 (ICES-2026-324); Kluis & Loeppky 2021 (PMC8594431) | ✅ verified |
| 2 | µg spread sustained ≈17% O₂ @ 60 kPa (vs 18% @ 1g) | Link et al. 2018, PMC5760683 | ✅ verified |
| 3 | Spread observed @ 19.8% O₂, 60 kPa, 12.7 mm PMMA, µg | UC Berkeley / SoFIE reporting, Dec 2024 | ✅ verified |
| 4 | LOC decreases with increasing total pressure | NASA-STD-6001 methodology; Konno 2023; He 2021; Constellation-era LOC studies | ✅ verified |
| 5 | Lunar/Mars minimum O₂ for spread ≈ µg value | Ruff, NIST r0200471 | ✅ verified |
| 6 | BASS-II test variables: ambient O₂, flow velocity, fuel type/thickness/geometry; HRR < 100 W; equivalence ratio ≈1.3 | NTRS 20210011385 (BASS-II Summary Report, public TM) | ✅ verified — content read via NTRS API |
| 7 | SoFIE-MIST varies O₂, pressure, flow for ignition/extinction studies | NASA Science SoFIE-MIST pages | ✅ verified |
| 8 | Apollo 1: 16.7 psia 100% O₂ cabin; flash fire at 6:31 p.m., Jan 27 1967; spread "within seconds" | NASA History "55 Years Ago: The Apollo 1 Fire"; Smithsonian Air & Space | ✅ verified — **the phrase "37 seconds" is NOT verifiable and is excluded** |
| 9 | NTRS API programmatic access (citation + search) | live HTTP tests, §6 Test 7 | ✅ executed |
| 10 | Competitive gap (no registered team computes a flammability boundary or backtests) | Space Apps 2026 registered teams: μFlame, Flame Vector, Firestorm, DataMents, et al. | ✅ scanned |

**Primary experiment targets for the curated database (60–120 records):** Saffire I–IV · BASS / BASS-II · SoFIE-MIST · FLEX · ACME/CSE · Constellation-era LOC threshold tables · Ivanov 1999 (NTRS 20000024924) LOC tables. Each record hand-verified against its NTRS page; 20-record seed ships in this repository.

---

## 8. Model Governance

- The engine is pure, deterministic, and unit-tested (`backend/tests/`). Local command: `py -m pytest backend/tests -q` (95 tests). The same suite runs in CI on every push (`.github/workflows/ci.yml`).
- **No language model is called in this build.** Answers are composed deterministically from engine outputs and database records; there is no LLM client and no API key is read anywhere in the backend. Every citation ID is verified against the database before display, and any ID not present is caught and flagged rather than shown (§6 Test 6). An LLM narration layer over the same engine-grounded payload is declared as future work (F4) rather than implied.
- Known-limitations list (§4.7) ships in the product UI ("Methodology" screen), served from `backend/app/methodology.py` at `/api/methodology` — stated openly, as in NASA engineering reports. A unit test asserts all eight limits are present (L8 records that the 3D Freefall Lab view is schematic, not a simulation), so the claim in this sentence cannot silently become false again.
- The §6 test log is reproduced by `backend/tools/reproduce_dossier_log.py` against the shipped code. Where an earlier published figure disagreed with this engine, the figure was corrected rather than the code (§6.1).
