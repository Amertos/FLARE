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
from .backtest import leave_one_out, FIT_ANCHOR_IDS  # noqa: F401
from .records import (  # noqa: F401
    KIND_EXPERIMENT,
    KIND_LABELS,
    annotate,
    partition,
    record_kind,
)
from .intents import Atmosphere, compose, route  # noqa: F401
from .design import (  # noqa: F401
    crew_floor_o2_pct,
    crossover_pressure_psia,
    design_search_payload,
)
