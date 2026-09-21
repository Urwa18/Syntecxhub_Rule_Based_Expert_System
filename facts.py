"""Working memory: a set of facts with origin tracking."""

from __future__ import annotations

from typing import Dict, List, Optional


def normalize_fact(fact: str) -> str:
    """Lowercase and collapse whitespace so matching is consistent."""
    return " ".join(fact.strip().lower().split()).replace(" ", "_")


class FactsBase:
    """Stores known facts and where each one came from.

    Origins are human-readable, e.g. ``"user input"`` or
    ``"inferred by rule R2"``.
    """

    def __init__(self) -> None:
        self._facts: Dict[str, str] = {}

    def add(self, fact: str, source: str = "user input") -> bool:
        """Add a fact if it is new.

        Returns True when the fact was inserted, False if it was already present.
        Empty / whitespace-only strings are ignored.
        """
        key = normalize_fact(fact)
        if not key:
            return False
        if key in self._facts:
            return False
        self._facts[key] = source
        return True

    def has(self, fact: str) -> bool:
        """Return True if the (normalized) fact is known."""
        return normalize_fact(fact) in self._facts

    def all(self) -> List[str]:
        """Return all facts in insertion order."""
        return list(self._facts.keys())

    def origin(self, fact: str) -> Optional[str]:
        """Return the recorded source of a fact, or None if unknown."""
        return self._facts.get(normalize_fact(fact))

    def items(self) -> List[tuple[str, str]]:
        """Return (fact, origin) pairs in insertion order."""
        return list(self._facts.items())

    def user_facts(self) -> List[str]:
        return [f for f, src in self._facts.items() if src == "user input"]

    def inferred_facts(self) -> List[str]:
        return [f for f, src in self._facts.items() if src != "user input"]

    def clear(self) -> None:
        """Remove every fact."""
        self._facts.clear()

    def __len__(self) -> int:
        return len(self._facts)

    def __contains__(self, fact: str) -> bool:
        return self.has(fact)

    def __repr__(self) -> str:
        return f"FactsBase({self.all()!r})"
