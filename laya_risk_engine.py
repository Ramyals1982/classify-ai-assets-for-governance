"""
The risk engine. Two inputs feed one decision per asset:

  1. The developer questionnaire (enterprise_ai_intake_forms.csv) -
     deterministic EU AI Act trigger checkboxes and NIST sub-check levels.
  2. Laya's semantic read of the same system description - the EU tier and
     (today) GOVERN maturity are fine-tuned; MAP/MEASURE/MANAGE are zero-shot
     until the training set includes gold labels for them (see
     governance_schema.py's module docstring).

Both are passed to ai_governance.rego (via opa_bridge), which is the single
place the actual weighing/scoring logic lives. This file only orchestrates:
build the Laya questions, call the model, build the policy input, evaluate
it, and write the result out.

Run: python laya_risk_engine.py
"""
from __future__ import annotations

import json
import sys

import pandas as pd

import opa_bridge
from governance_schema import (
    CONFIDENCE_THRESHOLD,
    EU_TRIGGERS,
    LAYA_QUESTIONS,
    NIST_SUBCHECKS,
)

LOCAL_MODEL_PATH = "./laya_finetuned_typed_decisions"
INTAKE_CSV = "enterprise_ai_intake_forms.csv"
LEGACY_INVENTORY_CSV = "enterprise_ai_inventory.csv"
OUTPUT_CSV = "laya_full_audit_report.csv"


def load_intake() -> tuple[pd.DataFrame, bool]:
    """Returns (dataframe, has_questionnaire_data)."""
    import os

    if os.path.exists(INTAKE_CSV):
        df = pd.read_csv(INTAKE_CSV)
        if len(df) > 0:
            return df, True
    if os.path.exists(LEGACY_INVENTORY_CSV):
        print(
            f"WARNING: '{INTAKE_CSV}' not found or empty. Falling back to "
            f"'{LEGACY_INVENTORY_CSV}', which has no questionnaire answers. "
            "Every NIST sub-check will default to Level 1 (the conservative "
            "floor) and EU triggers will all default to False, so results "
            "for these rows rest entirely on Laya's semantic read."
        )
        df = pd.read_csv(LEGACY_INVENTORY_CSV)
        return df, False
    raise FileNotFoundError(f"Neither {INTAKE_CSV} nor {LEGACY_INVENTORY_CSV} found.")


def row_to_state(row: pd.Series) -> dict:
    description = row.get("Description")
    if pd.isna(description) or description is None:
        description = row.get("Governance_Notes", "")
    return {"system_name": row.get("Name", "unknown"), "description": str(description)}


def row_to_triggers(row: pd.Series, has_questionnaire: bool) -> dict:
    if not has_questionnaire:
        return {key: False for key in EU_TRIGGERS}
    return {key: str(row.get(f"Trigger_{key}", "No")).strip().lower() == "yes" for key in EU_TRIGGERS}


def row_to_subchecks(row: pd.Series, has_questionnaire: bool) -> dict:
    out = {}
    for function, spec in NIST_SUBCHECKS.items():
        out[function] = {}
        for item_key in spec["items"]:
            col = f"{function.title()}_{item_key}"
            level = str(row.get(col, "Level 1")) if has_questionnaire else "Level 1"
            if level not in ("Level 1", "Level 2", "Level 3", "Level 4"):
                level = "Level 1"
            out[function][item_key] = level
    return out


def predict_semantic(agent, state: dict) -> dict:
    """Calls the Laya agent once with all five questions, returns choice + confidence per question."""
    result = agent.predict(state=state, questions=LAYA_QUESTIONS)
    semantic = {}
    confidence = {}
    for qid in LAYA_QUESTIONS:
        answer = result["answers"][qid]
        choice = answer.get("choice", "Minimal Risk" if qid == "eu_risk_tier" else "Level 1")
        probs = answer.get("probabilities", {})
        semantic[qid] = choice
        confidence[qid] = float(probs.get(choice, 0.0))
    return semantic, confidence


def build_report(df: pd.DataFrame, has_questionnaire: bool, agent) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        state = row_to_state(row)
        triggers = row_to_triggers(row, has_questionnaire)
        subchecks = row_to_subchecks(row, has_questionnaire)
        semantic, confidence = predict_semantic(agent, state)

        policy_input = {
            "eu_triggers": triggers,
            "nist_subchecks": subchecks,
            "semantic": {**semantic, "confidence": confidence},
        }
        decision = opa_bridge.evaluate(policy_input)

        rows.append({
            "System_ID": row.get("System_ID", ""),
            "Name": row.get("Name", ""),
            "EU_Risk_Tier": decision["final_eu_tier"],
            "EU_Confidence": f"{confidence['eu_risk_tier']:.1%}",
            "Undisclosed_Risk_Flag": decision["undisclosed_risk"],
            "Govern_Final": opa_bridge_level(decision["govern_final_score"]),
            "Govern_Composite": decision["govern_composite"],
            "Govern_Semantic": semantic["nist_govern"],
            "Govern_Disagreement": decision["govern_disagreement"],
            "Map_Final": opa_bridge_level(decision["map_final_score"]),
            "Map_Disagreement": decision["map_disagreement"],
            "Measure_Final": opa_bridge_level(decision["measure_final_score"]),
            "Measure_Disagreement": decision["measure_disagreement"],
            "Manage_Final": opa_bridge_level(decision["manage_final_score"]),
            "Manage_Disagreement": decision["manage_disagreement"],
            "Valid_NIST_Baseline": decision["valid_nist_baseline"],
            "Is_Approved": decision["is_approved"],
            "Action_Priority": decision["action_priority"],
            # Full trace for the dashboard drill-down: exact sub-check levels,
            # semantic answers, and confidences that produced this row.
            "Decision_Trace": json.dumps({
                "triggers": triggers,
                "nist_subchecks": subchecks,
                "semantic": semantic,
                "confidence": confidence,
                "decision": decision,
            }),
        })
    return pd.DataFrame(rows)


def opa_bridge_level(score: float) -> str:
    from governance_schema import score_to_level
    return score_to_level(score)


def main():
    try:
        import laya
    except ImportError:
        print(
            "ERROR: the 'laya' package is not installed / importable. "
            "Install it (see requirements.txt) or run this from an "
            "environment where the fine-tuned model has been loaded.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loading fine-tuned Laya agent from {LOCAL_MODEL_PATH} ...")
    agent = laya.Agent(LOCAL_MODEL_PATH)

    df, has_questionnaire = load_intake()
    print(f"Scoring {len(df)} asset(s) "
          f"({'questionnaire + semantic' if has_questionnaire else 'semantic-only, no questionnaire data'})...")

    report_df = build_report(df, has_questionnaire, agent)
    report_df.to_csv(OUTPUT_CSV, index=False)

    print(f"\nAudit complete. Wrote {OUTPUT_CSV}.")
    low_conf = (report_df["EU_Confidence"].str.rstrip("%").astype(float) / 100 < CONFIDENCE_THRESHOLD).sum()
    print(report_df[["Name", "EU_Risk_Tier", "EU_Confidence", "Action_Priority"]].to_string(index=False))
    if low_conf:
        print(f"\n{low_conf} asset(s) fell below the {CONFIDENCE_THRESHOLD:.0%} confidence threshold "
              "and were routed to manual review.")


if __name__ == "__main__":
    main()
