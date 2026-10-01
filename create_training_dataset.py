import json
from collections import Counter

from governance_schema import FINE_TUNED_QUESTIONS

# Laya is fine-tuned on exactly these two questions/option sets. Import them
# from governance_schema.py (rather than redefining them here) so the risk
# engine can never ask Laya a question with different option text than what
# it was trained on.
GOVERNANCE_QUESTIONS = FINE_TUNED_QUESTIONS

# Comprehensive scenario matrix covering all risk tiers, domains, and NIST
# governance levels.
COMPREHENSIVE_SCENARIOS = [
    # =========================================================================
    # PROHIBITED / UNACCEPTABLE RISK (EU AI Act Article 5)
    # =========================================================================
    {
        "name": "SocialCredit Evaluator",
        "domain": "Public Sector",
        "desc": "Governmental and commercial joint scoring engine analyzing citizen social behavior, purchase history, and public activity to calculate a trust score for public service access.",
        "notes": "Unmonitored public score tracking. No appeal mechanism.",
        "eu_tier": "Prohibited Risk",
        "nist_level": "Level 1",
    },
    {
        "name": "Workplace Emotion Tracker",
        "domain": "HR & Workforce",
        "desc": "Computer vision system mounted in office space tracking employee facial micro-expressions and eye movements during working hours to infer emotional state and productivity.",
        "notes": "Policies drafted by HR but no employee consent or risk impact assessment executed.",
        "eu_tier": "Prohibited Risk",
        "nist_level": "Level 2",
    },
    {
        "name": "FaceScrape DB Indexer",
        "domain": "Biometrics",
        "desc": "Automated web crawler building a facial recognition database by scraping untargeted video feeds and social media photos without user consent.",
        "notes": "Ad-hoc web scraping tool with unassigned governance ownership.",
        "eu_tier": "Prohibited Risk",
        "nist_level": "Level 1",
    },
    {
        "name": "Classroom Mood Monitor",
        "domain": "Education",
        "desc": "AI camera system deployed in university lecture halls to continuously analyze student emotion and frustration levels during exams.",
        "notes": "Documented pilot evaluation, missing formal enterprise risk register integration.",
        "eu_tier": "Prohibited Risk",
        "nist_level": "Level 2",
    },
    {
        "name": "NeuroNudge Marketing Engine",
        "domain": "Consumer Marketing",
        "desc": "Subliminal audio and behavioral manipulation algorithm targeting vulnerable demographics to induce impulsive financial loan agreements.",
        "notes": "No formal risk assessment or ethics board review conducted.",
        "eu_tier": "Prohibited Risk",
        "nist_level": "Level 1",
    },

    # =========================================================================
    # HIGH RISK (EU AI Act Annex I & III)
    # =========================================================================
    {
        "name": "LendRate Underwriter",
        "domain": "Financial Services",
        "desc": "Automated credit underwriting machine learning model that determines consumer mortgage interest rates, credit card limits, and loan approvals.",
        "notes": "No designated model owner, no bias testing conducted, ad-hoc spreadsheet tracking.",
        "eu_tier": "High Risk",
        "nist_level": "Level 1",
    },
    {
        "name": "OptiHire Resume Ranker",
        "domain": "HR & Recruitment",
        "desc": "Natural language candidate screening algorithm that parses incoming resumes and automatically rejects applicants prior to human HR review.",
        "notes": "Internal policy document exists, but model drift and demographic bias audits are performed irregularly.",
        "eu_tier": "High Risk",
        "nist_level": "Level 2",
    },
    {
        "name": "MedTriage Diagnostics",
        "domain": "Healthcare",
        "desc": "Deep learning diagnostic tool analyzing radiological lung CT scans to categorize urgent oncology cases in emergency rooms.",
        "notes": "Formal enterprise ISO 13485 quality management, appointed medical risk committee, quarterly accuracy reviews.",
        "eu_tier": "High Risk",
        "nist_level": "Level 3",
    },
    {
        "name": "GridGuard Load Controller",
        "domain": "Critical Infrastructure",
        "desc": "Reinforcement learning agent dynamically controlling electrical sub-station voltage switching across regional power grids.",
        "notes": "Real-time telemetry, continuous safety interlocks, automated anomaly shutdown, automated SOC integration.",
        "eu_tier": "High Risk",
        "nist_level": "Level 4",
    },
    {
        "name": "EduScore National Evaluator",
        "domain": "Education",
        "desc": "Algorithmic grading and university placement system determining high school student admission qualification based on historical exam trends.",
        "notes": "Governance owned by academic board, documented review cadence, manual appeal channel established.",
        "eu_tier": "High Risk",
        "nist_level": "Level 3",
    },
    {
        "name": "Recidivism Risk Assessor",
        "domain": "Law Enforcement & Justice",
        "desc": "Predictive scoring algorithm utilized by judicial clerks to estimate defendant bail eligibility and re-offense probabilities.",
        "notes": "Formal review board established, annual algorithmic fairness audits conducted.",
        "eu_tier": "High Risk",
        "nist_level": "Level 3",
    },
    {
        "name": "AccessFace Identification Gateway",
        "domain": "Biometric Authentication",
        "desc": "Biometric 3D facial verification system controlling physical entry into high-security data centers and vault facilities.",
        "notes": "Continuous automated liveness monitoring, integrated Open Policy Agent access rules, audit-logged.",
        "eu_tier": "High Risk",
        "nist_level": "Level 4",
    },

    # =========================================================================
    # LIMITED RISK / SPECIFIC TRANSPARENCY OBLIGATIONS
    # =========================================================================
    {
        "name": "Nexus Retail Chatbot",
        "domain": "Customer Support",
        "desc": "Customer-facing conversational virtual assistant providing store directions, order tracking status, and return policy answers.",
        "notes": "Missing clear AI disclaimers at start of interaction; no assigned product owner.",
        "eu_tier": "Limited Risk",
        "nist_level": "Level 1",
    },
    {
        "name": "BrandAvatar Presenter",
        "domain": "Marketing & Content",
        "desc": "Generative video tool synthesizing photorealistic synthetic human spokespersons for corporate marketing broadcasts.",
        "notes": "Guidelines exist for watermark disclosures, enforced manually by video production staff.",
        "eu_tier": "Limited Risk",
        "nist_level": "Level 2",
    },
    {
        "name": "SupportVoice Synthesizer",
        "domain": "Customer Service",
        "desc": "Text-to-speech audio synthesis engine handling interactive voice response (IVR) phone calls for banking balance inquiries.",
        "notes": "Enterprise transparency mandate: explicit audio disclosures play before call, documented fallback to human agents.",
        "eu_tier": "Limited Risk",
        "nist_level": "Level 3",
    },
    {
        "name": "DocuDraft Generative Assistant",
        "domain": "Enterprise Knowledge Management",
        "desc": "Internal RAG LLM helping employees draft internal project status reports and summarize long intranet documents.",
        "notes": "Automated prompt guardrails active, hallucination rate telemetry monitored, automated compliance logging enabled.",
        "eu_tier": "Limited Risk",
        "nist_level": "Level 4",
    },

    # =========================================================================
    # MINIMAL / NO RISK
    # =========================================================================
    {
        "name": "CyberPhish Header Filter",
        "domain": "IT Cybersecurity",
        "desc": "Inbound corporate email security tool analyzing email headers, SPF records, and URL structures to filter spam and phishing.",
        "notes": "Unmonitored background utility maintained by IT helpdesk team.",
        "eu_tier": "Minimal Risk",
        "nist_level": "Level 1",
    },
    {
        "name": "Inventory Demand Predictor",
        "domain": "Supply Chain",
        "desc": "Time-series forecasting model predicting monthly warehouse office supply requirements based on seasonal purchase trends.",
        "notes": "Managed by logistics lead with standard quarterly stock re-order reviews.",
        "eu_tier": "Minimal Risk",
        "nist_level": "Level 2",
    },
    {
        "name": "CodeLint Syntax Auto-Fixer",
        "domain": "Software Engineering",
        "desc": "Internal developer tooling that formats Python scripts and fixes PEP8 syntax indentation prior to Git commits.",
        "notes": "Enterprise software development lifecycle standards, mandatory peer code reviews, automated pipeline checks.",
        "eu_tier": "Minimal Risk",
        "nist_level": "Level 3",
    },
    {
        "name": "SQL Query Optimizer",
        "domain": "Database Operations",
        "desc": "Heuristic execution planner that re-routes complex database query workloads to minimize server memory latency.",
        "notes": "Continuous database performance telemetry, automated failover routing, fully automated operational dashboard.",
        "eu_tier": "Minimal Risk",
        "nist_level": "Level 4",
    },
    {
        "name": "Meeting Transcribe-Lite",
        "domain": "Internal Productivity",
        "desc": "Local speech-to-text utility transcribing internal team standup recordings and extracting bulleted action items.",
        "notes": "Ad-hoc local software installation with no formal enterprise governance policy.",
        "eu_tier": "Minimal Risk",
        "nist_level": "Level 1",
    },
]

SMOOTH = 0.05  # soft targets: 0.95 on the true label, remainder spread over the other options


def make_gold(qdef, answer):
    keys = list(qdef["criteria"].keys())
    assert answer in keys, f"{answer!r} not in {keys}"
    k = len(keys)
    probs = {key: (1.0 - SMOOTH) if key == answer else SMOOTH / (k - 1) for key in keys}
    return {"label": answer, "probabilities": probs}


def generate_laya_dataset(output_filename="train_dataset.jsonl"):
    print("Formatting synthetic enterprise scenarios into Laya JSONL format...")
    formatted_dataset = []

    for i, item in enumerate(COMPREHENSIVE_SCENARIOS):
        answers = {"eu_risk_tier": item["eu_tier"], "nist_govern": item["nist_level"]}
        laya_record = {
            "id": f"gov_{i:04d}",
            "workflow": "ai_governance",
            "state": {
                "system_name": item["name"],
                "description": f"[{item['domain']}] {item['desc']}",
                "governance_notes": item["notes"],
            },
            "questions": GOVERNANCE_QUESTIONS,
            "gold": {qid: make_gold(GOVERNANCE_QUESTIONS[qid], ans) for qid, ans in answers.items()},
        }
        formatted_dataset.append(laya_record)

    with open(output_filename, "w", encoding="utf-8") as f:
        for record in formatted_dataset:
            f.write(json.dumps(record) + "\n")

    print(f"Dataset creation complete: '{output_filename}' generated ({len(formatted_dataset)} records).")

    eu_counts = Counter(r["gold"]["eu_risk_tier"]["label"] for r in formatted_dataset)
    nist_counts = Counter(r["gold"]["nist_govern"]["label"] for r in formatted_dataset)
    print("\n--- EU AI Act Distribution ---")
    for tier, count in eu_counts.items():
        print(f"  - {tier}: {count}")
    print("\n--- NIST AI RMF GOVERN Distribution ---")
    for level, count in sorted(nist_counts.items()):
        print(f"  - {level}: {count}")


if __name__ == "__main__":
    generate_laya_dataset("train_dataset.jsonl")
