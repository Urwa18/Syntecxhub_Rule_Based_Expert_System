"""Unit tests for the forward-chaining expert-system engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.facts import FactsBase, normalize_fact
from engine.inference import ForwardChainingEngine
from engine.logger import InferenceLog
from engine.rules import Rule, RuleBase, RuleValidationError


def tiny_rules() -> RuleBase:
    """A miniature 3-layer chain used by several tests."""
    return RuleBase(
        [
            Rule("R1", ["fever", "cough"], "respiratory_infection", "layer 1"),
            Rule("R2", ["respiratory_infection", "body_ache"], "flu_suspected", "layer 2"),
            Rule("R3", ["flu_suspected", "fatigue"], "rest_and_fluids", "layer 3"),
            Rule("R4", ["itchy_eyes"], "allergy", "unrelated"),
        ]
    )


def test_normalize_and_duplicate_facts() -> None:
    facts = FactsBase()
    assert facts.add("  Fever ", "user input") is True
    assert facts.has("FEVER")
    assert facts.add("fever", "user input") is False
    assert facts.all() == ["fever"]
    assert facts.origin("fever") == "user input"
    facts.clear()
    assert len(facts) == 0


def test_single_step_inference() -> None:
    engine = ForwardChainingEngine(tiny_rules())
    result = engine.run(["fever", "cough"])
    assert "respiratory_infection" in result.derived
    assert result.derived[0] == "respiratory_infection"
    assert len(result.log.entries) == 1
    assert result.log.entries[0].rule_id == "R1"
    assert result.log.complete is True


def test_multi_step_chaining() -> None:
    engine = ForwardChainingEngine(tiny_rules())
    result = engine.run(["fever", "cough", "body_ache", "fatigue"])
    assert result.derived == [
        "respiratory_infection",
        "flu_suspected",
        "rest_and_fluids",
    ]
    assert result.iterations == 3
    assert result.facts.has("rest_and_fluids")
    assert result.facts.origin("flu_suspected") == "inferred by rule R2"


def test_no_rule_applicable() -> None:
    engine = ForwardChainingEngine(tiny_rules())
    result = engine.run(["headache"])
    assert result.derived == []
    assert result.iterations == 0
    assert "No more rules applicable. Inference complete." in result.log.format()


def test_duplicate_facts_do_not_refire() -> None:
    engine = ForwardChainingEngine(tiny_rules())
    result = engine.run(["fever", "fever", "Cough", "cough"])
    assert result.facts.user_facts() == ["fever", "cough"]
    assert result.derived.count("respiratory_infection") == 1


def test_no_infinite_loop() -> None:
    """A cyclic pair would spin without the conclusion-already-present check / guard."""
    cyclic = RuleBase(
        [
            Rule("RA", ["spark"], "ping"),
            Rule("RB", ["ping"], "spark"),
        ]
    )
    engine = ForwardChainingEngine(cyclic, max_iterations=20)
    result = engine.run(["spark"])
    # First fire adds ping; spark is already present so RB never adds a new fact.
    assert "ping" in result.derived
    assert result.stopped_by_guard is False
    assert result.log.complete is True
    assert len(result.derived) == 1


def test_loop_guard_when_new_facts_keep_appearing() -> None:
    """Rules that mint a distinct conclusion each time would be unbounded.

    We simulate that with a custom RuleBase subclass... simpler: set max_iterations
    very low on a 3-step chain and confirm the guard trips before completion.
    """
    engine = ForwardChainingEngine(tiny_rules(), max_iterations=2)
    result = engine.run(["fever", "cough", "body_ache", "fatigue"])
    assert result.stopped_by_guard is True
    assert result.iterations == 2
    assert "infinite-loop guard" in result.log.format()


def test_log_order_correctness() -> None:
    engine = ForwardChainingEngine(tiny_rules())
    result = engine.run(["fever", "cough", "body_ache", "fatigue"])
    texts = [e.format() for e in result.log.entries]
    assert texts[0] == (
        "Iteration 1: R1 fired: fever AND cough => respiratory_infection"
    )
    assert texts[1] == (
        "Iteration 2: R2 fired: respiratory_infection AND body_ache => flu_suspected"
    )
    assert texts[2] == (
        "Iteration 3: R3 fired: flu_suspected AND fatigue => rest_and_fluids"
    )
    assert result.log.messages[-1] == "No more rules applicable. Inference complete."


def test_log_export(tmp_path: Path) -> None:
    log = InferenceLog()
    log.record(1, "R1", ["a", "b"], "c")
    log.mark_complete()
    txt = tmp_path / "log.txt"
    js = tmp_path / "log.json"
    log.export(txt, as_json=False)
    log.export(js, as_json=True)
    assert "R1 fired" in txt.read_text(encoding="utf-8")
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert payload["entries"][0]["conclusion"] == "c"


def test_rulebase_validation_and_runtime_add() -> None:
    with pytest.raises(RuleValidationError):
        RuleBase.from_data({"rules": [{"id": "X", "conditions": [], "conclusion": "y"}]})
    base = tiny_rules()
    base.add_rule(Rule("R9", ["x"], "y"))
    assert base.get("R9") is not None
    with pytest.raises(RuleValidationError):
        base.add_rule(Rule("R1", ["z"], "w"))


def test_medical_rules_three_step_flu() -> None:
    rules = RuleBase.from_json(ROOT / "data" / "rules.json")
    engine = ForwardChainingEngine(rules)
    result = engine.run(["fever", "cough", "body_ache", "fatigue"])
    assert "respiratory_infection" in result.derived
    assert "flu_suspected" in result.derived
    assert "rest_and_fluids" in result.derived
    # At least three inference steps.
    assert len(result.log.entries) >= 3
    ids = [e.rule_id for e in result.log.entries]
    assert ids.index("R1") < ids.index("R15") < ids.index("R24")
