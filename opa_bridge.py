"""
Evaluates the ai_governance policy for one asset.

Tries the real OPA CLI first (`opa eval`), so ai_governance.rego stays the
single source of truth for the policy logic. If the `opa` binary isn't on
PATH, falls back to `_python_fallback`, a line-for-line mirror of the .rego
file kept in this same file so the two are easy to diff against each other.

I could not run the actual `opa` binary while writing this (no network in
the sandbox), so `_python_fallback` has not been cross-checked against a
live OPA evaluation of ai_governance.rego -- it was logic-tested in
isolation instead. ai_governance.rego targets Rego v1 syntax (requires
`import rego.v1` and explicit `if` keywords); if your OPA errors with exit
code 2, that's almost always a v0/v1 syntax mismatch -- see the error
message `evaluate()` raises for the fix. Before trusting the fallback in
production, compare it against a real OPA run for a handful of cases:

    opa eval -f json -d ai_governance.rego -I data.ai_governance.decision
    # (paste a JSON input on stdin, Ctrl-D to run)

and compare the result against evaluate(sample_input, use_opa=False).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REGO_PATH = Path(__file__).parent / "ai_governance.rego"
CONFIDENCE_THRESHOLD = 0.85
BASELINE_COMPOSITE = 2.5
DISAGREEMENT_DELTA = 2.0

_LEVEL_TO_SCORE = {"Level 1": 1.0, "Level 2": 2.0, "Level 3": 3.0, "Level 4": 4.0}


class PolicyInputError(ValueError):
    """Raised when the input dict is missing a field the policy needs."""


def evaluate(policy_input: dict, use_opa: bool = True) -> dict:
    """Returns the same shape as the .rego file's `decision` object."""
    if use_opa and shutil.which("opa"):
        try:
            return _evaluate_with_opa(policy_input)
        except subprocess.CalledProcessError as exc:
            # exit code 1 = eval/runtime error, 2 = compile/parse error.
            # OPA's real diagnostic is on stderr -- never swallow it.
            raise RuntimeError(
                "OPA CLI failed to evaluate ai_governance.rego "
                f"(exit {exc.returncode}).\n--- opa stderr ---\n{exc.stderr}"
                "\n--- opa stdout ---\n" + (exc.stdout or "(empty)") + "\n"
                "Common cause: your OPA binary defaults to Rego v1 syntax "
                "but the .rego file is older v0-style (missing 'if' keywords) "
                "or vice versa. Run `opa eval -f json -d ai_governance.rego "
                "-I data.ai_governance.decision` by hand with a sample input "
                "on stdin to reproduce this directly."
            ) from exc
        except (json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(
                f"OPA ran but its output wasn't the shape expected ({exc}). "
                "This usually means the 'decision' rule in ai_governance.rego "
                "is undefined for this input (missing a required field) "
                "rather than a syntax error."
            ) from exc
    return _python_fallback(policy_input)


def _evaluate_with_opa(policy_input: dict) -> dict:
    proc = subprocess.run(
        ["opa", "eval", "-f", "json", "-d", str(REGO_PATH),
         "-I", "data.ai_governance.decision"],
        input=json.dumps(policy_input),
        capture_output=True, text=True, check=True,
    )
    result = json.loads(proc.stdout)
    return result["result"][0]["expressions"][0]["value"]


def _level(level_str) -> float:
    return _LEVEL_TO_SCORE.get(level_str, 1.0)


def _require(d: dict, path: str):
    node = d
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise PolicyInputError(f"policy input missing required field '{path}'")
        node = node[part]
    return node


def _python_fallback(inp: dict) -> dict:
    """Mirrors ai_governance.rego exactly. See module docstring for caveats."""
    triggers = _require(inp, "eu_triggers")
    subchecks = _require(inp, "nist_subchecks")
    semantic = _require(inp, "semantic")

    requires_conformity = any(triggers.get(k) is True for k in
                               ("financial_credit", "hr_recruitment", "biometrics",
                                "critical_infrastructure"))

    semantic_tier = _require(semantic, "eu_risk_tier")
    final_eu_tier = "High Risk" if requires_conformity else semantic_tier
    undisclosed_risk = (not requires_conformity) and semantic_tier in (
        "High Risk", "Prohibited Risk")

    govern_composite = (
        _level(subchecks["govern"]["ownership"]) * 0.30
        + _level(subchecks["govern"]["policies"]) * 0.30
        + _level(subchecks["govern"]["training"]) * 0.20
        + _level(subchecks["govern"]["legal"]) * 0.20
    )
    map_composite = (
        _level(subchecks["map"]["context"]) * 0.50
        + _level(subchecks["map"]["data_lineage"]) * 0.50
    )
    measure_composite = (
        _level(subchecks["measure"]["testing"]) * 0.50
        + _level(subchecks["measure"]["fairness"]) * 0.50
    )
    manage_composite = (
        _level(subchecks["manage"]["incident_response"]) * 0.50
        + _level(subchecks["manage"]["monitoring"]) * 0.50
    )

    govern_semantic_score = _level(semantic["nist_govern"])
    govern_final_score = min(govern_composite, govern_semantic_score)
    govern_disagreement = abs(govern_composite - govern_semantic_score) >= DISAGREEMENT_DELTA

    map_disagreement = abs(map_composite - _level(semantic.get("nist_map", "Level 1"))) >= DISAGREEMENT_DELTA
    measure_disagreement = abs(measure_composite - _level(semantic.get("nist_measure", "Level 1"))) >= DISAGREEMENT_DELTA
    manage_disagreement = abs(manage_composite - _level(semantic.get("nist_manage", "Level 1"))) >= DISAGREEMENT_DELTA
    any_disagreement = any([govern_disagreement, map_disagreement, measure_disagreement, manage_disagreement])

    confidence = semantic.get("confidence", {})
    low_confidence = (
        confidence.get("eu_risk_tier", 1.0) < CONFIDENCE_THRESHOLD
        or confidence.get("nist_govern", 1.0) < CONFIDENCE_THRESHOLD
    )

    valid_nist_baseline = govern_final_score >= BASELINE_COMPOSITE and measure_composite >= BASELINE_COMPOSITE
    is_approved = (
        final_eu_tier in ("Minimal Risk", "Limited Risk")
        and valid_nist_baseline
        and not low_confidence
        and not any_disagreement
    )

    if final_eu_tier == "Prohibited Risk":
        action_priority = "BLOCKED - Prohibited Under EU AI Act Article 5"
    elif low_confidence:
        action_priority = "Manual Compliance Review (Low Confidence)"
    elif final_eu_tier == "High Risk" and not valid_nist_baseline:
        action_priority = "CRITICAL - Immediate Remediation"
    elif final_eu_tier == "High Risk":
        action_priority = "High - Requires Conformity Assessment"
    elif any_disagreement:
        action_priority = "Escalate - Review Required"
    else:
        action_priority = "Monitor"

    return {
        "final_eu_tier": final_eu_tier,
        "requires_conformity_assessment": requires_conformity,
        "undisclosed_risk": undisclosed_risk,
        "govern_composite": round(govern_composite, 4),
        "govern_semantic_score": govern_semantic_score,
        "govern_final_score": govern_final_score,
        "govern_disagreement": govern_disagreement,
        "map_final_score": round(map_composite, 4),
        "map_disagreement": map_disagreement,
        "measure_final_score": round(measure_composite, 4),
        "measure_disagreement": measure_disagreement,
        "manage_final_score": round(manage_composite, 4),
        "manage_disagreement": manage_disagreement,
        "any_disagreement": any_disagreement,
        "low_confidence": low_confidence,
        "valid_nist_baseline": valid_nist_baseline,
        "is_approved": is_approved,
        "action_priority": action_priority,
    }
