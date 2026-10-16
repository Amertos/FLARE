"""FLARE engine package — pure science layer (no I/O). See docs/SCIENTIFIC-VALIDATION-DOSSIER.md."""
from .loc import loc_percent, effective_loc, LOC_A, LOC_B  # noqa: F401
from .hazard import hazard_vector, po2_psia, po2_normoxia_pct  # noqa: F401
from .epistemics import classify, coverage  # noqa: F401
from .similarity import similarity, rank_experiments  # noqa: F401
from .pareto import pareto_front, weighted_score  # noqa: F401
