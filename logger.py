"""Inference trace: one record per fired rule, plus a completion message."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Sequence, Union


@dataclass
class LogEntry:
    """A single forward-chaining step."""

    iteration: int
    rule_id: str
    conditions: List[str]
    conclusion: str
    description: str = ""

    def format(self) -> str:
        joined = " AND ".join(self.conditions)
        return (
            f"Iteration {self.iteration}: {self.rule_id} fired: "
            f"{joined} => {self.conclusion}"
        )


@dataclass
class InferenceLog:
    """Collects reasoning steps and can export them as text or JSON."""

    entries: List[LogEntry] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    complete: bool = False

    def record(
        self,
        iteration: int,
        rule_id: str,
        conditions: Sequence[str],
        conclusion: str,
        description: str = "",
    ) -> LogEntry:
        entry = LogEntry(
            iteration=iteration,
            rule_id=rule_id,
            conditions=list(conditions),
            conclusion=conclusion,
            description=description,
        )
        self.entries.append(entry)
        self.messages.append(entry.format())
        return entry

    def mark_complete(self, message: str = "No more rules applicable. Inference complete.") -> None:
        self.complete = True
        self.messages.append(message)

    def note(self, message: str) -> None:
        """Append a free-form status line (e.g. loop-guard warning)."""
        self.messages.append(message)

    def format(self) -> str:
        return "\n".join(self.messages)

    def to_json(self) -> str:
        payload = {
            "entries": [asdict(e) for e in self.entries],
            "messages": self.messages,
            "complete": self.complete,
        }
        return json.dumps(payload, indent=2)

    def export(self, path: Union[str, Path], as_json: bool = False) -> Path:
        """Write the log to a file. JSON if ``as_json`` else plain text."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self.to_json() if as_json else self.format(), encoding="utf-8")
        return dest

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)
