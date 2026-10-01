"""
Single source of truth for the AI governance program.

Every other file (the developer intake form, the Rego policy, the Laya
risk engine, the dashboard, and the training-set generator) imports its
question text, option text, and NIST weights from here. Nothing about
governance content should be hand-duplicated in more than one place.

IMPORTANT - keep this in sync with two things you cannot enforce with code:
  1. ai_governance.rego hard-codes the same NIST_SUBCHECKS weights and the
     same CONFIDENCE_THRESHOLD / BASELINE_COMPOSITE values as constants,
     because Rego cannot import a Python module. If you change a weight
     here, change it in the .rego file too (search for "keep in sync").
  2. FINE_TUNED_QUESTIONS below must match exactly what
     create_training_dataset.py used to fine-tune Laya. Laya's
     typed-decisions protocol scores whatever option text it is given at
     inference time, so changing option wording or the option set here
     without retraining silently moves the model off its fine-tuning.
     MAP/MEASURE/MANAGE are NOT in the current training set (only
     eu_risk_tier and nist_govern are) -- treat their semantic output as
     advisory/zero-shot until you add gold labels for them and retrain.
"""

# ---------------------------------------------------------------------------
# 1. EU AI Act Annex III deterministic triggers
#    These are the developer's own disclosures. They can only ESCALATE a
#    system to High Risk; the engine never uses them to downgrade what
#    Laya's semantic classifier independently concludes.
# ---------------------------------------------------------------------------
EU_TRIGGERS = {
    "financial_credit": {
        "label": "Financial Credit Scoring / Loan Eligibility",
        "eu_ref": "Annex III, Para 5",
    },
    "hr_recruitment": {
        "label": "HR, Candidate Evaluation, or Resume Parsing",
        "eu_ref": "Annex III, Para 4",
    },
    "biometrics": {
        "label": "Remote Biometric Identification or Categorisation",
        "eu_ref": "Annex III, Para 1",
    },
    "critical_infrastructure": {
        "label": "Management of Critical Infrastructure",
        "eu_ref": "Annex III, Para 2",
    },
}

# ---------------------------------------------------------------------------
# 2. Laya questions - split into what the model is actually fine-tuned on
#    vs. what it is answering zero-shot today.
# ---------------------------------------------------------------------------
FINE_TUNED_QUESTIONS = {
    "eu_risk_tier": {
        "type": "choice",
        "instructions": "Strictly classify the EU AI Act risk tier.",
        "criteria": {
            "Prohibited Risk": "Systems that violate fundamental rights (e.g., social scoring, real-time public biometric identification, cognitive behavioral manipulation of vulnerable groups, emotion recognition in workplaces/schools, untargeted facial scraping).",
            "High Risk": "Systems used in safety components, critical infrastructure, credit/loan underwriting, recruitment/HR, education admissions, healthcare diagnosis, law enforcement, or biometrics.",
            "Limited Risk": "Systems subject to specific transparency obligations such as customer-facing chatbots, synthetic media generation (deepfakes), or AI video avatars.",
            "Minimal Risk": "Non-sensitive operational systems like spam filtering, inventory optimization, database query routing, code completion, or IT infrastructure monitoring.",
        },
    },
    "nist_govern": {
        "type": "choice",
        "instructions": "Evaluate the NIST AI RMF GOVERN maturity tier.",
        "criteria": {
            "Level 1": "Ad-hoc/Informal: No documented AI policies, unassigned risk ownership, or untracked models.",
            "Level 2": "Risk-Informed: Policies defined at project level, but inconsistent enterprise governance or audit cadences.",
            "Level 3": "Repeatable: Enterprise-wide documented policies, assigned risk owners, formal risk registers, and regular audits.",
            "Level 4": "Adaptive: Continuous automated compliance monitoring, automated guardrails, and real-time risk mitigation.",
        },
    },
}

# Advisory only: Laya has not been fine-tuned on these yet (no gold labels
# in the current training set). The risk engine uses them for a
# disagreement check, never as the authoritative score.
ADVISORY_QUESTIONS = {
    "nist_map": {
        "type": "choice",
        "instructions": "Evaluate against the NIST AI RMF MAP function (context and data lineage).",
        "criteria": {
            "Level 1": "Informal: system context, data lineage, and downstream impacts are undocumented.",
            "Level 2": "Risk-Informed: basic internal context and impact assessed informally.",
            "Level 3": "Repeatable: formal impact assessment completed and data dependencies mapped.",
            "Level 4": "Adaptive: systemic risks and data lineage continuously mapped via automated telemetry.",
        },
    },
    "nist_measure": {
        "type": "choice",
        "instructions": "Evaluate against the NIST AI RMF MEASURE function (testing and fairness).",
        "criteria": {
            "Level 1": "Informal: no formal testing, bias evaluation, or metric tracking.",
            "Level 2": "Risk-Informed: manual, irregular accuracy or bias testing.",
            "Level 3": "Repeatable: documented test suites, routine red-teaming, and bias tracking.",
            "Level 4": "Adaptive: real-time drift detection and automated CI/CD guardrails.",
        },
    },
    "nist_manage": {
        "type": "choice",
        "instructions": "Evaluate against the NIST AI RMF MANAGE function (incident response and monitoring).",
        "criteria": {
            "Level 1": "Informal: no incident response plan or active monitoring.",
            "Level 2": "Risk-Informed: drafted incident response plans exist but are rarely tested.",
            "Level 3": "Repeatable: active monitoring with a documented, exercised incident response plan.",
            "Level 4": "Adaptive: automated kill-switches and dynamic real-time mitigation.",
        },
    },
}

LAYA_QUESTIONS = {**FINE_TUNED_QUESTIONS, **ADVISORY_QUESTIONS}

# ---------------------------------------------------------------------------
# 3. Deterministic questionnaire sub-checks that feed the Rego composite
#    score for each NIST function. Text is deliberately mirrored against
#    the Laya criteria above so a developer and the model are being asked
#    about the same maturity ladder in different words.
# ---------------------------------------------------------------------------
NIST_SUBCHECKS = {
    "govern": {
        "weights": {"ownership": 0.30, "policies": 0.30, "training": 0.20, "legal": 0.20},
        "items": {
            "ownership": {
                "question": "Is there an explicitly designated owner accountable for this system? (GOVERN 1.2)",
                "levels": [
                    "Level 1: Unassigned or unclear",
                    "Level 2: Informal engineering lead",
                    "Level 3: Named owner formally signed off",
                    "Level 4: Automated accountability tracking in a GRC tool",
                ],
            },
            "policies": {
                "question": "Are this system's risks documented against enterprise AI policy? (GOVERN 2.1)",
                "levels": [
                    "Level 1: No policies documented",
                    "Level 2: Informal team-level guidelines",
                    "Level 3: Mapped to formal enterprise policy",
                    "Level 4: Continuous automated policy-enforcement guardrails",
                ],
            },
            "training": {
                "question": "Has the team completed AI risk / bias training for this system? (GOVERN 3.1)",
                "levels": [
                    "Level 1: No specific training",
                    "Level 2: Informal peer reviews only",
                    "Level 3: Formal training completed and logged",
                    "Level 4: Embedded risk champions on the team",
                ],
            },
            "legal": {
                "question": "Has this system undergone a legal / privacy compliance review? (GOVERN 1.1)",
                "levels": [
                    "Level 1: No legal review",
                    "Level 2: Initial consultation only",
                    "Level 3: Formal legal approval secured",
                    "Level 4: Continuous automated privacy scrubbing (e.g., Presidio)",
                ],
            },
        },
    },
    "map": {
        "weights": {"context": 0.50, "data_lineage": 0.50},
        "items": {
            "context": {
                "question": "Is the system's business context and downstream use documented?",
                "levels": [
                    "Level 1: Undocumented",
                    "Level 2: Basic internal notes only",
                    "Level 3: Formal impact assessment on file",
                    "Level 4: Continuously updated via automated telemetry",
                ],
            },
            "data_lineage": {
                "question": "Are the system's upstream data sources and lineage documented?",
                "levels": [
                    "Level 1: Unknown / untracked",
                    "Level 2: Partially documented",
                    "Level 3: Fully mapped and version-controlled",
                    "Level 4: Automated lineage tracking with alerting",
                ],
            },
        },
    },
    "measure": {
        "weights": {"testing": 0.50, "fairness": 0.50},
        "items": {
            "testing": {
                "question": "How is this system tested for accuracy and robustness?",
                "levels": [
                    "Level 1: No formal testing",
                    "Level 2: Manual, ad-hoc testing",
                    "Level 3: Standardized pre-deployment test suite",
                    "Level 4: Automated CI/CD pipeline blocking on regressions",
                ],
            },
            "fairness": {
                "question": "How is this system tested for demographic bias or fairness?",
                "levels": [
                    "Level 1: Never assessed",
                    "Level 2: Informal one-off review",
                    "Level 3: Documented fairness audit completed",
                    "Level 4: Continuous automated fairness monitoring",
                ],
            },
        },
    },
    "manage": {
        "weights": {"incident_response": 0.50, "monitoring": 0.50},
        "items": {
            "incident_response": {
                "question": "Is there a documented, exercised incident response plan for this system?",
                "levels": [
                    "Level 1: No plan",
                    "Level 2: Drafted but untested",
                    "Level 3: Documented and exercised (tabletop or live)",
                    "Level 4: Automated kill-switch / rollback in place",
                ],
            },
            "monitoring": {
                "question": "Is the system monitored in production for drift or failures?",
                "levels": [
                    "Level 1: No monitoring",
                    "Level 2: Manual, ad-hoc checks",
                    "Level 3: Dashboarded monitoring reviewed on a cadence",
                    "Level 4: Real-time automated drift detection with alerting",
                ],
            },
        },
    },
}

DISPLAY_MAPPING = {
    "govern": {
        "Level 1": "\U0001F534 Unmanaged (No Owner)",
        "Level 2": "\U0001F7E0 Developing (Informal)",
        "Level 3": "\U0001F7E1 Managed (Repeatable)",
        "Level 4": "\U0001F7E2 Optimized (Continuous)",
    },
    "map": {
        "Level 1": "\U0001F534 Unmapped (No Data Lineage)",
        "Level 2": "\U0001F7E0 Partial (Basic Context)",
        "Level 3": "\U0001F7E1 Mapped (Fully Documented)",
        "Level 4": "\U0001F7E2 Advanced (Dynamic Tracking)",
    },
    "measure": {
        "Level 1": "\U0001F534 Unverified (Zero Audits)",
        "Level 2": "\U0001F7E0 Basic (Manual Tests)",
        "Level 3": "\U0001F7E1 Standardized (Fairness Audited)",
        "Level 4": "\U0001F7E2 Automated (Continuous CI/CD)",
    },
    "manage": {
        "Level 1": "\U0001F534 Deficient (No Incident Plan)",
        "Level 2": "\U0001F7E0 Manual (Ad-Hoc Monitors)",
        "Level 3": "\U0001F7E1 Controlled (Runbooks Active)",
        "Level 4": "\U0001F7E2 Automated (Real-Time Guardrails)",
    },
}

# ---------------------------------------------------------------------------
# 4. Thresholds - MUST match the constants of the same name in
#    ai_governance.rego (search "keep in sync").
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.85
BASELINE_COMPOSITE = 2.5
DISAGREEMENT_DELTA = 2.0

_LEVEL_TO_SCORE = {"Level 1": 1.0, "Level 2": 2.0, "Level 3": 3.0, "Level 4": 4.0}
_SCORE_TO_LEVEL = {v: k for k, v in _LEVEL_TO_SCORE.items()}


def level_to_score(level: str) -> float:
    """Same mapping as level_to_score() in ai_governance.rego."""
    return _LEVEL_TO_SCORE.get(level, 1.0)


def score_to_level(score: float) -> str:
    """Round-half-up to the nearest level, clipped to Level 1..4."""
    rounded = max(1, min(4, round(score)))
    return f"Level {rounded}"


def composite_score(function: str, subcheck_levels: dict) -> float:
    """Weighted composite for one NIST function, using NIST_SUBCHECKS weights."""
    weights = NIST_SUBCHECKS[function]["weights"]
    total = 0.0
    for key, weight in weights.items():
        level = subcheck_levels.get(key)
        if level is None:
            raise ValueError(f"missing sub-check '{key}' for NIST function '{function}'")
        total += level_to_score(level) * weight
    return round(total, 4)
