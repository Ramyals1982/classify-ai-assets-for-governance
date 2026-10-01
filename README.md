# AI Governance Risk Engine (Laya + Rego)

Classifies internal AI/ML systems against the **EU AI Act** and **NIST AI
RMF 1.0** (Govern, Map, Measure, Manage) by combining a developer
questionnaire (deterministic) with a fine-tuned Laya model (semantic), and
surfaces the result to a leadership dashboard with a full drill-down.

## What's done

- **Shared schema** (`governance_schema.py`) - every question, option, and
  NIST weight is defined once and imported everywhere else, so the intake
  form, the training-set generator, and the risk engine can't drift apart.
- **Developer questionnaire** (`developer_intake_app.py`) - a Streamlit
  form capturing EU AI Act Annex III triggers and NIST sub-check levels
  for all four functions (Govern, Map, Measure, Manage), writing to
  `enterprise_ai_intake_forms.csv`.
- **Policy engine** (`ai_governance.rego`) - the single place scoring
  logic lives: composite NIST scores, the rule that a deterministic
  trigger can only *escalate* risk (never downgrade Laya's semantic
  read), the confidence gate, disagreement flags between the
  questionnaire and the model, and the final `action_priority`.
  `opa_bridge.py` evaluates it via the real OPA CLI if installed, or an
  equivalent Python implementation if not.
- **Risk engine** (`laya_risk_engine.py`) - orchestrates the above: loads
  intake rows, calls the fine-tuned Laya model, builds the policy input,
  evaluates it, writes `laya_full_audit_report.csv` with a full decision
  trace per asset.
- **Training-set generator** (`create_training_dataset.py`) - produces
  `train_dataset.jsonl` for fine-tuning, now importing its question/option
  text from `governance_schema.py` instead of a separate copy, so the
  model is never trained on different wording than the risk engine
  queries it with at inference time.
- **Leadership dashboard** (`leadership_dashboard.py`) - designed for a
  single glance: a traffic-light posture banner, color-coded KPI tiles,
  a risk-tier donut chart and an action-priority bar chart, a four-up
  NIST maturity snapshot, and a filterable asset register. A per-asset
  drill-down reads the actual decision trace (sub-check levels, semantic
  read, disagreement flags) with a small bar chart of that asset's four
  NIST scores against the approval baseline, rather than re-deriving
  numbers from formatted strings. A second tab shows the model's own
  measured reliability with color-coded scorecards.
- **Test suite** (`test_laya_suite.py`) - accuracy against a golden set,
  calibration error (ECE), paraphrase robustness, and a check that the
  model hedges on genuinely ambiguous input. Writes
  `laya_benchmark_report.json` for the dashboard's reliability tab. Does
  **not** fabricate a commercial-API comparison; that table only appears
  if you set `TYPESAFE_API_KEY` and it's measured live.

## What's explicitly not done yet

- **Only `eu_risk_tier` and `nist_govern` are fine-tuned.** The training
  set has no gold labels for Map/Measure/Manage, so Laya's read on those
  is zero-shot. The Rego treats the questionnaire's composite as
  authoritative for those three and only uses Laya's read to flag
  disagreement. Add gold labels for them in
  `create_training_dataset.py` and retrain to change this.
- **`ai_governance.rego` has not been run through the real OPA CLI from
  this side.** It's written for Rego v1 syntax (`import rego.v1` +
  explicit `if` keywords on every rule body), which is what current OPA
  binaries expect by default. If you see `opa eval` fail with exit code
  2, that's a parse error -- `opa_bridge.py` now surfaces OPA's actual
  stderr in the exception instead of hiding it, so read that message
  first. Run `opa check ai_governance.rego` before relying on it in
  production.
- **The 21-case training set is small.** Good enough to prove the
  pipeline works end to end; not enough to trust the fine-tuned model's
  accuracy numbers as representative. Add more real, varied cases before
  treating `test_laya_suite.py`'s accuracy figure as meaningful.

## Repository layout

| File | Role |
|---|---|
| `governance_schema.py` | Single source of truth for questions, options, weights |
| `ai_governance.rego` | Scoring/decision policy |
| `opa_bridge.py` | Evaluates the Rego (real OPA, or Python fallback) |
| `developer_intake_app.py` | Streamlit intake questionnaire |
| `create_training_dataset.py` | Builds `train_dataset.jsonl` for fine-tuning |
| `laya_risk_engine.py` | Orchestrates Laya + the policy, writes the audit report |
| `leadership_dashboard.py` | Streamlit dashboard + drill-down |
| `test_laya_suite.py` | Accuracy / calibration / robustness tests |
| `executive_report_generator_jev.py` | Optional commercial-API comparison (unchanged) |
| `requirements.txt` | Python dependencies |

## Run sequence

**0. Install dependencies**
```bash
pip install -r requirements.txt
# optional, for the real Rego engine instead of the Python fallback:
# https://www.openpolicyagent.org/docs/latest/#running-opa
```

**1. Generate the fine-tuning dataset**
```bash
python create_training_dataset.py
# -> train_dataset.jsonl
```

**2. Fine-tune Laya** (on Kaggle, or wherever you train) using
`train_dataset.jsonl`, following the notebook changes from earlier in
this conversation. Place the resulting model at `./laya_fine_tuned_model`
(the path `laya_risk_engine.py` and `test_laya_suite.py` expect).

**3. Prove the model's confidence before trusting it downstream**
```bash
python test_laya_suite.py
# -> prints accuracy / ECE / robustness / ambiguity results
# -> writes laya_benchmark_report.json
```
If this reports less than 100% on the golden set or fails the
robustness check, fix the model or the training set before step 5.

**4. Collect developer submissions**
```bash
streamlit run developer_intake_app.py
```
Each submission appends a row to `enterprise_ai_intake_forms.csv`.

**5. Run the risk engine**
```bash
python laya_risk_engine.py
# -> laya_full_audit_report.csv
```
If `enterprise_ai_intake_forms.csv` is empty or missing, it falls back to
`enterprise_ai_inventory.csv` (no questionnaire data) and defaults every
NIST sub-check to Level 1 and every EU trigger to False for those rows -
it will say so on the console.

**6. Open the dashboard**
```bash
streamlit run leadership_dashboard.py
```
Reads `laya_full_audit_report.csv` (asset register + drill-down) and
`laya_benchmark_report.json` (reliability tab), both produced above.

**Re-running:** steps 4-6 repeat as new systems are registered; steps
1-3 only repeat when you change the training data or retrain the model.
