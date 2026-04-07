"""
test_env.py — Offline unit tests for FinReg Compliance Environment
Run: python test_env.py
No server required — tests models, tasks, and environment logic directly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import (
    ComplianceAction, ComplianceDecision, ComplianceObservation,
    ComplianceState, RegulationFramework, RiskLevel, Transaction, RegulatoryAlert
)
from tasks import TASKS, grade_task_1, grade_task_2, grade_task_3
from server.finreg_environment import FinRegEnvironment

PASS = "✓"
FAIL = "✗"
results = []

def check(name, condition, got=None, expected=None):
    if condition:
        print(f"  {PASS} {name}")
        results.append(True)
    else:
        print(f"  {FAIL} {name}  got={got!r}  expected={expected!r}")
        results.append(False)

print("\n=== FinReg Compliance Env — Test Suite ===\n")

# ─── Model instantiation ────────────────────────────────────────────────────
print("▶ Models")
a = ComplianceAction(
    decision=ComplianceDecision.FLAG_AML,
    reasoning="Classic structuring pattern below CTR threshold.",
    identified_risks=["structuring", "smurfing"],
    regulation_cited=[RegulationFramework.BSA, RegulationFramework.FATF],
)
check("ComplianceAction instantiates", a.decision == ComplianceDecision.FLAG_AML)
check("ComplianceAction risks list", len(a.identified_risks) == 2)

t = Transaction(
    transaction_id="TEST-001",
    amount_usd=9800.0,
    sender_name="Test User",
    sender_country="US",
    sender_account_type="individual",
    receiver_name="Shell Co",
    receiver_country="Cayman Islands",
    receiver_account_type="corporate",
    transaction_type="wire",
    purpose="Consulting",
)
check("Transaction instantiates", t.amount_usd == 9800.0)

obs = ComplianceObservation(task_description="Test task", done=False, reward=0.0)
check("ComplianceObservation instantiates", not obs.done)

state = ComplianceState(episode_id="test-123", task_name="easy_structuring")
check("ComplianceState instantiates", state.task_name == "easy_structuring")

# ─── Task registry ──────────────────────────────────────────────────────────
print("\n▶ Task Registry")
check("3 tasks registered", len(TASKS) == 3, got=len(TASKS), expected=3)
check("easy_structuring present", "easy_structuring" in TASKS)
check("medium_pep_sanctions present", "medium_pep_sanctions" in TASKS)
check("hard_crypto_layering present", "hard_crypto_layering" in TASKS)

for name, task in TASKS.items():
    check(f"{name} has grader", callable(task["grader"]))
    check(f"{name} has transaction", task["transaction"] is not None)
    check(f"{name} has alerts", len(task["alerts"]) > 0)

# ─── Grader correctness ─────────────────────────────────────────────────────
print("\n▶ Grader Scoring (Task 1 — Easy)")

good1 = ComplianceAction(
    decision=ComplianceDecision.FLAG_AML,
    reasoning="Classic structuring (smurfing): 4 transactions totaling $38,200 in 24h just below $10,000 CTR threshold. BSA 31 CFR 1010.314 applies. SAR must be filed. Destination is Cayman Islands shell company — FATF R13 risk.",
    identified_risks=["structuring", "smurfing", "ctr", "threshold", "shell", "cayman", "velocity"],
    regulation_cited=[RegulationFramework.BSA, RegulationFramework.FATF],
)
bad1 = ComplianceAction(
    decision=ComplianceDecision.APPROVE,
    reasoning="Looks fine",
    identified_risks=[],
    regulation_cited=[],
)
partial1 = ComplianceAction(
    decision=ComplianceDecision.ESCALATE,
    reasoning="Suspicious pattern",
    identified_risks=["structuring"],
    regulation_cited=[RegulationFramework.BSA],
)
score_good1 = grade_task_1(good1)
score_bad1 = grade_task_1(bad1)
score_partial1 = grade_task_1(partial1)

check("Task 1 good score >= 0.80", score_good1 >= 0.80, got=score_good1)
check("Task 1 bad score <= 0.15", score_bad1 <= 0.15, got=score_bad1)
check("Task 1 partial > bad", score_partial1 > score_bad1, got=score_partial1)
check("Task 1 good > partial", score_good1 > score_partial1, got=(score_good1, score_partial1))
check("Task 1 score in [0,1]", 0.0 <= score_good1 <= 1.0)

print("\n▶ Grader Scoring (Task 2 — Medium)")
good2 = ComplianceAction(
    decision=ComplianceDecision.FLAG_SANCTIONS,
    reasoning="OFAC EO-13662 sanctions apply to Russia. Sender is PEP — FATF R12 Enhanced Due Diligence mandatory. SDN list check required. Transaction cannot proceed.",
    identified_risks=["pep", "politically exposed", "sanctions", "ofac", "russia", "sdn", "edd", "enhanced due diligence"],
    regulation_cited=[RegulationFramework.OFAC, RegulationFramework.FATF],
)
approve2 = ComplianceAction(
    decision=ComplianceDecision.APPROVE,
    reasoning="Legitimate investment",
    identified_risks=[],
    regulation_cited=[],
)
score_good2 = grade_task_2(good2)
score_approve2 = grade_task_2(approve2)
check("Task 2 good score >= 0.75", score_good2 >= 0.75, got=score_good2)
check("Task 2 approve score = 0.0 (critical failure)", score_approve2 == 0.0, got=score_approve2)
check("Task 2 score in [0,1]", 0.0 <= score_good2 <= 1.0)

print("\n▶ Grader Scoring (Task 3 — Hard)")
good3 = ComplianceAction(
    decision=ComplianceDecision.ESCALATE,
    reasoning="Multi-framework violation detected. Wash trading pattern matches MiFID2 MAR-5 market manipulation. FATF R15 crypto chain-hopping layering across 3 wallets. GDPR Article 6 violated — EU personal data transmitted without consent. Volume spike 840% above average. Senior compliance review required.",
    identified_risks=["wash trading", "layering", "chain-hopping", "velocity", "volume spike", "gdpr", "personal data", "mifid", "market manipulation", "crypto"],
    regulation_cited=[RegulationFramework.MiFID2, RegulationFramework.FATF, RegulationFramework.GDPR],
)
easy_wrong3 = ComplianceAction(
    decision=ComplianceDecision.APPROVE,
    reasoning="Crypto is fine",
    identified_risks=[],
    regulation_cited=[],
)
score_good3 = grade_task_3(good3)
score_wrong3 = grade_task_3(easy_wrong3)
check("Task 3 good score >= 0.70", score_good3 >= 0.70, got=score_good3)
check("Task 3 wrong score <= 0.10", score_wrong3 <= 0.10, got=score_wrong3)
check("Task 3 score in [0,1]", 0.0 <= score_good3 <= 1.0)
check("Task 3 harder than Task 1 for same effort", score_good3 <= score_good1 + 0.15)

# ─── Environment full episode ─────────────────────────────────────────────
print("\n▶ Environment — Easy Task Full Episode")
env = FinRegEnvironment(task_name="easy_structuring")

obs = env.reset()
check("reset() returns ComplianceObservation", isinstance(obs, ComplianceObservation))
check("reset() done=False", not obs.done)
check("reset() has transaction", obs.transaction is not None)
check("reset() has alerts", len(obs.alerts) > 0)
check("reset() step_count=0", obs.step_count == 0)
check("reset() reward=0.0", obs.reward == 0.0)

obs2 = env.step(good1)
check("step() returns ComplianceObservation", isinstance(obs2, ComplianceObservation))
check("step() done=True after definitive decision", obs2.done)
check("step() reward > 0 for good action", obs2.reward > 0, got=obs2.reward)
check("step() step_count=1", obs2.step_count == 1)
check("step() has feedback", len(obs2.feedback) > 0)
check("step() has score_breakdown on done", len(obs2.score_breakdown) > 0)

state = env.state
check("state returns ComplianceState", isinstance(state, ComplianceState))
check("state.done=True", state.done)
check("state.step_count=1", state.step_count == 1)
check("state has action_history", len(state.action_history) == 1)

print("\n▶ Environment — Medium Task Reset Produces Clean State")
env2 = FinRegEnvironment(task_name="medium_pep_sanctions")
obs_m = env2.reset()
check("Medium task reset done=False", not obs_m.done)
check("Medium task transaction is PEP", obs_m.transaction.is_pep)
check("Medium task transaction is sanctioned", obs_m.transaction.is_sanctioned_country)
check("Medium task has 2 alerts", len(obs_m.alerts) == 2, got=len(obs_m.alerts))

print("\n▶ Environment — Hard Task")
env3 = FinRegEnvironment(task_name="hard_crypto_layering")
obs_h = env3.reset()
check("Hard task reset done=False", not obs_h.done)
check("Hard task has 4 alerts", len(obs_h.alerts) == 4, got=len(obs_h.alerts))
check("Hard task velocity_24h=12", obs_h.transaction.velocity_24h == 12)

print("\n▶ Reward Shaping — Penalties")
env4 = FinRegEnvironment(task_name="easy_structuring")
env4.reset()
penalized = env4.step(ComplianceAction(
    decision=ComplianceDecision.APPROVE,
    reasoning="Fine",
    identified_risks=[],
    regulation_cited=[],
))
check("Approve on flagged txn gets negative reward", penalized.reward < 0, got=penalized.reward)

print("\n▶ Episode Boundary")
env5 = FinRegEnvironment(task_name="easy_structuring")
env5.reset()
env5.step(good1)  # done=True
obs_after = env5.step(good1)  # call step after done
check("step() after done returns gracefully", isinstance(obs_after, ComplianceObservation))

print("\n▶ openenv.yaml exists")
import os
check("openenv.yaml present", os.path.exists("openenv.yaml"))
check("Dockerfile present", os.path.exists("Dockerfile"))
check("inference.py present", os.path.exists("inference.py"))
check("requirements.txt present", os.path.exists("requirements.txt"))
check("server/app.py present", os.path.exists("server/app.py"))

# ─── Summary ────────────────────────────────────────────────────────────────
total = len(results)
passed = sum(results)
failed = total - passed
print(f"\n{'='*46}")
print(f"  Results: {passed}/{total} passed  ({failed} failed)")
print(f"{'='*46}\n")
if failed == 0:
    print("🎉 All tests passed! Environment is ready for submission.\n")
else:
    print("⚠️  Some tests failed. Review output above.\n")
    sys.exit(1)
