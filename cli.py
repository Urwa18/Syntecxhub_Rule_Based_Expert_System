"""Command-line interface for the medical symptom expert system."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Sequence

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.facts import normalize_fact
from engine.inference import ForwardChainingEngine, InferenceResult
from engine.rules import RuleBase

RULES_PATH = ROOT / "data" / "rules.json"

DIAGNOSES = {
    "flu_suspected",
    "common_cold",
    "migraine",
    "food_poisoning",
    "covid_suspected",
    "allergy",
}
RECOMMENDATIONS = {"see_doctor", "rest_and_fluids", "take_antihistamine"}


def load_engine() -> tuple[RuleBase, ForwardChainingEngine]:
    rule_base = RuleBase.from_json(RULES_PATH)
    return rule_base, ForwardChainingEngine(rule_base)


def parse_symptom_text(text: str) -> List[str]:
    parts = [p for chunk in text.replace(";", ",").split(",") for p in chunk.split()]
    facts = []
    for part in parts:
        fact = normalize_fact(part)
        if fact and fact not in facts:
            facts.append(fact)
    return facts


def prompt_symptoms(known: Sequence[str]) -> List[str]:
    print("Known symptoms (enter numbers, names, or a comma-separated list):\n")
    for i, name in enumerate(known, start=1):
        print(f"  {i:2d}. {name}")
    print()
    raw = input("Your symptoms: ").strip()
    if not raw:
        return []

    selected: List[str] = []
    tokens = [t.strip() for t in raw.replace(";", ",").split(",") if t.strip()]
    for token in tokens:
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(known):
                fact = known[idx - 1]
                if fact not in selected:
                    selected.append(fact)
            else:
                print(f"  (ignored out-of-range number: {token})")
        else:
            # allow space-separated numbers in one token group
            sub = token.split()
            if all(s.isdigit() for s in sub):
                for s in sub:
                    idx = int(s)
                    if 1 <= idx <= len(known):
                        fact = known[idx - 1]
                        if fact not in selected:
                            selected.append(fact)
            else:
                fact = normalize_fact(token)
                if fact and fact not in selected:
                    selected.append(fact)
    return selected


def split_derived(derived: Sequence[str]) -> tuple[List[str], List[str], List[str]]:
    diagnoses = [f for f in derived if f in DIAGNOSES]
    recs = [f for f in derived if f in RECOMMENDATIONS]
    other = [f for f in derived if f not in DIAGNOSES and f not in RECOMMENDATIONS]
    return diagnoses, recs, other


def print_result(result: InferenceResult) -> None:
    print("\n=== Reasoning path ===")
    print(result.log.format() or "(empty log)")

    diagnoses, recs, other = split_derived(result.derived)
    print("\n=== Derived conclusions ===")
    if not result.derived:
        print("No conclusion found.")
        print(
            "Try adding more symptoms (for example fever + cough + body_ache + fatigue), "
            "or check the numbered list for spelling."
        )
        return

    if diagnoses:
        print("Diagnoses:")
        for d in diagnoses:
            print(f"  - {d}")
    if recs:
        print("Recommendations:")
        for r in recs:
            print(f"  - {r}")
    if other:
        print("Intermediate conditions:")
        for o in other:
            print(f"  - {o}")

    print("\n=== All facts ===")
    for fact, origin in result.facts.items():
        print(f"  [{origin}] {fact}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Forward-chaining medical symptom expert system (educational demo)."
    )
    parser.add_argument(
        "-s",
        "--symptoms",
        help="Comma-separated symptoms, e.g. fever,cough,body_ache,fatigue",
    )
    parser.add_argument(
        "--export-log",
        metavar="PATH",
        help="Write the inference log to a text file.",
    )
    parser.add_argument(
        "--export-json",
        metavar="PATH",
        help="Write the inference log to a JSON file.",
    )
    args = parser.parse_args(argv)

    print("Rule-Based Expert System - medical symptoms (educational demo, not medical advice).\n")
    rule_base, engine = load_engine()
    known = rule_base.known_symptoms()

    if args.symptoms:
        initial = parse_symptom_text(args.symptoms)
    else:
        initial = prompt_symptoms(known)

    if not initial:
        print("No symptoms entered. Exiting.")
        return 1

    print("Input facts:", ", ".join(initial))
    result = engine.run(initial)
    print_result(result)

    if args.export_log:
        result.log.export(args.export_log, as_json=False)
        print(f"\nLog written to {args.export_log}")
    if args.export_json:
        result.log.export(args.export_json, as_json=True)
        print(f"JSON log written to {args.export_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
