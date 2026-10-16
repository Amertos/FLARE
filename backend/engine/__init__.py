"""FLARE engine package — pure science layer (no I/O). See docs/SCIENTIFIC-VALIDATION-DOSSIER.md."""
from .loc import (  # noqa: F401
    loc_percent,
    effective_loc,
    temperature_loc_offset_pct,
    LOC_A,
    LOC_B,
    TEMP_REFERENCE_C,
)
from .hazard import (  # noqa: F401
    hazard_vector,
    po2_psia,
    po2_normoxia_pct,
    MATERIAL_CLASSES,
    THICKNESS_FACTOR_BY_MATERIAL,
    thickness_factor_for,
    COMPONENT_KEYS,
    IGNITION_SPAN_PCT,
    EXTINCTION_SPAN_PCT,
)
from .epistemics import classify, coverage, evidence_pressure_range  # noqa: F401
from .similarity import similarity, rank_experiments  # noqa: F401
from .pareto import pareto_front, weighted_score  # noqa: F401
