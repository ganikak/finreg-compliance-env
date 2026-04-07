"""
Task catalogue for FinReg Compliance Env.

Each task is a dict describing:
  - name
  - difficulty
  - description
  - transaction  (the scenario)
  - correct_decision
  - correct_risks
  - correct_regulations
  - grader        callable(action) -> float [0.0, 1.0]
"""

from __future__ import annotations

from typing import Any, Dict, List

from models import (
    ComplianceAction,
    ComplianceDecision,
    RegulationFramework,
    RegulatoryAlert,
    RiskLevel,
    Transaction,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _risk_overlap(identified: List[str], expected: List[str]) -> float:
    """Partial credit for identified risks (case-insensitive keyword match)."""
    if not expected:
        return 1.0
    identified_lower = " ".join(identified).lower()
    matched = sum(
        1 for r in expected if any(kw in identified_lower for kw in r.lower().split())
    )
    return matched / len(expected)


def _regulation_overlap(cited: List[RegulationFramework], expected: List[RegulationFramework]) -> float:
    if not expected:
        return 1.0
    matched = sum(1 for r in expected if r in cited)
    return matched / len(expected)


def _reasoning_quality(reasoning: str, keywords: List[str]) -> float:
    """Score reasoning quality by presence of domain keywords."""
    if not reasoning or not keywords:
        return 0.0
    lower = reasoning.lower()
    hits = sum(1 for kw in keywords if kw in lower)
    return min(hits / len(keywords), 1.0)


# ---------------------------------------------------------------------------
# TASK 1 – EASY
# Obvious money-laundering smurfing pattern
# ---------------------------------------------------------------------------

TASK_1_TRANSACTION = Transaction(
    transaction_id="TXN-001-EASY",
    amount_usd=9_800.0,
    sender_name="John Martinez",
    sender_country="United States",
    sender_account_type="individual",
    receiver_name="Shell Holdings Ltd",
    receiver_country="Cayman Islands",
    receiver_account_type="corporate",
    transaction_type="wire",
    purpose="Consulting services",
    velocity_24h=4,
    velocity_amount_24h=38_200.0,
    is_pep=False,
    is_sanctioned_country=False,
    structuring_flag=True,
    unusual_hours=False,
    new_relationship=True,
    prior_sar_count=1,
)

TASK_1_ALERTS = [
    RegulatoryAlert(
        framework=RegulationFramework.BSA,
        severity=RiskLevel.HIGH,
        description="Multiple transactions just below $10,000 CTR threshold — possible structuring (smurfing).",
        rule_id="BSA-31-CFR-1010.314",
    ),
    RegulatoryAlert(
        framework=RegulationFramework.FATF,
        severity=RiskLevel.MEDIUM,
        description="Destination is a high-risk jurisdiction (Cayman Islands) with shell company characteristics.",
        rule_id="FATF-R13",
    ),
]

TASK_1_CORRECT_RISKS = ["structuring", "smurfing", "ctr", "threshold", "shell", "cayman", "velocity"]
TASK_1_CORRECT_REGULATIONS = [RegulationFramework.BSA, RegulationFramework.FATF]
TASK_1_REASONING_KEYWORDS = ["structuring", "10000", "ctr", "sar", "suspicious", "shell"]


def grade_task_1(action: ComplianceAction) -> float:
    """
    Easy task grader — clear structuring / AML flag scenario.
    Correct answer: FLAG_AML or ESCALATE (not APPROVE or REJECT without SAR).
    """
    score = 0.0

    # Decision correctness (0.40)
    if action.decision in (ComplianceDecision.FLAG_AML, ComplianceDecision.ESCALATE):
        score += 0.40
    elif action.decision == ComplianceDecision.REJECT:
        score += 0.20  # partial — wrong process (should file SAR, not just reject)
    elif action.decision == ComplianceDecision.REQUEST_INFO:
        score += 0.10

    # Risk identification (0.30)
    score += 0.30 * _risk_overlap(action.identified_risks, TASK_1_CORRECT_RISKS)

    # Regulations cited (0.15)
    score += 0.15 * _regulation_overlap(action.regulation_cited, TASK_1_CORRECT_REGULATIONS)

    # Reasoning quality (0.15)
    score += 0.15 * _reasoning_quality(action.reasoning, TASK_1_REASONING_KEYWORDS)

    return round(min(score, 1.0), 4)


# ---------------------------------------------------------------------------
# TASK 2 – MEDIUM
# Politically Exposed Person + OFAC sanctions edge case
# ---------------------------------------------------------------------------

TASK_2_TRANSACTION = Transaction(
    transaction_id="TXN-002-MEDIUM",
    amount_usd=250_000.0,
    sender_name="Viktor Volkov",
    sender_country="Russia",
    sender_account_type="individual",
    receiver_name="Global Energy Partners AG",
    receiver_country="Switzerland",
    receiver_account_type="corporate",
    transaction_type="swift",
    purpose="Investment in renewable energy project",
    velocity_24h=1,
    velocity_amount_24h=250_000.0,
    is_pep=True,
    is_sanctioned_country=True,
    structuring_flag=False,
    unusual_hours=False,
    new_relationship=True,
    prior_sar_count=0,
)

TASK_2_ALERTS = [
    RegulatoryAlert(
        framework=RegulationFramework.OFAC,
        severity=RiskLevel.CRITICAL,
        description="Sender country (Russia) subject to OFAC sectoral sanctions (SDN list check required). Transaction may violate Executive Order 13662.",
        rule_id="OFAC-EO-13662",
    ),
    RegulatoryAlert(
        framework=RegulationFramework.FATF,
        severity=RiskLevel.HIGH,
        description="Sender identified as Politically Exposed Person (PEP). Enhanced Due Diligence (EDD) required.",
        rule_id="FATF-R12",
    ),
]

TASK_2_CORRECT_RISKS = ["pep", "politically exposed", "sanctions", "ofac", "russia", "sdn", "edd", "enhanced due diligence"]
TASK_2_CORRECT_REGULATIONS = [RegulationFramework.OFAC, RegulationFramework.FATF]
TASK_2_REASONING_KEYWORDS = ["pep", "sanction", "ofac", "russia", "sdn", "enhanced due diligence", "edd"]


def grade_task_2(action: ComplianceAction) -> float:
    """
    Medium task grader — PEP + OFAC sanctions scenario.
    Correct answer: FLAG_SANCTIONS or ESCALATE (APPROVE is severely wrong).
    """
    score = 0.0

    # Decision correctness (0.40)
    if action.decision == ComplianceDecision.FLAG_SANCTIONS:
        score += 0.40
    elif action.decision == ComplianceDecision.ESCALATE:
        score += 0.35
    elif action.decision == ComplianceDecision.REJECT:
        score += 0.15  # wrong process — sanctions violations need reporting
    elif action.decision == ComplianceDecision.APPROVE:
        score += 0.0  # approving a sanctions violation = critical failure
    elif action.decision == ComplianceDecision.REQUEST_INFO:
        # Requesting info on a CRITICAL OFAC alert is inappropriate — partial
        score += 0.10

    # Risk identification (0.30)
    score += 0.30 * _risk_overlap(action.identified_risks, TASK_2_CORRECT_RISKS)

    # Regulations cited (0.15)
    score += 0.15 * _regulation_overlap(action.regulation_cited, TASK_2_CORRECT_REGULATIONS)

    # Reasoning quality (0.15)
    score += 0.15 * _reasoning_quality(action.reasoning, TASK_2_REASONING_KEYWORDS)

    return round(min(score, 1.0), 4)


# ---------------------------------------------------------------------------
# TASK 3 – HARD
# Layered obfuscation: crypto → fiat conversion, GDPR data redaction,
# MiFID2 market manipulation signal, subtle fraud indicators
# ---------------------------------------------------------------------------

TASK_3_TRANSACTION = Transaction(
    transaction_id="TXN-003-HARD",
    amount_usd=47_320.0,
    sender_name="Nexus Digital Assets GmbH",
    sender_country="Germany",
    sender_account_type="crypto",
    receiver_name="Apex Capital Management SA",
    receiver_country="Luxembourg",
    receiver_account_type="corporate",
    transaction_type="crypto",
    purpose="Liquidity provision for algorithmic trading strategy",
    velocity_24h=12,
    velocity_amount_24h=520_000.0,
    is_pep=False,
    is_sanctioned_country=False,
    structuring_flag=False,
    unusual_hours=True,
    new_relationship=False,
    prior_sar_count=0,
)

TASK_3_ALERTS = [
    RegulatoryAlert(
        framework=RegulationFramework.MiFID2,
        severity=RiskLevel.HIGH,
        description="High-frequency crypto-to-fiat conversion pattern consistent with wash trading or layering strategy. Volume spike 840% above 30-day average.",
        rule_id="MiFID2-MAR-5",
    ),
    RegulatoryAlert(
        framework=RegulationFramework.GDPR,
        severity=RiskLevel.MEDIUM,
        description="Transaction metadata contains personal data of EU citizens transmitted without explicit consent record. Potential Article 6 GDPR violation.",
        rule_id="GDPR-ART6",
    ),
    RegulatoryAlert(
        framework=RegulationFramework.FATF,
        severity=RiskLevel.MEDIUM,
        description="Crypto layering pattern detected. Funds moved through 3 intermediate wallets in past 72h (chain-hopping).",
        rule_id="FATF-R15",
    ),
    RegulatoryAlert(
        framework=RegulationFramework.PCI_DSS,
        severity=RiskLevel.LOW,
        description="Payment processing system used does not meet PCI DSS 4.0 tokenization requirements for crypto-card settlement.",
        rule_id="PCI-DSS-4.0-REQ3",
    ),
]

TASK_3_CORRECT_RISKS = [
    "wash trading", "layering", "chain-hopping", "velocity", "volume spike",
    "gdpr", "personal data", "mifid", "market manipulation", "crypto"
]
TASK_3_CORRECT_REGULATIONS = [
    RegulationFramework.MiFID2,
    RegulationFramework.FATF,
    RegulationFramework.GDPR,
]
TASK_3_REASONING_KEYWORDS = [
    "wash", "layering", "mifid", "gdpr", "chain", "volume", "spike",
    "algorithmic", "manipulation", "velocity", "crypto"
]


def grade_task_3(action: ComplianceAction) -> float:
    """
    Hard task grader — multi-regulation layered financial crime scenario.
    Correct: ESCALATE or FLAG_AML/FLAG_FRAUD (multiple violations require senior review).
    Must cite at least 2 of the 3 primary regulations.
    Must identify at least 3 of the 4+ risk signals.
    """
    score = 0.0

    # Decision correctness (0.30) — escalation or dual-flag expected
    if action.decision == ComplianceDecision.ESCALATE:
        score += 0.30
    elif action.decision in (ComplianceDecision.FLAG_AML, ComplianceDecision.FLAG_FRAUD):
        score += 0.25
    elif action.decision == ComplianceDecision.REJECT:
        score += 0.10
    elif action.decision == ComplianceDecision.REQUEST_INFO:
        score += 0.05
    elif action.decision == ComplianceDecision.APPROVE:
        score += 0.0

    # Risk identification (0.35) — harder, needs depth
    risk_score = _risk_overlap(action.identified_risks, TASK_3_CORRECT_RISKS)
    score += 0.35 * risk_score

    # Regulations cited (0.20) — must get at least 2/3
    reg_score = _regulation_overlap(action.regulation_cited, TASK_3_CORRECT_REGULATIONS)
    score += 0.20 * reg_score

    # Reasoning depth (0.15)
    score += 0.15 * _reasoning_quality(action.reasoning, TASK_3_REASONING_KEYWORDS)

    return round(min(score, 1.0), 4)


# ---------------------------------------------------------------------------
# Task catalogue registry
# ---------------------------------------------------------------------------

TASKS: Dict[str, Dict[str, Any]] = {
    "easy_structuring": {
        "name": "easy_structuring",
        "difficulty": "easy",
        "description": (
            "A retail customer makes multiple wire transfers just below the $10,000 "
            "Currency Transaction Report (CTR) threshold to a shell company in the Cayman Islands. "
            "Prior SAR on file. Identify the structuring pattern and apply BSA/FATF rules."
        ),
        "transaction": TASK_1_TRANSACTION,
        "alerts": TASK_1_ALERTS,
        "correct_decision": ComplianceDecision.FLAG_AML.value,
        "correct_risks": TASK_1_CORRECT_RISKS,
        "correct_regulations": TASK_1_CORRECT_REGULATIONS,
        "grader": grade_task_1,
        "max_steps": 3,
    },
    "medium_pep_sanctions": {
        "name": "medium_pep_sanctions",
        "difficulty": "medium",
        "description": (
            "A $250,000 SWIFT transfer from a Russian Politically Exposed Person (PEP) "
            "to a Swiss holding company. Russia is subject to OFAC sectoral sanctions. "
            "Enhanced Due Diligence required. Apply OFAC/FATF rules correctly."
        ),
        "transaction": TASK_2_TRANSACTION,
        "alerts": TASK_2_ALERTS,
        "correct_decision": ComplianceDecision.FLAG_SANCTIONS.value,
        "correct_risks": TASK_2_CORRECT_RISKS,
        "correct_regulations": TASK_2_CORRECT_REGULATIONS,
        "grader": grade_task_2,
        "max_steps": 5,
    },
    "hard_crypto_layering": {
        "name": "hard_crypto_layering",
        "difficulty": "hard",
        "description": (
            "A German crypto-to-fiat firm sends $47K to a Luxembourg asset manager, "
            "but velocity data shows $520K moved in 24h across 12 transactions. "
            "Indicators of wash trading (MiFID2), chain-hopping (FATF R15), "
            "GDPR personal-data leakage, and PCI DSS gaps. "
            "Identify all violations and apply the correct multi-framework response."
        ),
        "transaction": TASK_3_TRANSACTION,
        "alerts": TASK_3_ALERTS,
        "correct_decision": ComplianceDecision.ESCALATE.value,
        "correct_risks": TASK_3_CORRECT_RISKS,
        "correct_regulations": TASK_3_CORRECT_REGULATIONS,
        "grader": grade_task_3,
        "max_steps": 8,
    },
}
