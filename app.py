"""Streamlit UI for the medical symptom expert system."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.facts import normalize_fact
from engine.inference import ForwardChainingEngine
from engine.rules import Rule, RuleBase, RuleValidationError

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

CUSTOM_CSS = """
<style>
    .block-container { max-width: 980px; padding-top: 1.4rem; }
    .disclaimer {
        background: #fff6e5;
        border: 1px solid #f0d9a6;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        color: #5c4a1f;
        margin-bottom: 1rem;
    }
    .fact-user { color: #1d4ed8; }
    .fact-inferred { color: #047857; }
    .empty-box {
        background: #f8fafc;
        border: 1px dashed #cbd5e1;
        border-radius: 10px;
        padding: 1rem 1.1rem;
    }
</style>
"""


@st.cache_resource
def load_rule_base() -> RuleBase:
    return RuleBase.from_json(RULES_PATH)


def session_rule_base() -> RuleBase:
    if "rule_base" not in st.session_state:
        st.session_state.rule_base = load_rule_base()
    return st.session_state.rule_base


def parse_free_text(text: str) -> list[str]:
    if not text.strip():
        return []
    chunks = text.replace(";", ",").split(",")
    facts: list[str] = []
    for chunk in chunks:
        fact = normalize_fact(chunk)
        if fact and fact not in facts:
            facts.append(fact)
    return facts


def render_sidebar(rule_base: RuleBase) -> None:
    with st.sidebar:
        st.header("Rules")
        st.caption(f"{len(rule_base)} rules loaded from data/rules.json")
        with st.expander("View all rules", expanded=False):
            for rule in rule_base.all():
                st.markdown(f"**{rule.pretty()}**")
                if rule.description:
                    st.caption(rule.description)

        st.subheader("Add a rule")
        with st.form("add_rule_form", clear_on_submit=True):
            new_id = st.text_input("Rule id", placeholder="R35")
            conds = st.text_input("Conditions (comma-separated)", placeholder="fever, cough")
            conclusion = st.text_input("Conclusion", placeholder="respiratory_infection")
            description = st.text_input("Description (optional)")
            persist = st.checkbox("Save to rules.json", value=False)
            submitted = st.form_submit_button("Add rule")

        if submitted:
            conditions = [normalize_fact(c) for c in conds.split(",") if c.strip()]
            try:
                rule = Rule(
                    id=new_id,
                    conditions=conditions,
                    conclusion=conclusion,
                    description=description,
                )
                persist_path = RULES_PATH if persist else None
                rule_base.add_rule(rule, persist_path=persist_path)
                if persist:
                    load_rule_base.clear()
                st.success(f"Added {rule.pretty()}")
            except RuleValidationError as exc:
                st.error(str(exc))


def main() -> None:
    st.set_page_config(page_title="Symptom Expert System", page_icon="🩺", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    st.title("Rule-Based Symptom Expert System")
    st.markdown(
        '<div class="disclaimer"><strong>Disclaimer:</strong> This is an educational '
        "demo of forward chaining. It is <em>not</em> medical advice, diagnosis, or "
        "treatment. If you are unwell, consult a qualified clinician.</div>",
        unsafe_allow_html=True,
    )

    rule_base = session_rule_base()
    render_sidebar(rule_base)

    symptoms = rule_base.known_symptoms()
    col1, col2 = st.columns([1.15, 0.85])
    with col1:
        picked = st.multiselect("Select symptoms", options=symptoms)
        free = st.text_input(
            "Or type extra symptoms",
            placeholder="e.g. fever, cough, body_ache",
        )
    with col2:
        st.write("")
        st.write("")
        diagnose = st.button("Diagnose", type="primary", use_container_width=True)

    initial: list[str] = []
    for fact in list(picked) + parse_free_text(free):
        if fact not in initial:
            initial.append(fact)

    if diagnose:
        if not initial:
            st.warning("Enter or select at least one symptom.")
            return
        engine = ForwardChainingEngine(rule_base)
        result = engine.run(initial)
        st.session_state.last_result = result
        st.session_state.last_inputs = initial

    result = st.session_state.get("last_result")
    if result is None:
        st.info("Select symptoms and click Diagnose to run forward chaining.")
        return

    derived = result.derived
    diagnoses = [f for f in derived if f in DIAGNOSES]
    recs = [f for f in derived if f in RECOMMENDATIONS]
    intermediate = [f for f in derived if f not in DIAGNOSES and f not in RECOMMENDATIONS]

    st.subheader("Conclusions")
    if not derived:
        st.markdown(
            '<div class="empty-box"><strong>No conclusion found.</strong><br/>'
            "No rule matched the current facts. Add related symptoms "
            "(for example <code>fever, cough, body_ache, fatigue</code> for a "
            "three-step flu chain) or inspect the rule list in the sidebar.</div>",
            unsafe_allow_html=True,
        )
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Diagnoses**")
            st.write("\n".join(f"- {x}" for x in diagnoses) if diagnoses else "_none_")
        with c2:
            st.markdown("**Recommendations**")
            st.write("\n".join(f"- {x}" for x in recs) if recs else "_none_")
        with c3:
            st.markdown("**Intermediate conditions**")
            st.write("\n".join(f"- {x}" for x in intermediate) if intermediate else "_none_")

    st.subheader("Reasoning path")
    if result.log.entries:
        for entry in result.log.entries:
            st.markdown(
                f"**Iteration {entry.iteration}** · `{entry.rule_id}`  \n"
                f"{' AND '.join(entry.conditions)} → **{entry.conclusion}**"
            )
            if entry.description:
                st.caption(entry.description)
        if result.log.complete:
            st.success("No more rules applicable. Inference complete.")
        if result.stopped_by_guard:
            st.warning("Stopped by the infinite-loop guard.")
    else:
        st.write("No rules fired.")
        if result.log.complete:
            st.caption("No more rules applicable. Inference complete.")

    with st.expander("Full log (text / JSON)", expanded=False):
        st.code(result.log.format(), language="text")
        st.code(result.log.to_json(), language="json")

    st.subheader("All facts")
    user_rows = result.facts.user_facts()
    inferred_rows = result.facts.inferred_facts()
    f1, f2 = st.columns(2)
    with f1:
        st.markdown("**User input**")
        for fact in user_rows:
            st.markdown(f"<span class='fact-user'>● {fact}</span>", unsafe_allow_html=True)
        if not user_rows:
            st.caption("None")
    with f2:
        st.markdown("**Inferred**")
        for fact in inferred_rows:
            origin = result.facts.origin(fact) or "inferred"
            st.markdown(
                f"<span class='fact-inferred'>● {fact}</span>  \n<small>{origin}</small>",
                unsafe_allow_html=True,
            )
        if not inferred_rows:
            st.caption("None")


main()
