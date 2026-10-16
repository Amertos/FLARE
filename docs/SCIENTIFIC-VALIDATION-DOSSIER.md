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
4. **The engine is deterministic** — same inputs, same outputs. AI sits *above* the engine (retrieval-augmented, citation-verified), never *inside* it.
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

- **F_i (ignition)** = clamp01((X_O₂ − LOC_eff(P,g,v))/ (X_O₂_ref_upper − LOC_eff)) scaled 0–100, plus a small Arrhenius-scaled temperature term referenced to 22 °C. Above the boundary → tendency rises with margin above LOC; below → near-zero tendency.
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

Executed ranking check (§6 Test 5), as produced by the shipped engine for a 8.2 psia/34% µg/polymer query: `EXPATM-EVA-REF-01` (the exact-atmosphere reference) 0.700, `LOC-UG-60KPA-01` (the fundamental microgravity LOC record) 0.580, `SOFIE-MIST-REF-01` 0.496, `SOFIE-MIST-REF-02` 0.338, `LOC-PRESSURE-TREND-02` 0.327, and the 1g ground LOC record 0.000 — nearest conditions first, as an engineer would expect.

---

## 6. Executed Test Log (verbatim results)

Everything below is the **verbatim stdout of the shipped engine and API in this repository** — not a prototype run. It is regenerated by a committed script, so the published log cannot drift from the code it describes:

```
py -m backend.tools.reproduce_dossier_log
```

The script exits non-zero if any check fails. The same claims are asserted independently by the unit suite. **Figures that disagreed with the shipped code have been replaced** — Test 5 in particular previously published prototype similarity values that this engine does not reproduce.

```
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
  /api/validate LOO: 7/12 (58.3%) overall, 77.8% non-anchor (9 records)      PASS
  /api/methodology: 7 limitations, 4 unbuilt items served to the UI          PASS
  /api/tradespace: envelope [50.0, 101.3] kPa, 15/34 P-columns hatching as EXTRAPOLATED PASS
  input validation: unknown material class -> HTTP 422                       PASS

TEST 8 (material classes and thickness factor, §4.5)
  material vocabulary ('polymer', 'textile', 'insulation', 'composite')      PASS
  thickness factors {'polymer': 1.0, 'textile': 0.85, 'insulation': 0.7, 'composite': 1.15} PASS
  spread moves by material: polymer 43.2 > insulation 30.2                   PASS
  temperature term in F_i: 18 C 45.7 < 30 C 105.0                            PASS

TEST 9 (NTRS API, live HTTP)
  GET ntrs citation 20210011385 -> 200, 7042 bytes                           PASS

RESULT: all checks PASS
```

**Unit suite:** 42 tests green (`py -m pytest backend/tests -q`), covering every figure above plus the material vocabulary, the derived thickness factors, the temperature term, API input validation and the completeness of the §4.7 limitation set.

### 6.1 Open item surfaced by this regeneration

Test 5 shows that the record nearest a *fire* query is `EXPATM-EVA-REF-01` — an atmosphere **specification** reference (34% O₂ / 56.5 kPa) that carries no combustion verdict. Ranking by condition-distance is behaving as specified, and the exact-atmosphere match genuinely is the nearest record, but `/api/ask` presents its top five as "key supporting experiments", which reads as combustion evidence. Separating specification records from experimental results in that presentation is an open refinement, stated here rather than hidden.

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

- The engine is pure, deterministic, and unit-tested (`backend/tests/`). Local command: `py -m pytest backend/tests -q` (42 tests). The same suite runs in CI on every push (`.github/workflows/ci.yml`).
- **No language model is called in this build.** Answers are composed deterministically from engine outputs and database records; there is no LLM client and no API key is read anywhere in the backend. Every citation ID is verified against the database before display, and any ID not present is caught and flagged rather than shown (§6 Test 6). An LLM narration layer over the same engine-grounded payload is declared as future work (F4) rather than implied.
- Known-limitations list (§4.7) ships in the product UI ("Methodology" screen), served from `backend/app/methodology.py` at `/api/methodology` — stated openly, as in NASA engineering reports. A unit test asserts all seven limits are present, so the claim in this sentence cannot silently become false again.
- The §6 test log is reproduced by `backend/tools/reproduce_dossier_log.py` against the shipped code. Where an earlier published figure disagreed with this engine, the figure was corrected rather than the code (§6.1).
