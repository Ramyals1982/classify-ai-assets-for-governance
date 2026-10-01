"""
Proves the fine-tuned Laya model classifies with the confidence you need
before trusting it in the risk engine. Run directly (`python
test_laya_suite.py`) or under pytest (`pytest test_laya_suite.py -v`).

What this measures, honestly:
  - Accuracy against a golden set of hand-labeled cases (ground truth you
    supply below - extend GOLDEN_CASES with real cases from your own
    audits as you get them; 3 cases is not a statistically meaningful
    sample).
  - Calibration (ECE): does Laya's stated confidence match its actual
    hit rate? A well-calibrated model that says "90% confident" should be
    right about 90% of the time.
  - Robustness: does semantic paraphrasing of the same underlying system
    change the predicted tier?
  - Latency: p50 prediction time.

What this deliberately does NOT do: invent a comparison against a
commercial API (Jev/typesafe or otherwise). If you want that comparison,
set TYPESAFE_API_KEY and this suite will run the same golden cases through
executive_report_generator_jev.py's evaluate_system() and report real
numbers; without a key, the comparison table is simply omitted rather than
filled with guesses.
"""
from __future__ import annotations

import json
import os
import statistics
import time

from governance_schema import CONFIDENCE_THRESHOLD, FINE_TUNED_QUESTIONS

LOCAL_MODEL_PATH = "./laya_finetuned_typed_decisions"
BENCHMARK_OUTPUT = "laya_benchmark_report.json"

# Extend this with real, hand-verified cases as your audit program matures.
GOLDEN_CASES = [
    {
        "system_name": "LendRate Optimizer",
        "description": "Automated machine learning model that calculates credit limits and approves mortgage pricing for retail banking customers.",
        "governance_notes": "No formal documentation or owner assigned yet.",
        "expected_eu_risk": "High Risk",
        "expected_govern": "Level 1",
    },
    {
        "system_name": "Nexus Support Companion",
        "description": "Customer service conversational chatbot that answers FAQs about branch timings and credit card rewards.",
        "governance_notes": "Documented guidelines and designated product owner.",
        "expected_eu_risk": "Limited Risk",
        "expected_govern": "Level 3",
    },
    {
        "system_name": "CyberShield PhishDetect",
        "description": "Internal cybersecurity tool that scans inbound corporate emails for phishing links and malware signatures.",
        "governance_notes": "Fully managed IT security asset with automated blocklists.",
        "expected_eu_risk": "Minimal Risk",
        "expected_govern": "Level 3",
    },
]

# Same underlying system, three different phrasings. Robust classification
# should agree on the tier for all three.
ROBUSTNESS_VARIANTS = [
    "Automated credit scoring and mortgage pricing engine.",
    "Algorithmic financial assessment tool computing retail loan thresholds.",
    "Machine learning pipeline executing automated borrower credit evaluations.",
]
ROBUSTNESS_EXPECTED_TIER = "High Risk"

AMBIGUOUS_CASE = {
    "system_name": "Ambiguous Asset",
    "description": "Some tool doing some backend data processing thing.",
    "governance_notes": "None",
}


def _predict(agent, case: dict) -> dict:
    state = {"system_name": case["system_name"], "description": case["description"],
              "governance_notes": case.get("governance_notes", "")}
    start = time.perf_counter()
    result = agent.predict(state=state, questions=FINE_TUNED_QUESTIONS)
    latency_ms = (time.perf_counter() - start) * 1000
    return result, latency_ms


def run_accuracy(agent) -> dict:
    hits, latencies, records = 0, [], []
    for case in GOLDEN_CASES:
        result, latency_ms = _predict(agent, case)
        latencies.append(latency_ms)
        eu = result["answers"]["eu_risk_tier"]
        gov = result["answers"]["nist_govern"]
        eu_ok = eu.get("choice") == case["expected_eu_risk"]
        gov_ok = gov.get("choice") == case["expected_govern"]
        if eu_ok and gov_ok:
            hits += 1
        records.append({
            "name": case["system_name"], "eu_expected": case["expected_eu_risk"],
            "eu_predicted": eu.get("choice"), "eu_confidence": eu.get("probabilities", {}).get(eu.get("choice"), 0.0),
            "govern_expected": case["expected_govern"], "govern_predicted": gov.get("choice"),
            "pass": eu_ok and gov_ok,
        })
    accuracy = hits / len(GOLDEN_CASES)
    return {"accuracy": accuracy, "records": records, "latencies_ms": latencies}


def compute_ece(records: list[dict], n_bins: int = 5) -> float:
    """Expected Calibration Error over the eu_risk_tier predictions."""
    if not records:
        return 0.0
    bins = [[] for _ in range(n_bins)]
    for r in records:
        conf = r["eu_confidence"]
        idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx].append(r)
    total = len(records)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        avg_conf = statistics.mean(r["eu_confidence"] for r in b)
        acc = statistics.mean(1.0 if r["pass"] else 0.0 for r in b)
        ece += (len(b) / total) * abs(avg_conf - acc)
    return ece


def run_robustness(agent) -> dict:
    tiers, confidences = [], []
    for text in ROBUSTNESS_VARIANTS:
        result, _ = _predict(agent, {"system_name": "variant", "description": text})
        answer = result["answers"]["eu_risk_tier"]
        tiers.append(answer.get("choice"))
        confidences.append(answer.get("probabilities", {}).get(answer.get("choice"), 0.0))
    consistent = all(t == ROBUSTNESS_EXPECTED_TIER for t in tiers)
    return {"tiers": tiers, "confidences": confidences, "consistent": consistent}


def run_ambiguity_check(agent) -> dict:
    result, _ = _predict(agent, AMBIGUOUS_CASE)
    answer = result["answers"]["eu_risk_tier"]
    choice = answer.get("choice")
    confidence = answer.get("probabilities", {}).get(choice, 0.0)
    # A trustworthy model should hedge on a genuinely vague description,
    # not report high confidence in either direction.
    appropriately_uncertain = confidence < CONFIDENCE_THRESHOLD
    return {"choice": choice, "confidence": confidence, "appropriately_uncertain": appropriately_uncertain}


def try_jev_comparison(agent_accuracy: dict) -> list[dict] | None:
    if not os.environ.get("TYPESAFE_API_KEY"):
        return None
    try:
        from executive_report_generator_jev import evaluate_system
    except ImportError:
        return None
    rows = []
    for case in GOLDEN_CASES:
        start = time.perf_counter()
        jev_result = evaluate_system(case["description"], case.get("governance_notes", ""))
        latency_ms = (time.perf_counter() - start) * 1000
        jev_ok = case["expected_eu_risk"].split(" ")[0] in jev_result.get("Risk_Tier", "")
        rows.append({"Case": case["system_name"], "Model": "Jev", "Correct": jev_ok, "Latency_ms": round(latency_ms, 1)})
    for r in agent_accuracy["records"]:
        rows.append({"Case": r["name"], "Model": "Laya (fine-tuned)", "Correct": r["pass"], "Latency_ms": None})
    return rows


def main():
    import laya

    print(f"Loading fine-tuned Laya agent from {LOCAL_MODEL_PATH} ...")
    agent = laya.Agent(LOCAL_MODEL_PATH)

    print("\n=== Accuracy against golden set ===")
    acc = run_accuracy(agent)
    for r in acc["records"]:
        status = "PASS" if r["pass"] else "FAIL"
        print(f"[{status}] {r['name']}: EU {r['eu_expected']} -> {r['eu_predicted']} "
              f"({r['eu_confidence']:.1%}), GOVERN {r['govern_expected']} -> {r['govern_predicted']}")
    ece = compute_ece(acc["records"])
    print(f"Accuracy: {acc['accuracy']:.1%} | ECE: {ece:.1%} (lower is better-calibrated)")

    print("\n=== Robustness to paraphrasing ===")
    rob = run_robustness(agent)
    for text, tier, conf in zip(ROBUSTNESS_VARIANTS, rob["tiers"], rob["confidences"]):
        print(f"  '{text[:50]}...' -> {tier} ({conf:.1%})")
    print("PASS" if rob["consistent"] else "FAIL", "- tier is consistent across paraphrases" if rob["consistent"] else "- tier drifted across paraphrases")

    print("\n=== Confidence hedging on an ambiguous case ===")
    amb = run_ambiguity_check(agent)
    print(f"  Predicted {amb['choice']} at {amb['confidence']:.1%} confidence "
          f"({'appropriately uncertain' if amb['appropriately_uncertain'] else 'overconfident on vague input'})")

    latency_ms = sorted(acc["latencies_ms"])
    p50 = latency_ms[len(latency_ms) // 2] if latency_ms else 0.0

    report = {
        "metrics": {"accuracy": acc["accuracy"], "ece": ece, "latency_p50_ms": p50,
                    "robustness_consistent": rob["consistent"],
                    "ambiguous_case_appropriately_uncertain": amb["appropriately_uncertain"]},
    }
    comparison = try_jev_comparison(acc)
    if comparison:
        report["comparison"] = comparison
    else:
        print("\n(No TYPESAFE_API_KEY set - skipping the Jev comparison rather than inventing numbers.)")

    with open(BENCHMARK_OUTPUT, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nWrote {BENCHMARK_OUTPUT} for the leadership dashboard's reliability tab.")

    if acc["accuracy"] < 1.0 or not rob["consistent"]:
        raise SystemExit(1)


# --- pytest entry points (reuse the same functions, need a shared agent) ---
def _pytest_agent():
    import laya
    return laya.Agent(LOCAL_MODEL_PATH)


def test_golden_set_accuracy():
    agent = _pytest_agent()
    acc = run_accuracy(agent)
    assert acc["accuracy"] == 1.0, acc["records"]


def test_calibration_error_is_low():
    agent = _pytest_agent()
    acc = run_accuracy(agent)
    assert compute_ece(acc["records"]) < 0.15


def test_robust_to_paraphrasing():
    agent = _pytest_agent()
    assert run_robustness(agent)["consistent"]


def test_hedges_on_ambiguous_input():
    agent = _pytest_agent()
    assert run_ambiguity_check(agent)["appropriately_uncertain"]


if __name__ == "__main__":
    main()
