"""Tests for the question router, the record taxonomy and the decision memo.

These assert the two claims the product makes about /api/ask:

1. the typed question actually steers the answer (the router is explicit and
   the composition depends on it), and
2. only controlled combustion experiments are ever cited as supporting fire
   evidence — specification and historical records are reported as context
   (this is the dossier §6.1 open item, closed here).

Run: py -m pytest backend/tests -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.data import load_experiments
from backend.engine.backtest import leave_one_out
from backend.engine.intents import Atmosphere, compose, route
from backend.engine.records import (
    KIND_EXPERIMENT,
    KIND_HISTORICAL,
    KIND_SPECIFICATION,
    KIND_UNSPECIFIED,
    partition,
    record_kind,
)

client = TestClient(app)


# ---------- Routing ----------

@pytest.mark.parametrize("question,intent", [
    ("Where is the limiting oxygen concentration boundary?", "loc_boundary"),
    ("Why is 34% O2 riskier than 28% at the same pressure?", "comparison"),
    ("Is this atmosphere safe for the crew?", "crew_physiology"),
    ("Which experiments support this atmosphere?", "evidence_coverage"),
    ("What if airflow drops to 0.05 m/s?", "flow_effect"),
    ("How does the material class change spread?", "material_effect"),
    ("What does a warmer cabin do to the boundary?", "temperature_effect"),
    ("What pressure makes this atmosphere non-flammable?", "pressure_effect"),
    ("How accurate is the model on held-out experiments?", "validation"),
    ("What happens if O2 increases by 2%?", "what_if"),
    ("Which hazard component is highest?", "hazard_components"),
])
def test_router_sends_questions_to_the_expected_intent(question, intent):
    assert route(question)[0] == intent


def test_router_reports_its_confidence():
    intent, matched, share = route("What if airflow drops to 0.05 m/s?")
    assert intent == "flow_effect"
    assert matched and 0.0 < share <= 1.0
    # An unrecognised question is honestly reported as an unspecific route
    # rather than given a confident label.
    assert route("hello there")[0] == "general"


def test_answer_depends_on_the_question():
    atm = Atmosphere(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer")
    exps = load_experiments()
    crew = compose("Is this safe for the crew?", atm, exps)
    flow = compose("What if airflow drops to 0.05 m/s?", atm, exps)
    assert crew["answer"] != flow["answer"]
    assert crew["intent"] != flow["intent"]
    assert "pO2" in crew["answer"]
    assert "flow" in flow["answer"].lower()


def test_out_of_scope_question_is_declared_not_answered():
    atm = Atmosphere(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer")
    result = compose("Write me a poem about Mars", atm, load_experiments())
    assert result["intent"] == "out_of_scope"
    assert "outside what this engine models" in result["answer"]


# ---------- Record taxonomy (dossier §6.1) ----------

def test_every_shipped_record_has_a_known_kind():
    kinds = {record_kind(e) for e in load_experiments()}
    assert KIND_UNSPECIFIED not in kinds, (
        "a record's outcome_type is not covered by the taxonomy in "
        "backend/engine/records.py — add it deliberately, do not let it land "
        "in the evidence pool by default"
    )
    assert kinds <= {KIND_EXPERIMENT, KIND_HISTORICAL, KIND_SPECIFICATION}


def test_apollo_1_is_historical_not_experimental_evidence():
    exps = load_experiments()
    apollo = next(e for e in exps if e["experiment_id"] == "APOLLO1-CABIN-REF-01")
    assert record_kind(apollo) == KIND_HISTORICAL


def test_exploration_atmosphere_reference_is_specification_not_evidence():
    exps = load_experiments()
    ref = next(e for e in exps if e["experiment_id"] == "EXPATM-EVA-REF-01")
    assert record_kind(ref) == KIND_SPECIFICATION


def test_partition_keeps_ranking_order():
    ranked = [{"experiment_id": "a", "outcome_type": "flame_spread"},
              {"experiment_id": "b", "outcome_type": "crew_reference"},
              {"experiment_id": "c", "outcome_type": "flammability_limit"}]
    evidence, context = partition(ranked)
    assert [e["experiment_id"] for e in evidence] == ["a", "c"]
    assert [e["experiment_id"] for e in context] == ["b"]


def test_ask_never_cites_a_context_record_as_evidence():
    exps = load_experiments()
    atm = Atmosphere(8.2, 34.0, "microgravity", 0.2, 22.0, "polymer")
    result = compose("Which experiments support this atmosphere?", atm, exps)
    kinds = {e["experiment_id"]: record_kind(e) for e in exps}
    assert all(kinds[c] == KIND_EXPERIMENT for c in result["citations"])
    # The nearest record on the Exploration Atmosphere is the specification
    # reference; it must appear as context, never as supporting evidence.
    assert "EXPATM-EVA-REF-01" in result["context_citations"]
    assert "EXPATM-EVA-REF-01" not in result["citations"]


# ---------- API payloads ----------

def test_experiments_endpoint_labels_record_kinds():
    r = client.get("/api/experiments", params={"pressure_psia": 8.2, "o2_pct": 34.0})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == body["evidence_count"] + body["context_count"]
    kinds = {e["record_kind"] for e in body["results"]}
    assert kinds <= {KIND_EXPERIMENT, KIND_HISTORICAL, KIND_SPECIFICATION}
    assert all(e.get("source_url") and e.get("source_id") for e in body["results"])


def test_ask_payload_exposes_the_routing_decision():
    r = client.post("/api/ask", json={
        "question": "What if airflow drops to 0.05 m/s?",
        "pressure_psia": 8.2, "o2_pct": 34.0, "gravity": "microgravity",
        "flow_ms": 0.2, "temperature_c": 22.0, "material_class": "polymer",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "flow_effect"
    assert body["intent_matched"]
    assert body["citation_check_ok"] is True
    assert body["fabricated_citations"] == []
    assert body["suggested_questions"]


def test_validate_endpoint_uses_the_engine_backtest():
    r = client.get("/api/validate")
    assert r.status_code == 200
    assert r.json() == leave_one_out(load_experiments())


def test_validate_numbers_are_the_published_ones():
    body = client.get("/api/validate").json()
    assert (body["correct"], body["total"]) == (7, 12)
    assert body["accuracy_non_anchor"] == pytest.approx(0.778, abs=0.001)


# ---------- Decision memo ----------

def test_report_is_a_complete_markdown_memo():
    r = client.get("/api/report", params={
        "pressure_psia": 8.2, "o2_pct": 34.0, "gravity": "microgravity",
        "flow_ms": 0.2, "temperature_c": 22.0, "material_class": "polymer"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    body = r.text
    for section in ("Atmosphere state", "Evidence status", "Fire Hazard Vector",
                    "Flammability boundary", "Crew side", "Supporting evidence",
                    "Sensitivity of this state", "Model confidence",
                    "Stated limitations", "Load-bearing sources"):
        assert section in body
    # Every limitation and provenance row the product claims to publish travels
    # with the memo, so a number cannot leave the tool without its caveats.
    assert "L7 — Seed database is a subset" in body
    assert "Exploration Atmosphere = 8.2 psia / 34% O2" in body
    assert "no operational command" in body


def test_report_download_sets_a_filename():
    r = client.get("/api/report", params={"download": "true"})
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["content-disposition"].endswith('.md"')


def test_report_marks_the_state_it_carries():
    r = client.get("/api/report", params={"o2_pct": 40.0, "pressure_psia": 7.5})
    assert "40" in r.text and "7.5" in r.text
    assert "Effective boundary" in r.text
