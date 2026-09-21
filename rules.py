"""If-then rules and a loadable rule base."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from engine.facts import FactsBase, normalize_fact


class RuleValidationError(ValueError):
    """Raised when a rule or rules file is malformed."""


@dataclass
class Rule:
    """A production rule: IF all conditions THEN conclusion (AND logic)."""

    id: str
    conditions: List[str]
    conclusion: str
    description: str = ""

    def __post_init__(self) -> None:
        self.id = str(self.id).strip()
        self.conditions = [normalize_fact(c) for c in self.conditions if str(c).strip()]
        self.conclusion = normalize_fact(self.conclusion)
        self.description = (self.description or "").strip()
        if not self.id:
            raise RuleValidationError("Rule id cannot be empty.")
        if not self.conditions:
            raise RuleValidationError(f"Rule {self.id} must have at least one condition.")
        if not self.conclusion:
            raise RuleValidationError(f"Rule {self.id} must have a conclusion.")

    def is_applicable(self, facts: FactsBase) -> bool:
        """True when every condition is known and the conclusion is not."""
        if facts.has(self.conclusion):
            return False
        return all(facts.has(c) for c in self.conditions)

    def missing_conditions(self, facts: FactsBase) -> List[str]:
        return [c for c in self.conditions if not facts.has(c)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conditions": self.conditions,
            "conclusion": self.conclusion,
            "description": self.description,
        }

    def pretty(self) -> str:
        joined = " AND ".join(self.conditions)
        return f"{self.id}: IF {joined} THEN {self.conclusion}"


class RuleBase:
    """Collection of rules, typically loaded from ``data/rules.json``."""

    def __init__(self, rules: Optional[Iterable[Rule]] = None) -> None:
        self._rules: List[Rule] = []
        self._by_id: Dict[str, Rule] = {}
        if rules:
            for rule in rules:
                self.add_rule(rule)

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "RuleBase":
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Rules file not found: {path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuleValidationError(f"Invalid JSON in {path}: {exc}") from exc
        return cls.from_data(raw)

    @classmethod
    def from_data(cls, data: Any) -> "RuleBase":
        rules_list = cls._extract_rules_list(data)
        base = cls()
        for item in rules_list:
            base.add_rule(cls._parse_rule(item))
        if not base._rules:
            raise RuleValidationError("Rule base is empty.")
        return base

    @staticmethod
    def _extract_rules_list(data: Any) -> List[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "rules" in data:
            if not isinstance(data["rules"], list):
                raise RuleValidationError("'rules' must be a JSON array.")
            return data["rules"]
        raise RuleValidationError(
            "Rules JSON must be an array of rules or an object with a 'rules' array."
        )

    @staticmethod
    def _parse_rule(item: Any) -> Rule:
        if not isinstance(item, dict):
            raise RuleValidationError("Each rule must be a JSON object.")
        missing = [k for k in ("id", "conditions", "conclusion") if k not in item]
        if missing:
            raise RuleValidationError(f"Rule missing fields: {', '.join(missing)}")
        if not isinstance(item["conditions"], list):
            raise RuleValidationError(f"Rule {item.get('id')}: conditions must be a list.")
        return Rule(
            id=str(item["id"]),
            conditions=item["conditions"],
            conclusion=str(item["conclusion"]),
            description=str(item.get("description", "")),
        )

    def add_rule(self, rule: Rule, persist_path: Optional[Union[str, Path]] = None) -> None:
        """Register a rule. Optionally append it to the JSON file on disk."""
        if rule.id in self._by_id:
            raise RuleValidationError(f"Duplicate rule id: {rule.id}")
        self._rules.append(rule)
        self._by_id[rule.id] = rule
        if persist_path is not None:
            self.save_json(persist_path)

    def get(self, rule_id: str) -> Optional[Rule]:
        return self._by_id.get(rule_id)

    def all(self) -> List[Rule]:
        return list(self._rules)

    def applicable(self, facts: FactsBase) -> List[Rule]:
        """Rules that can fire given the current facts (stable list order)."""
        return [r for r in self._rules if r.is_applicable(facts)]

    def conclusions(self) -> List[str]:
        return [r.conclusion for r in self._rules]

    def all_literals(self) -> List[str]:
        seen = []
        for rule in self._rules:
            for fact in rule.conditions + [rule.conclusion]:
                if fact not in seen:
                    seen.append(fact)
        return seen

    def known_symptoms(self) -> List[str]:
        """Facts that appear as conditions but never as a conclusion (user inputs)."""
        conclusions = set(self.conclusions())
        symptoms: List[str] = []
        for rule in self._rules:
            for cond in rule.conditions:
                if cond not in conclusions and cond not in symptoms:
                    symptoms.append(cond)
        return symptoms

    def save_json(self, path: Union[str, Path]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"rules": [r.to_dict() for r in self._rules]}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._rules)

    def __iter__(self):
        return iter(self._rules)
