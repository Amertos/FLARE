"""Loaders for the curated experiment database."""
from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "experiments.json"


def load_experiments() -> list[dict]:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def experiment_ids(experiments: list[dict] | None = None) -> set[str]:
    return {e["experiment_id"] for e in (experiments or load_experiments())}
