"""Citation verification: AI citations must reference real experiment IDs.

Validated in dossier §6 Test 6: fabricated IDs are caught and flagged,
never shown to the user.
"""
from __future__ import annotations


def verify_citations(cited_ids: list[str], experiment_ids: set[str]) -> dict:
    valid = [c for c in cited_ids if c in experiment_ids]
    fabricated = [c for c in cited_ids if c not in experiment_ids]
    return {
        "valid": valid,
        "fabricated": fabricated,
        "ok": len(fabricated) == 0,
    }
