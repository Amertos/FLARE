"""Product-side statement of the model's limits, scope and provenance.

Single source for what the "Methodology" screen renders. Mirrors
docs/SCIENTIFIC-VALIDATION-DOSSIER.md §4.7 (validity limits), §7 (data
provenance) and §8 (model governance). The dossier claims this list ships in
the product UI; this module is what makes that true, and
backend/tests/test_engine.py asserts the §4.7 limits are all present so the
claim cannot silently drift again.

When the dossier changes, change this file in the same commit.
"""
from __future__ import annotations

# dossier §4.7 -- explicit validity limits, verbatim in substance.
LIMITATIONS: list[dict[str, str]] = [
    {
        "id": "L1",
        "title": "Material classes, not materials",
        "detail": (
            "The LOC boundary is a 2-parameter fit per material class. It is not a "
            "chemistry model of an individual material, and it does not resolve "
            "sample geometry within a class."
        ),
    },
    {
        "id": "L2",
        "title": "The boundary is drawn only where data exists",
        "detail": (
            "The flammability boundary is rendered only inside the experimental "
            "coverage envelope (50-101.3 kPa). Outside it the map shows a hatched "
            "\"EXTRAPOLATED - insufficient NASA data\" region instead of colour."
        ),
    },
    {
        "id": "L3",
        "title": "Radiation-convection coupling not modelled",
        "detail": (
            "v1 does not model radiation-convection coupling. Smoldering combustion "
            "is out of scope and is not predicted anywhere in the product."
        ),
    },
    {
        "id": "L4",
        "title": "Relative comparison, not absolute risk",
        "detail": (
            "The Fire Hazard Vector supports relative comparison of atmospheres. It "
            "is not an absolute risk assessor and must not be read as a "
            "certification of any atmosphere."
        ),
    },
    {
        "id": "L5",
        "title": "Semi-quantitative modifiers",
        "detail": (
            "Flow, gravity and thickness modifiers have cited direction of effect; "
            "their magnitudes are bounded fit choices stated in code "
            "(backend/engine/loc.py, backend/engine/hazard.py), not measurements."
        ),
    },
    {
        "id": "L6",
        "title": "Crew-safe band is a model construct",
        "detail": (
            "The crew-safe region is drawn from pO2 in [2.4, 3.4] psia (about "
            "78-110% of sea-level normoxia), a conservative planning band chosen by "
            "this project. It is not a NASA requirement. Pressure-reduction lower "
            "limits (PRLL) and oxygen-toxicity exposure limits are not modelled."
        ),
    },
    {
        "id": "L7",
        "title": "Seed database is a subset",
        "detail": (
            "The shipped curated database holds 20 NTRS-referenced records out of a "
            "target 60-120. Every label, coverage value and backtest figure in the "
            "product is computed from those 20 records and will change when the "
            "database grows."
        ),
    },
]

# Work that is explicitly NOT built. Stated here so the product does not imply
# capability it does not have (dossier §8 governance; implementation plan
# "Stretch (deferred)").
FUTURE_WORK: list[dict[str, str]] = [
    {
        "id": "F1",
        "title": "NTRS auto-ingestion",
        "detail": (
            "Programmatic ingestion of NTRS/SoFIE/Saffire records to grow the "
            "curated database from 20 to the 60-120 target and tighten the "
            "leave-one-out backtest."
        ),
    },
    {
        "id": "F2",
        "title": "Smoldering mode",
        "detail": (
            "Smoldering propagation is a distinct regime from flaming spread and is "
            "not modelled at all in v1."
        ),
    },
    {
        "id": "F3",
        "title": "Multi-module Fire Danger Index",
        "detail": (
            "A single aggregated index across modules. Deliberately not built: "
            "design rule 1 forbids collapsing risk into one number."
        ),
    },
    {
        "id": "F4",
        "title": "LLM-augmented narration",
        "detail": (
            "Answers are composed deterministically from the engine and the "
            "database. An optional LLM narration layer is planned but is NOT "
            "implemented in this build; no model is called at any point."
        ),
    },
]

GOVERNANCE: list[str] = [
    "The engine is pure, deterministic and unit-tested; the same inputs always "
    "produce the same outputs.",
    "No quantitative claim is produced by the AI layer. Every number shown comes "
    "from the engine.",
    "Every cited experiment ID is verified against the database in code before "
    "display; fabricated citations are caught and flagged, never shown.",
    "Every experiment record links to its NASA source (NTRS ID + URL).",
    "Every quantitative output carries an evidence label computed from the "
    "database at request time, never assigned by hand.",
]

DATA_PROVENANCE: list[dict[str, str]] = [
    {"claim": "Exploration Atmosphere = 8.2 psia / 34% O2",
     "source": "NTRS 20260002050 (ICES-2026-324); Kluis & Loeppky 2021, PMC8594431"},
    {"claim": "Microgravity sustains spread near 17% O2 at ~60 kPa",
     "source": "Link et al. 2018, PMC5760683"},
    {"claim": "Spread observed at 19.8% O2, 60 kPa, PMMA, microgravity",
     "source": "UC Berkeley / SoFIE reporting, Dec 2024"},
    {"claim": "LOC decreases as total pressure increases",
     "source": "NASA-STD-6001 lineage; Konno 2023; He 2021"},
    {"claim": "Lunar/Mars minimum O2 for spread is near the microgravity value",
     "source": "Ruff, NIST r0200471"},
    {"claim": "BASS-II test variables and sub-100 W heat release frame",
     "source": "NTRS 20210011385 (BASS-II Summary Report)"},
    {"claim": "Apollo 1 cabin: 16.7 psia, 100% O2; flash fire 27 Jan 1967",
     "source": "NASA History; Smithsonian Air & Space"},
]


def methodology_payload() -> dict:
    """Everything the Methodology screen renders."""
    return {
        "limitations": LIMITATIONS,
        "future_work": FUTURE_WORK,
        "governance": GOVERNANCE,
        "data_provenance": DATA_PROVENANCE,
        "dossier_refs": [
            "docs/SCIENTIFIC-VALIDATION-DOSSIER.md §4.7",
            "docs/SCIENTIFIC-VALIDATION-DOSSIER.md §7",
            "docs/SCIENTIFIC-VALIDATION-DOSSIER.md §8",
        ],
    }
