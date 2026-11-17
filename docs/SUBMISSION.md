# FLARE — submission package

**Fire & Life Atmosphere Risk Explorer**
NASA Space Apps Challenge · challenge: *"Flame in Freefall"* — making fire safety visible for space missions.

**One line:** give FLARE any cabin atmosphere (pressure, O₂, gravity, airflow, temperature, material) and it shows what NASA's microgravity combustion record implies about fire spread and crew physiology, how confident each statement is, and — visibly — where the experimental evidence ends.

---

## 1. The problem, stated the way an engineer would

An atmosphere is a two-sided design decision:

- **Crew side.** Oxygen partial pressure (pO₂) determines hypoxia and oxygen-toxicity risk. NASA's Exploration Atmosphere (8.2 psia / 34% O₂) exists to make rapid EVA possible without a long prebreathe.
- **Fire side.** Flammability is governed by the *molar oxygen concentration* against the limiting oxygen concentration (LOC) boundary — not by pO₂.

Those two axes do not move together. **10.0 psia / 30% O₂ and 7.5 psia / 40% O₂ deliver exactly the same pO₂ (3.00 psia) — and different fire behaviour.** Every mission architect trading pressure against oxygen is trading on that gap, usually without a tool that shows where the data underneath the answer stops.

FLARE is that tool. It is deliberately a *decision-support* instrument, not a risk calculator and not a control system.

## 2. What it does (eight screens, all live)

| Screen | What a reviewer can do |
|---|---|
| **Trade Space** | Pressure × O₂ map of ignition tendency with the LOC boundary (white line), the crew-safe pO₂ band, and the region outside NASA data coverage **hatched, never coloured**. Click anywhere to move the atmosphere. |
| **Countermoves** | Four ranked, engine-computed fire-safety levers for the current atmosphere — cool the cabin, substitute a lower-representative-risk material class, reduce microgravity airflow, trade O₂ down to the crew-band floor. Every lever reports its own before/after hazard vector from the same engine as the map, names the dossier-backed quantity behind its effect, and a lever the model cannot support in this regime is shown not-applicable **with the reason**, never as a zero-delta recommendation. |
| **Design Search** | The inverse of the map: for each cabin pressure, the O₂ fraction the crew's pO₂ floor forces, the effective boundary at that pressure, and whether a breathable mix can sit below it. The two curves are solved in closed form, so the crossing pressure is a number, not a drag of the eye — at 8.2 psia the crew floor is 29.3% O₂ against an 18.9% boundary, and the widest calibrated breathable fire-safe window is 0.92 O₂ points at 14.6 psia, narrower than the model's own uncertainty. |
| **Candidate atmospheres** | Six-year-old spreadsheet thinking, replaced: candidate atmospheres scored on fire risk vs EVA benefit, with the Pareto frontier marked and a weight slider that changes which option leads. Includes a deliberate control pair (12 psia at 21% vs 28% O₂) where one option buys *no* EVA benefit and is shown as dominated. |
| **Evidence** | The curated NASA record nearest the current state, each row labelled `experiment` / `historical` / `specification`, each linking to its real source (NTRS / PMC / journal / NASA History). |
| **Ask FLARE** | Type a question; an explicit keyword router picks the intent (boundary, hazard components, crew physiology, evidence, comparison, material, flow, temperature, pressure, validation, what-if, inverse design) and the answer is composed from engine outputs. Citation chips jump straight to the cited record. Out-of-scope questions are declared out of scope rather than narrated. |
| **Validation** | Leave-one-out backtest of the engine against NASA's own experiments — including the four misses (three of them the curve's own fit anchors), each with an explanation. |
| **Methodology** | The known-limitations list, what is deliberately *not* built, the model-governance rules and the provenance table — served by the engine (`/api/methodology`), so the product and the written record cannot drift apart. |
| **Export memo** | Any atmosphere becomes a one-page Markdown decision memo: state, evidence label, hazard vector, boundary derivation, crew side, cited experiments with sources, sensitivity sweep, backtest summary, limitations, sources. |

## 3. What makes it different (the part judges can check in code)

1. **No single fire-risk number.** The output is a 5-component Fire Hazard Vector; persistence and heat release are stated to be *derived from* spread rather than pretending to be independent measurements.
2. **Every quantitative output carries an evidence label** — OBSERVED / INTERPOLATED / EXTRAPOLATED / INSUFFICIENT — computed from the database at request time, never hand-assigned.
3. **The boundary is drawn only where the curve was calibrated.** Outside the fitted pressure envelope the map is hatched and labelled. No pixel implies a measurement NASA did not make.
4. **No language model is called anywhere in this build.** Answers are composed deterministically and every citation ID is verified against the database in code; a fabricated ID would be caught and flagged, not displayed. The router returns its own decision (`intent`, matched keywords, confidence) with the answer.
5. **Fire evidence is separated from context.** A record that carries no combustion verdict (the Exploration Atmosphere specification, the Apollo 1 historical reference) can never be presented as "supporting evidence" — the regression that produced that overclaim is written up in the dossier (§6.1) and asserted by a test.
6. **Our failures are published.** The backtest table shows 14/18 overall (77.8%) and 93.3% on non-anchor records, with per-miss explanations, rather than a headline accuracy figure with a hidden denominator.
7. **The design question is answered, not just plotted.** Design Search turns the two constraints into one crossing pressure: below it, the oxygen a crew needs is itself above the boundary, so no breathable mix is fire-safe. The result is uncomfortable for the Exploration Atmosphere — at 8.2 psia the crew floor sits 10.3 O₂ points above the boundary, and the widest fire-safe breathable window inside the calibrated data is 0.92 point, inside the fit's stated ±1.5 pt uncertainty. The product reports that instead of implying a safe atmosphere exists.

### 3.1 The screen that answers the challenge in one look

The challenge is called *Flame in Freefall*, so the product has a screen that shows exactly that. **Freefall Lab** pulls its whole state from `/api/flame`:

- a rotatable 3D surface of the ignition index over the whole P × O₂ space, with the LOC boundary as a white ridge and a hatched vertical face where the fitted envelope ends (the same rule as the 2D map, made impossible to miss at an angle);
- a flame chamber where the fire is **spherical in microgravity and a teardrop at 1g**, bluer where the published microgravity flame is soot-poor, and which **stalls and extinguishes** whenever the state sits below the effective boundary — reproducing what BASS-II-04 actually did on orbit;
- a margin chart where the microgravity and 1g curves **cross**: at 21% O₂ the 1g flame spreads faster, below ~19% the microgravity flame does. That crossover is the engine's own 0.8 pt gravity offset, not a drawn curve, and it is the single most counter-intuitive fact in the challenge brief.

Each of those figures sits next to the citation list the API returned with it, and the screen carries its own "what this does not claim" block. A judge can press `?no3d=1` and get the identical numbers with no WebGL.

## 4. How it is verified (minutes, no account needed)

```bash
py -m pip install -r backend/requirements.txt
py -m pytest backend/tests -q                     # 128 tests, all green
py -m backend.tools.reproduce_dossier_log         # exits non-zero if the published log drifts from the code
py -m uvicorn backend.app.main:app --port 8787    # API

cd frontend && npm install && npm run dev         # UI on http://127.0.0.1:5173
```

The published test log in [SCIENTIFIC-VALIDATION-DOSSIER.md](SCIENTIFIC-VALIDATION-DOSSIER.md) §6 is *verbatim stdout* of the shipped engine, regenerated by the committed script above — the same script runs in CI, so documentation drift fails the build. CI also runs the frontend type-check + build.

Useful URLs while the API is up:

| URL | What it returns |
|---|---|
| `/api/scenario` | hazard vector + evidence label + coverage for one state |
| `/api/tradespace` | the P × O₂ grid, LOC boundary points and the hatching envelope |
| `/api/flame` | flame regime, fire-front fate, relative front rate, µg-vs-1g crossover, and the citations for every visual claim |
| `/api/experiments` | the ranked record set with each row's kind |
| `/api/ask` (POST) | routed, engine-grounded answer with verified citations |
| `/api/design-search` | per-pressure crew floor vs boundary, closed-form crossing and the breathable fire-safe window |
| `/api/pareto` | candidate set, frontier and weighted ranking |
| `/api/validate` | the leave-one-out backtest |
| `/api/report` | the Markdown decision memo (`&download=true` attaches it) |
| `/api/methodology` | limitations, unbuilt work, governance, provenance |

The UI is also deep-linkable and shareable — the address bar always carries the state, e.g.
`http://127.0.0.1:5173/?p=8.2&o2=34&g=microgravity&f=0.2&t=22&m=polymer&tab=trade`.

## 5. Judging criteria — where to look

| Criterion | Evidence in this repository |
|---|---|
| **Impact** | The trade the tool makes visible is the one Artemis-era atmosphere design actually faces (Exploration Atmosphere ↔ fire risk). The memo export drops a decision artifact into a real review folder. Limitations are stated instead of implied away, which is what makes a numbers tool usable in engineering review. |
| **Creativity** | Hatching evidence absence onto the map itself; a Fire Hazard Vector instead of one risk number; a Pareto trade instead of a recommended atmosphere; a **3D Freefall Lab** whose flame is driven by the same boundary the rest of the tool uses, and which self-extinguishes on camera where the model says it must; an engine-served methodology page; a deterministic question router instead of a chatbot that cannot be checked. |
| **Validity** | LOC(P) = 15.88 + 200.5/P fitted to three 1g anchors (max error 0.25 pt), gravity/flow/thickness modifiers with cited direction of effect and magnitudes declared as fit choices, leave-one-out backtest with published misses, 95 unit tests, a dossier whose test log is regenerated from the shipped code, and a 3D figure whose every visual claim carries a source returned by the API beside it. |
| **Relevance** | The challenge asks for fire behaviour in microgravity made visible and comparable to 1g. FLARE's boundary is drawn for the microgravity regime, shows the µg-vs-1g offset explicitly, and refuses to colour regions where no microgravity data exists. |
| **Presentation** | Live UI with a 3D screen a projector can show, PNG export of the terrain, shareable links, one-page memo export, 4-minute demo script, dossier, security notes, and a CI pipeline that keeps all of it honest. |

## 6. What FLARE explicitly does *not* claim

- Not an absolute risk assessor: the vector compares atmospheres relative to one another.
- Not a chemistry model of a material — material *classes* with a representative thickness factor (L1).
- No smoldering, no radiation–convection coupling modelled (L3).
- The crew-safe band (pO₂ ∈ [2.4, 3.4] psia) is this project's conservative planning construct, not a NASA requirement (L6).
- The Freefall Lab is a **schematic of published regimes**, not a CFD solution: shape, colour and front geometry are not solved fields, and front speed is relative to the Saffire-I anchor, never m/s (L8, L4).
- The shipped database is 20 curated, source-linked records out of a 60–120 target; every label, coverage value and backtest figure will move when it grows (L7).
- No language model is called, so answers cannot paraphrase outside the engine's evidence.

Full list: `py -m uvicorn … ` → **Methodology** screen, or `/api/methodology`.

## 7. Roadmap

1. **Database growth** — NTRS/SoFIE/Saffire ingestion toward 60–120 records; every record hand-checked against its NTRS page.
2. **Smoldering mode** — a distinct regime, deliberately absent today.
3. **Multi-module Fire Danger Index** — only if it can be done without collapsing risk into one number.
4. **Optional LLM narration** — permitted *above* this engine (it would receive the engine payload and verified citation set), never inside it.

## 8. Submission checklist (fill in at submission time)

- [ ] Team name / members and the project URL
- [ ] Demo video link — script in [demo-script.md](demo-script.md)
- [ ] Repository link (this repo) — public
- [ ] Challenge selected: *Flame in Freefall*
- [ ] Optional: recorded live-demo backup for venue network failure (the app runs entirely offline: no language model, no outbound call at request time)
