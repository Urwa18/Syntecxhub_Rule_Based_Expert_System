# Medical Symptom Expert System (forward chaining)

Educational rule-based expert system. You enter symptoms as facts; if-then rules fire in a loop until nothing new can be inferred. **This is not medical advice.**

## Install (Windows / PowerShell)

```powershell
cd "D:\frontend\Rule system\expert_system"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If script execution is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Run the CLI

Interactive (numbered symptom list):

```powershell
python cli.py
```

Pass symptoms directly:

```powershell
python cli.py -s "fever,cough,body_ache,fatigue"
```

Export the reasoning log:

```powershell
python cli.py -s "itchy_eyes,sneezing,runny_nose" --export-log log.txt --export-json log.json
```

## Run the Streamlit UI

```powershell
streamlit run app.py
```

Then open the URL shown in the terminal (usually `http://localhost:8501`).

- Pick symptoms (multiselect) and/or type extra facts.
- Click **Diagnose**.
- The page shows conclusions, a step-by-step timeline, and user vs inferred facts.
- Sidebar: browse every rule or add a new one (optionally write it to `data/rules.json`).

## Run tests

```powershell
python -m pytest tests/test_engine.py -v
```

## How forward chaining works

1. User facts go into a **facts base** (working memory), normalized to lowercase with underscores (`Body ache` → `body_ache`).
2. A rule is **applicable** when every condition is already a fact and the conclusion is not.
3. The engine fires applicable rules **one at a time**, adding each conclusion as a new fact tagged `inferred by rule R#`.
4. That new fact can unlock later rules (multi-step chaining) until a **fixed point**: no remaining applicable rules.
5. A max-iteration **guard** stops runaway loops. Each fired rule is written to an **inference log**.

Layers in `data/rules.json`:

| Layer | Example | Role |
| --- | --- | --- |
| 1 | `fever` AND `cough` → `respiratory_infection` | symptoms → intermediate |
| 2 | `respiratory_infection` AND `body_ache` AND `fever` → `flu_suspected` | intermediate → diagnosis |
| 3 | `flu_suspected` AND `fatigue` → `rest_and_fluids` | diagnosis → recommendation |

Three built-in chains that need **3+ inference steps**:

1. `fever, cough, body_ache, fatigue` → respiratory_infection → flu_suspected → rest_and_fluids
2. `nausea, vomiting, diarrhea, abdominal_pain` → GI distress / dehydration_risk → food_poisoning → rest_and_fluids / see_doctor
3. `itchy_eyes, sneezing, runny_nose` → allergic_reaction → allergy → take_antihistamine

## How to add rules

Edit `data/rules.json` (no code changes). Each rule:

```json
{
  "id": "R35",
  "conditions": ["fact_a", "fact_b"],
  "conclusion": "new_fact",
  "description": "Why this rule exists"
}
```

Conditions are AND-ed. Ids must be unique. You can also add a rule at runtime from the Streamlit sidebar.

## Sample run

```powershell
python cli.py -s "fever,cough,body_ache,fatigue"
```

Expected reasoning path (rule ids from the shipped JSON):

```
Iteration 1: R1 fired: fever AND cough => respiratory_infection
Iteration 2: R15 fired: respiratory_infection AND body_ache AND fever => flu_suspected
Iteration 3: R24 fired: flu_suspected AND fatigue => rest_and_fluids
No more rules applicable. Inference complete.
```

Diagnoses include `flu_suspected`; recommendations include `rest_and_fluids`.

## Project layout

```
expert_system/
  engine/          # FactsBase, Rule/RuleBase, ForwardChainingEngine, InferenceLog
  data/rules.json  # knowledge base
  app.py           # Streamlit UI
  cli.py           # command line
  tests/           # pytest
  requirements.txt
  README.md
```
