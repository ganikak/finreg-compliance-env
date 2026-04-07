"""
FinReg Compliance Environment — core Environment class.
Implements OpenEnv's Environment interface: reset(), step(), state property.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from models import (
    ComplianceAction,
    ComplianceDecision,
    ComplianceObservation,
    ComplianceState,
    RegulationFramework,
)
from tasks import TASKS


# ---------------------------------------------------------------------------
# Reward shaping constants
# ---------------------------------------------------------------------------

STEP_PENALTY = -0.02          # small cost per step to discourage wasting moves
WRONG_APPROVE_PENALTY = -0.30 # severe penalty for approving a flagged transaction
WRONG_REJECT_PENALTY = -0.10  # process error (should follow SAR workflow, not just reject)


class FinRegEnvironment:
    """
    AI Regulatory Compliance Simulator for Financial Transactions.

    The agent reviews a financial transaction, inspects alerts, and must
    decide: approve / reject / escalate / request_info / flag_aml /
    flag_fraud / flag_sanctions.

    Supports 3 tasks: easy_structuring, medium_pep_sanctions, hard_crypto_layering.
    """

    def __init__(self, task_name: str = "easy_structuring") -> None:
        if task_name not in TASKS:
            raise ValueError(f"Unknown task '{task_name}'. Choose from: {list(TASKS)}")
        self._task_name = task_name
        self._task = TASKS[task_name]
        self._state = self._fresh_state()

    # -----------------------------------------------------------------------
    # OpenEnv interface
    # -----------------------------------------------------------------------

    def reset(self) -> ComplianceObservation:
        """Start a new episode. Returns the initial observation."""
        self._state = self._fresh_state()
        return self._build_observation(reward=0.0, feedback="Episode started. Review the transaction and alerts.")

    def step(self, action: ComplianceAction) -> ComplianceObservation:
        """Take one compliance decision step."""
        if self._state.done:
            return self._build_observation(reward=0.0, feedback="Episode already complete. Call reset().")

        self._state.step_count += 1

        # Score the action with the task's grader
        raw_score: float = self._task["grader"](action)

        # Reward shaping
        reward = self._shape_reward(action, raw_score)
        self._state.cumulative_reward += reward

        # Record action
        self._state.action_history.append({
            "step": self._state.step_count,
            "decision": action.decision.value,
            "reasoning_length": len(action.reasoning),
            "risks_identified": len(action.identified_risks),
            "regulations_cited": [r.value for r in action.regulation_cited],
            "raw_score": raw_score,
            "shaped_reward": reward,
        })

        # Episode ends when agent makes a definitive decision OR max steps reached
        is_definitive = action.decision not in (
            ComplianceDecision.REQUEST_INFO,
        )
        at_max_steps = self._state.step_count >= self._state.max_steps

        if is_definitive or at_max_steps:
            self._state.done = True

        feedback = self._generate_feedback(action, raw_score)

        obs = self._build_observation(reward=reward, feedback=feedback)
        if self._state.done:
            obs.correct_decision = self._state.correct_decision
            obs.score_breakdown = self._compute_score_breakdown(action, raw_score)
        return obs

    @property
    def state(self) -> ComplianceState:
        """Return the full internal state (for debugging / RL frameworks)."""
        return self._state

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "finreg-compliance-env",
            "version": "1.0.0",
            "task": self._task_name,
            "difficulty": self._task["difficulty"],
            "description": self._task["description"],
        }

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _fresh_state(self) -> ComplianceState:
        return ComplianceState(
            episode_id=str(uuid.uuid4()),
            task_name=self._task_name,
            step_count=0,
            max_steps=self._task["max_steps"],
            done=False,
            cumulative_reward=0.0,
            current_transaction=self._task["transaction"],
            action_history=[],
            correct_decision=self._task["correct_decision"],
            correct_risks=self._task["correct_risks"],
            correct_regulations=self._task["correct_regulations"],
            grader_metadata={},
        )

    def _build_observation(self, reward: float, feedback: str) -> ComplianceObservation:
        return ComplianceObservation(
            transaction=self._state.current_transaction,
            alerts=self._task["alerts"],
            task_description=self._task["description"],
            task_difficulty=self._task["difficulty"],
            step_count=self._state.step_count,
            cumulative_reward=self._state.cumulative_reward,
            done=self._state.done,
            reward=reward,
            feedback=feedback,
        )

    def _shape_reward(self, action: ComplianceAction, raw_score: float) -> float:
        """Apply reward shaping on top of raw grader score."""
        reward = raw_score

        # Step cost to discourage wasting moves
        reward += STEP_PENALTY * self._state.step_count

        # Penalise approving clearly flagged transactions
        if action.decision == ComplianceDecision.APPROVE and raw_score < 0.15:
            reward += WRONG_APPROVE_PENALTY

        # Penalise blind reject without any regulatory reasoning
        if action.decision == ComplianceDecision.REJECT and not action.regulation_cited:
            reward += WRONG_REJECT_PENALTY

        return round(reward, 4)

    def _generate_feedback(self, action: ComplianceAction, raw_score: float) -> str:
        if raw_score >= 0.80:
            return f"Excellent compliance decision. Score: {raw_score:.2f}. Decision '{action.decision.value}' aligns with regulatory requirements."
        elif raw_score >= 0.55:
            return f"Good decision with room for improvement. Score: {raw_score:.2f}. Consider citing more specific regulations."
        elif raw_score >= 0.30:
            return f"Partial compliance. Score: {raw_score:.2f}. Key risk factors were missed. Review the alerts more carefully."
        else:
            return f"Non-compliant decision. Score: {raw_score:.2f}. Significant regulatory violations unaddressed."

    def _compute_score_breakdown(self, action: ComplianceAction, raw_score: float) -> Dict[str, float]:
        return {
            "raw_grader_score": raw_score,
            "shaped_reward": self._state.cumulative_reward,
            "decision_accuracy": 1.0 if action.decision.value == self._state.correct_decision else 0.0,
            "risk_coverage": min(len(action.identified_risks) / max(len(self._state.correct_risks), 1), 1.0),
            "regulation_coverage": min(
                len([r for r in action.regulation_cited if r in self._state.correct_regulations])
                / max(len(self._state.correct_regulations), 1),
                1.0,
            ),
        }
