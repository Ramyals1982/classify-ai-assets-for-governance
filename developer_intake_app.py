import os
import uuid

import pandas as pd
import streamlit as st

from governance_schema import EU_TRIGGERS, NIST_SUBCHECKS

st.set_page_config(page_title="AI Asset Intake Portal", layout="centered")

st.title("Enterprise AI Asset Intake Portal")
st.markdown(
    """
Register any new AI model, ML pipeline, or LLM implementation here before it
goes to production. Your answers are evaluated against the **EU AI Act** and
the **NIST AI RMF 1.0** (Govern, Map, Measure, Manage) by the Laya risk
engine and a Rego policy that the risk team maintains.
"""
)
st.divider()

CSV_FILE = "enterprise_ai_intake_forms.csv"


def _csv_columns() -> list[str]:
    cols = ["System_ID", "Name", "Description"]
    cols += [f"Trigger_{key}" for key in EU_TRIGGERS]
    for function, spec in NIST_SUBCHECKS.items():
        cols += [f"{function.title()}_{item}" for item in spec["items"]]
    return cols


def init_csv():
    if not os.path.exists(CSV_FILE):
        pd.DataFrame(columns=_csv_columns()).to_csv(CSV_FILE, index=False)


init_csv()

with st.form("intake_form", clear_on_submit=True):
    st.subheader("1. System Identification")
    name = st.text_input("System Name", placeholder="e.g., OptiHire Video Analyzer")
    description = st.text_area(
        "System Description",
        placeholder="Describe the core functionality, intended use case, and target users.",
    )

    st.subheader("2. EU AI Act - High-Risk Use Case Triggers")
    st.markdown("Does this system directly perform or support any of the following? (Check all that apply)")
    trigger_answers = {}
    trigger_cols = st.columns(2)
    for i, (key, spec) in enumerate(EU_TRIGGERS.items()):
        with trigger_cols[i % 2]:
            trigger_answers[key] = st.checkbox(f"{spec['label']} ({spec['eu_ref']})", key=f"trigger_{key}")

    st.subheader("3. NIST AI RMF Maturity")
    st.caption(
        "Answer for GOVERN, MAP, MEASURE, and MANAGE. Laya's fine-tuned model currently "
        "scores GOVERN semantically; the other three rely on your answers here as the "
        "authoritative source until the model is retrained on them."
    )
    subcheck_answers: dict[str, dict[str, str]] = {}
    for function, spec in NIST_SUBCHECKS.items():
        st.markdown(f"**{function.upper()}**")
        subcheck_answers[function] = {}
        for item_key, item in spec["items"].items():
            choice = st.radio(item["question"], options=item["levels"], key=f"{function}_{item_key}", horizontal=False)
            subcheck_answers[function][item_key] = choice.split(":")[0].strip()  # "Level N"

    st.divider()
    submitted = st.form_submit_button("Submit Asset for Governance Review", type="primary")

if submitted:
    if not name or not description:
        st.error("System Name and Description are mandatory fields.")
    else:
        system_id = f"GCC-AI-{uuid.uuid4().hex[:6].upper()}"
        new_record = {"System_ID": system_id, "Name": name, "Description": description}
        for key, value in trigger_answers.items():
            new_record[f"Trigger_{key}"] = "Yes" if value else "No"
        for function, items in subcheck_answers.items():
            for item_key, level in items.items():
                new_record[f"{function.title()}_{item_key}"] = level

        df = pd.read_csv(CSV_FILE)
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)

        st.success(f"System '{name}' registered with ID {system_id}.")
        st.info("This asset will now be scored by the Laya risk engine. Check the Leadership Dashboard for its compliance posture.")
