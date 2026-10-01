package ai_governance

import rego.v1

# ============================================================================
# Inputs this policy expects (built by laya_risk_engine.py):
#
# {
#   "eu_triggers": {"financial_credit": bool, "hr_recruitment": bool,
#                    "biometrics": bool, "critical_infrastructure": bool},
#   "nist_subchecks": {
#       "govern":  {"ownership": "Level N", "policies": "Level N",
#                   "training": "Level N", "legal": "Level N"},
#       "map":     {"context": "Level N", "data_lineage": "Level N"},
#       "measure": {"testing": "Level N", "fairness": "Level N"},
#       "manage":  {"incident_response": "Level N", "monitoring": "Level N"}
#   },
#   "semantic": {
#       "eu_risk_tier": "Prohibited Risk|High Risk|Limited Risk|Minimal Risk",
#       "nist_govern": "Level N", "nist_map": "Level N",
#       "nist_measure": "Level N", "nist_manage": "Level N",
#       "confidence": {"eu_risk_tier": 0.0-1.0, "nist_govern": 0.0-1.0}
#   }
# }
#
# NOTE: weights below MUST match governance_schema.NIST_SUBCHECKS. This file
# cannot import that module, so any weight change must be made in both places.
#
# This file targets Rego v1 syntax (the `import rego.v1` line requires the
# `if` keyword before every rule body). If your OPA binary is older than
# v0.59, drop the import line and remove every `if` immediately before a
# `{` below to get the equivalent v0-syntax file.
# ============================================================================

default requires_conformity_assessment := false
default undisclosed_risk := false
default low_confidence := false
default govern_disagreement := false
default map_disagreement := false
default measure_disagreement := false
default manage_disagreement := false
default any_disagreement := false
default valid_nist_baseline := false
default is_approved := false

# ---------------------------------------------------------------------------
# 1. EU AI Act Annex III deterministic gate (developer disclosures)
# ---------------------------------------------------------------------------
requires_conformity_assessment if input.eu_triggers.financial_credit == true
requires_conformity_assessment if input.eu_triggers.hr_recruitment == true
requires_conformity_assessment if input.eu_triggers.biometrics == true
requires_conformity_assessment if input.eu_triggers.critical_infrastructure == true

# Disclosure can only escalate to High Risk; it never downgrades what Laya
# independently concluded.
final_eu_tier := "High Risk" if requires_conformity_assessment
final_eu_tier := input.semantic.eu_risk_tier if not requires_conformity_assessment

# Laya thinks this is High/Prohibited Risk but no trigger box was checked --
# flag for the risk team rather than silently trusting either side.
undisclosed_risk if {
	not requires_conformity_assessment
	input.semantic.eu_risk_tier == "High Risk"
}

undisclosed_risk if {
	not requires_conformity_assessment
	input.semantic.eu_risk_tier == "Prohibited Risk"
}

# ---------------------------------------------------------------------------
# 2. NIST level <-> numeric score
# ---------------------------------------------------------------------------
level_to_score(level) := 1.0 if level == "Level 1"
level_to_score(level) := 2.0 if level == "Level 2"
level_to_score(level) := 3.0 if level == "Level 3"
level_to_score(level) := 4.0 if level == "Level 4"
default level_to_score(_) := 1.0

# ---------------------------------------------------------------------------
# 3. Deterministic composite per NIST function (from the developer questionnaire)
# ---------------------------------------------------------------------------
govern_composite := score if {
	o := level_to_score(input.nist_subchecks.govern.ownership)
	p := level_to_score(input.nist_subchecks.govern.policies)
	t := level_to_score(input.nist_subchecks.govern.training)
	l := level_to_score(input.nist_subchecks.govern.legal)
	score := (o * 0.30) + (p * 0.30) + (t * 0.20) + (l * 0.20)
}

map_composite := score if {
	c := level_to_score(input.nist_subchecks.map.context)
	d := level_to_score(input.nist_subchecks.map.data_lineage)
	score := (c * 0.50) + (d * 0.50)
}

measure_composite := score if {
	tst := level_to_score(input.nist_subchecks.measure.testing)
	fr := level_to_score(input.nist_subchecks.measure.fairness)
	score := (tst * 0.50) + (fr * 0.50)
}

manage_composite := score if {
	ir := level_to_score(input.nist_subchecks.manage.incident_response)
	mo := level_to_score(input.nist_subchecks.manage.monitoring)
	score := (ir * 0.50) + (mo * 0.50)
}

# ---------------------------------------------------------------------------
# 4. Blend with Laya's semantic read.
#    GOVERN is the one function Laya is fine-tuned on today: take the more
#    conservative (lower) of the deterministic and semantic scores.
#    MAP/MEASURE/MANAGE are zero-shot until retrained on gold labels for
#    them, so the questionnaire composite is authoritative; semantic output
#    is only used to raise a disagreement flag for human review.
# ---------------------------------------------------------------------------
govern_semantic_score := level_to_score(input.semantic.nist_govern)

govern_final_score := govern_composite if govern_composite <= govern_semantic_score
govern_final_score := govern_semantic_score if govern_semantic_score < govern_composite

govern_disagreement if {
	d := govern_composite - govern_semantic_score
	d >= 2
}

govern_disagreement if {
	d := govern_semantic_score - govern_composite
	d >= 2
}

map_final_score := map_composite
measure_final_score := measure_composite
manage_final_score := manage_composite

map_disagreement if {
	d := map_composite - level_to_score(input.semantic.nist_map)
	d >= 2
}

map_disagreement if {
	d := level_to_score(input.semantic.nist_map) - map_composite
	d >= 2
}

measure_disagreement if {
	d := measure_composite - level_to_score(input.semantic.nist_measure)
	d >= 2
}

measure_disagreement if {
	d := level_to_score(input.semantic.nist_measure) - measure_composite
	d >= 2
}

manage_disagreement if {
	d := manage_composite - level_to_score(input.semantic.nist_manage)
	d >= 2
}

manage_disagreement if {
	d := level_to_score(input.semantic.nist_manage) - manage_composite
	d >= 2
}

any_disagreement if govern_disagreement
any_disagreement if map_disagreement
any_disagreement if measure_disagreement
any_disagreement if manage_disagreement

# ---------------------------------------------------------------------------
# 5. Confidence gate - keep threshold in sync with
#    governance_schema.CONFIDENCE_THRESHOLD (0.85)
# ---------------------------------------------------------------------------
low_confidence if input.semantic.confidence.eu_risk_tier < 0.85
low_confidence if input.semantic.confidence.nist_govern < 0.85

# ---------------------------------------------------------------------------
# 6. NIST baseline required for automated approval - keep in sync with
#    governance_schema.BASELINE_COMPOSITE (2.5)
# ---------------------------------------------------------------------------
valid_nist_baseline if {
	govern_final_score >= 2.5
	measure_final_score >= 2.5
}

is_approved if {
	final_eu_tier == "Minimal Risk"
	valid_nist_baseline
	not low_confidence
	not any_disagreement
}

is_approved if {
	final_eu_tier == "Limited Risk"
	valid_nist_baseline
	not low_confidence
	not any_disagreement
}

# ---------------------------------------------------------------------------
# 7. Action priority - the six rules below are mutually exclusive by
#    construction (each guards on the previous rules' negated condition),
#    so exactly one should ever be true for a given input.
# ---------------------------------------------------------------------------
action_priority := "BLOCKED - Prohibited Under EU AI Act Article 5" if {
	final_eu_tier == "Prohibited Risk"
}

action_priority := "Manual Compliance Review (Low Confidence)" if {
	final_eu_tier != "Prohibited Risk"
	low_confidence
}

action_priority := "CRITICAL - Immediate Remediation" if {
	final_eu_tier != "Prohibited Risk"
	not low_confidence
	final_eu_tier == "High Risk"
	not valid_nist_baseline
}

action_priority := "High - Requires Conformity Assessment" if {
	final_eu_tier != "Prohibited Risk"
	not low_confidence
	final_eu_tier == "High Risk"
	valid_nist_baseline
}

action_priority := "Escalate - Review Required" if {
	final_eu_tier != "Prohibited Risk"
	not low_confidence
	final_eu_tier != "High Risk"
	any_disagreement
}

action_priority := "Monitor" if {
	final_eu_tier != "Prohibited Risk"
	not low_confidence
	final_eu_tier != "High Risk"
	not any_disagreement
}

# ---------------------------------------------------------------------------
# 8. Full decision trace - this is what the dashboard drill-down renders.
# ---------------------------------------------------------------------------
decision := {
	"final_eu_tier": final_eu_tier,
	"requires_conformity_assessment": requires_conformity_assessment,
	"undisclosed_risk": undisclosed_risk,
	"govern_composite": govern_composite,
	"govern_semantic_score": govern_semantic_score,
	"govern_final_score": govern_final_score,
	"govern_disagreement": govern_disagreement,
	"map_final_score": map_final_score,
	"map_disagreement": map_disagreement,
	"measure_final_score": measure_final_score,
	"measure_disagreement": measure_disagreement,
	"manage_final_score": manage_final_score,
	"manage_disagreement": manage_disagreement,
	"any_disagreement": any_disagreement,
	"low_confidence": low_confidence,
	"valid_nist_baseline": valid_nist_baseline,
	"is_approved": is_approved,
	"action_priority": action_priority,
}
