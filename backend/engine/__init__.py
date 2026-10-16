"""FLARE engine package — pure science layer (no I/O). See docs/SCIENTIFIC-VALIDATION-DOSSIER.md."""
from .loc import loc_percent, effective_loc, LOC_A, LOC_B  # noqa: F401
from .hazard import (  # noqa: F401
    hazard_vector,
    po2_psia,
    po2_normoxia_pct,
    MATERIAL_CLASSES,
    THICKNESS_FACTOR_BY_MATERIAL,
    thickness_factor_for,
)
from .epistemics import classify, coverage, evidence_pressure_range  # noqa: F401
from .similarity import similarity, rank_experiments  # noqa: F401
from .pareto import pareto_front, weighted_score  # noqa: F401
