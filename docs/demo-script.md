# FLARE — 4-Minute Demo Script

> Total: 4 minutes. Rehearse 5×. Backup video recorded separately. The app runs fully
> offline (no language model, no outbound call at request time) if venue Wi-Fi dies.

**Before you start:** backend on `http://127.0.0.1:8787`, UI on `http://127.0.0.1:5173`,
browser at ~1440 px wide, and the address bar visible — every state in this demo is a
link you can hand to a judge.

---

1. **Apollo 1 hook (25s).** Select the 🕯️ **Apollo 1 (1967)** preset — 16.7 psia, 100% O₂.
   Point at the map: *the entire trade space sits deep inside the fire zone, and the
   pressure axis is hatched — the curve was never calibrated out there, so FLARE refuses to
   colour it.* "On January 27, 1967, a flash fire broke out in a cabin at 16.7 psia of pure
   oxygen, and spread within seconds. That atmosphere had an oxygen partial pressure 541% of
   sea-level normoxia. FLARE computes that — it doesn't guess it."

2. **The real trade (40s).** Switch to 🔴 **Mars transit 8.2 / 34** — NASA's Exploration
   Atmosphere. Show the Fire Hazard Vector and the crew-safe band. Then drag to 7.5 psia /
   40% O₂ and back to 10.0 / 30%: *same crew pO₂ (3.00 psia) — different fire vector.*
   "Two crew-equivalent atmospheres are not fire-equivalent. That is the compromise every
   mission designer faces, and it is invisible in a spreadsheet."

3. **Freefall Lab (40s).** Click the orange banner — *"What does a fire actually do in this
   atmosphere?"* — or **🔥 Freefall Lab**. Let the terrain rotate once: *"this is the whole
   design space at once — the white ridge is the flammability boundary, and that hatched wall
   is where our calibration ends. From above it is a map; from here you can see it is a cliff."*
   Then press **Ignite**: the flame is round and blue in microgravity. Switch gravity to
   **earth**: it snaps to a teardrop. Switch to **17% O₂ at 0.1 m/s** and ignite again — the
   front stalls and dies. "That is BASS-II-04, the experiment where a microgravity flame
   self-extinguished on the ISS. Our engine predicts it from the boundary, not from the video."
   Finally point at the crossover curve: *"and 'space burns slower' is false — the curves
   cross. Above ~19% oxygen Earth burns faster; below it, microgravity does. NASA published
   that in 2018; our gravity offset reproduces it."* Every figure on this screen carries its
   source beneath it.

4. **Where the data ends (30s).** Drag O₂ to 38%: the evidence label flips, coverage drops,
   and the map's hatched bands return. "We show you where NASA's data ends. We don't colour
   pixels where NASA has no measurements — and the known-limitations list is served by the
   engine, so the interface cannot claim more than the model does."

5. **Ask FLARE (45s).** Click **Ask FLARE**, press the starter
   *"Which experiments support this atmosphere?"* Point at the routing line:
   `route: evidence_coverage · matched "which experiments" · confidence 0.85`. "The question
   steers the answer — deterministically. No language model is called; the router is
   inspectable." Then click the **📄 LOC-UG-60KPA-01** chip: the app jumps to Evidence with
   that record open and highlighted. Note the *context* chips below it: the Exploration
   Atmosphere specification and the Apollo 1 historical reference, labelled as carrying no
   combustion verdict, because we do not present a specification as fire evidence.

6. **The Pareto close (30s).** Open **Candidate atmospheres**. Move the fire-safety weight
   slider: the leader changes hands and the frontier stays marked. Point at the control pair —
   12 psia / 21% vs 12 psia / 28% O₂: *same pressure, so zero EVA benefit from the extra
   oxygen, and it is shown as dominated.* "FLARE never says which atmosphere is best. It
   shows the trade."

7. **Graded, not claimed (20s).** Open **Validation**. "Our engine is graded against NASA's
   own held-out experiments — 7 of 12, 77.8% excluding the curve's own fit anchors, with every
   miss explained. We publish our accuracy and our failures."

8. **The artifact (10s).** Click **⬇ Export memo**. Open the downloaded file: state, evidence
   label, hazard vector, boundary derivation, crew side, cited sources, sensitivity sweep,
   backtest, limitations — one page a reviewer can file. "Every number, and every caveat about
   that number, in one artifact."

---

### Fallbacks

- **Projector or laptop without WebGL:** add `?no3d=1` to the URL. The Freefall Lab keeps every
  number and the crossover chart (plain SVG) and says so on screen; nothing you claim depends on
  the geometry being rendered. The terrain also exports as a PNG if you want a still.

- **UI fails to load:** the API alone tells the story — `/docs` (FastAPI), `GET /api/report`
  for the memo, `GET /api/validate` for the backtest.
- **Judge asks "is it AI?":** answer directly — no model is called; the engine is
  deterministic and the question router is explicit, because an unverifiable narration layer
  over safety numbers is worse than no narration layer.
- **Judge asks about data:** 20 curated, source-linked records shipped of a 60–120 target;
  every label and backtest figure is computed from what is actually there (limitation L7).
