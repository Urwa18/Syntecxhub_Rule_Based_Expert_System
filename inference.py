"""Forward-chaining inference engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from engine.facts import FactsBase, normalize_fact
from engine.logger import InferenceLog
from engine.rules import RuleBase


@dataclass
class InferenceResult:
    """Outcome of a forward-chaining run."""

    facts: FactsBase
    derived: List[str]
    log: InferenceLog
    iterations: int
    stopped_by_guard: bool = False

    @property
    def conclusions(self) -> List[str]:
        """Alias used by the UI/CLI: facts inferred by rules."""
        return list(self.derived)


class ForwardChainingEngine:
    """Apply if-then rules until a fixed point (no new facts).

    On each iteration every currently applicable rule is considered, but
    rules fire one at a time so each conclusion can enable later rules in
    the same or later iterations. A max-iteration guard prevents runaway
    loops if the rule set were cyclic in a way that kept adding facts.
    """

    def __init__(
        self,
        rule_base: RuleBase,
        max_iterations: Optional[int] = None,
    ) -> None:
        self.rule_base = rule_base
        # Default: plenty of room for multi-layer chaining, but finite.
        self.max_iterations = max_iterations if max_iterations is not None else max(
            50, len(rule_base) * 3 + 5
        )

    def run(self, initial_facts: Sequence[str]) -> InferenceResult:
        facts = FactsBase()
        for raw in initial_facts:
            facts.add(raw, source="user input")

        log = InferenceLog()
        derived: List[str] = []
        fired_ids: List[str] = []
        iteration = 0
        stopped_by_guard = False

        while iteration < self.max_iterations:
            applicable = self.rule_base.applicable(facts)
            if not applicable:
                log.mark_complete()
                break

            iteration += 1
            # Fire the first applicable rule (rule-file order). Newly added
            # facts may unlock other rules on the next pass.
            rule = applicable[0]
            source = f"inferred by rule {rule.id}"
            added = facts.add(rule.conclusion, source=source)
            if not added:
                # Should not happen (is_applicable checks this); skip to avoid a spin.
                log.note(f"Iteration {iteration}: {rule.id} skipped (conclusion already present).")
                continue

            derived.append(rule.conclusion)
            fired_ids.append(rule.id)
            log.record(
                iteration=iteration,
                rule_id=rule.id,
                conditions=rule.conditions,
                conclusion=rule.conclusion,
                description=rule.description,
            )
        else:
            # Loop exhausted without reaching a fixed point.
            stopped_by_guard = True
            log.note(
                f"Stopped after {self.max_iterations} iterations "
                "(infinite-loop guard). Inference halted."
            )

        return InferenceResult(
            facts=facts,
            derived=derived,
            log=log,
            iterations=iteration,
            stopped_by_guard=stopped_by_guard,
        )
