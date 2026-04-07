"""
Typed Pydantic models for the AI Regulatory Compliance Simulator
for Financial Transactions (FinReg Compliance Env).

Action  → ComplianceAction
Observation → ComplianceObservation
State   → ComplianceState
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    REQUEST_INFO = "request_info"
    FLAG_AML = "flag_aml"
    FLAG_FRAUD = "flag_fraud"
    FLAG_SANCTIONS = "flag_sanctions"


class RegulationFramework(str, Enum):
    FATF = "FATF"           # Anti-Money Laundering
    GDPR = "GDPR"           # Data privacy
    PCI_DSS = "PCI_DSS"     # Payment card security
    OFAC = "OFAC"           # US sanctions
    BSA = "BSA"             # Bank Secrecy Act
    MiFID2 = "MiFID2"       # EU financial instruments


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class Transaction(BaseModel):
    """A financial transaction to be reviewed."""
    transaction_id: str
    amount_usd: float
    sender_name: str
    sender_country: str
    sender_account_type: str          # individual / corporate / crypto
    receiver_name: str
    receiver_country: str
    receiver_account_type: str
    transaction_type: str             # wire / ach / swift / crypto / card
    purpose: str
    velocity_24h: int = 0             # how many transactions in last 24h
    velocity_amount_24h: float = 0.0  # total $ in last 24h
    is_pep: bool = False              # politically exposed person
    is_sanctioned_country: bool = False
    structuring_flag: bool = False    # smurfing / structuring indicator
    unusual_hours: bool = False
    new_relationship: bool = False    # first transaction with this counterpart
    prior_sar_count: int = 0          # prior Suspicious Activity Reports


class RegulatoryAlert(BaseModel):
    framework: RegulationFramework
    severity: RiskLevel
    description: str
    rule_id: str


class ComplianceAction(BaseModel):
    """Action the agent takes: a compliance decision + optional reasoning."""
    decision: ComplianceDecision
    reasoning: str = Field(
        default="",
        description="Agent's explanation of the decision (used in grading)"
    )
    identified_risks: List[str] = Field(
        default_factory=list,
        description="List of risk factors the agent identified"
    )
    regulation_cited: List[RegulationFramework] = Field(
        default_factory=list,
        description="Regulations the agent believes are relevant"
    )
    additional_info_requested: Optional[str] = Field(
        default=None,
        description="If decision=request_info, specify what info is needed"
    )


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

class ComplianceObservation(BaseModel):
    """What the agent observes after a step or reset."""
    transaction: Optional[Transaction] = None
    alerts: List[RegulatoryAlert] = Field(default_factory=list)
    task_description: str = ""
    task_difficulty: str = ""          # easy / medium / hard
    step_count: int = 0
    cumulative_reward: float = 0.0
    done: bool = False
    reward: float = 0.0
    feedback: str = ""                 # human-readable feedback on last action
    correct_decision: Optional[str] = None   # revealed after done=True
    score_breakdown: Dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ComplianceState(BaseModel):
    """Full internal state of the environment."""
    episode_id: str = ""
    task_name: str = ""
    step_count: int = 0
    max_steps: int = 10
    done: bool = False
    cumulative_reward: float = 0.0
    current_transaction: Optional[Transaction] = None
    action_history: List[Dict[str, Any]] = Field(default_factory=list)
    correct_decision: str = ""
    correct_risks: List[str] = Field(default_factory=list)
    correct_regulations: List[RegulationFramework] = Field(default_factory=list)
    grader_metadata: Dict[str, Any] = Field(default_factory=dict)
