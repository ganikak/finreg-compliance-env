"""
inference.py — FinReg Compliance Environment Baseline Inference Script
========================================================================

Runs an LLM agent against all 3 compliance tasks and emits structured
stdout logs in the mandatory [START] / [STEP] / [END] format.

Environment variables:
  API_BASE_URL    LLM endpoint (default: HuggingFace router)
  MODEL_NAME      Model identifier
  HF_TOKEN        API key / HF token
  FINREG_ENV_URL  Base URL of the running FinReg environment server
                  (default: http://localhost:8000)

Usage:
  python inference.py

Expected runtime: < 5 minutes for all 3 tasks.
"""

from __future__ import annotations

import json
import os
import textwrap
import time
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME: str = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
API_KEY: str = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or "hf_placeholder"
ENV_BASE_URL: str = os.getenv("FINREG_ENV_URL", "http://localhost:7860")

BENCHMARK = "finreg-compliance-env"
MAX_STEPS = 5
TEMPERATURE = 0.2
MAX_TOKENS = 800
SUCCESS_THRESHOLD = 0.40   # raw score >= 0.40 considered success

TASKS = ["easy_structuring", "medium_pep_sanctions", "hard_crypto_layering"]

# ---------------------------------------------------------------------------
# Logging helpers — MANDATORY FORMAT
# ---------------------------------------------------------------------------

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Environment HTTP client
# ---------------------------------------------------------------------------

def env_reset(task: str) -> Dict[str, Any]:
    """Reset the environment for a given task."""
    resp = requests.post(
        f"{ENV_BASE_URL}/reset",
        params={"task": task},
        headers={"X-Task": task},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def env_step(action_payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(
        f"{ENV_BASE_URL}/step",
        json=action_payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def env_set_task(task: str) -> None:
    """Restart environment with a different task (via query param)."""
    try:
        requests.post(f"{ENV_BASE_URL}/reset", params={"task": task}, timeout=10)
    except Exception:
        pass  # Server may not support hot-swapping; handled in run_task


# ---------------------------------------------------------------------------
# LLM agent
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""
You are an expert financial compliance officer with deep knowledge of:
- BSA (Bank Secrecy Act) and AML regulations
- FATF (Financial Action Task Force) recommendations
- OFAC (Office of Foreign Assets Control) sanctions
- MiFID2 market manipulation regulations
- GDPR data privacy requirements
- PCI DSS payment security standards

You will be given a financial transaction to review, along with regulatory alerts.
You must analyze the transaction and provide a compliance decision.

AVAILABLE DECISIONS:
- approve: Transaction meets compliance requirements
- reject: Transaction violates compliance rules (use sparingly — prefer flag/escalate)
- escalate: Transaction requires senior compliance officer review
- request_info: Need additional information before deciding
- flag_aml: Flag for Anti-Money Laundering investigation
- flag_fraud: Flag for fraud investigation
- flag_sanctions: Flag for sanctions violation (mandatory for OFAC hits)

RESPONSE FORMAT — respond ONLY with valid JSON, no markdown:
{
  "decision": "<one of the decisions above>",
  "reasoning": "<detailed explanation of your compliance analysis>",
  "identified_risks": ["<risk1>", "<risk2>", ...],
  "regulation_cited": ["<FATF|BSA|OFAC|MiFID2|GDPR|PCI_DSS>", ...],
  "additional_info_requested": null
}
""").strip()


def build_user_prompt(obs: Dict[str, Any], step: int) -> str:
    txn = obs.get("transaction", {})
    alerts = obs.get("alerts", [])
    
    alerts_text = "\n".join(
        f"  [{a.get('framework','')}] [{a.get('severity','')}] {a.get('description','')} (Rule: {a.get('rule_id','')})"
        for a in alerts
    )
    
    return textwrap.dedent(f"""
STEP {step} — TRANSACTION REVIEW

TASK: {obs.get('task_description', '')}
DIFFICULTY: {obs.get('task_difficulty', '')}

--- TRANSACTION DETAILS ---
Transaction ID: {txn.get('transaction_id', 'N/A')}
Amount: ${txn.get('amount_usd', 0):,.2f}
Sender: {txn.get('sender_name', 'N/A')} ({txn.get('sender_country', 'N/A')}) — Account type: {txn.get('sender_account_type', 'N/A')}
Receiver: {txn.get('receiver_name', 'N/A')} ({txn.get('receiver_country', 'N/A')}) — Account type: {txn.get('receiver_account_type', 'N/A')}
Transaction Type: {txn.get('transaction_type', 'N/A')}
Purpose: {txn.get('purpose', 'N/A')}
Velocity (24h): {txn.get('velocity_24h', 0)} transactions / ${txn.get('velocity_amount_24h', 0):,.2f} total
PEP Flag: {txn.get('is_pep', False)}
Sanctioned Country: {txn.get('is_sanctioned_country', False)}
Structuring Flag: {txn.get('structuring_flag', False)}
Unusual Hours: {txn.get('unusual_hours', False)}
New Relationship: {txn.get('new_relationship', False)}
Prior SARs: {txn.get('prior_sar_count', 0)}

--- REGULATORY ALERTS ---
{alerts_text}

--- PREVIOUS FEEDBACK ---
{obs.get('feedback', 'No prior feedback.')}

Analyze this transaction thoroughly and provide your compliance decision as JSON.
""").strip()


def get_llm_decision(client: OpenAI, obs: Dict[str, Any], step: int) -> Dict[str, Any]:
    """Call LLM and parse the compliance action JSON."""
    user_prompt = build_user_prompt(obs, step)
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        raw = (completion.choices[0].message.content or "").strip()
        
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        
        parsed = json.loads(raw)
        return parsed
        
    except json.JSONDecodeError:
        # Fallback: default safe action
        return {
            "decision": "escalate",
            "reasoning": "Unable to parse LLM response — defaulting to escalation for safety.",
            "identified_risks": ["unknown"],
            "regulation_cited": [],
            "additional_info_requested": None,
        }
    except Exception as exc:
        print(f"[DEBUG] LLM call failed: {exc}", flush=True)
        return {
            "decision": "escalate",
            "reasoning": "LLM call failed — defaulting to escalation.",
            "identified_risks": [],
            "regulation_cited": [],
            "additional_info_requested": None,
        }


# ---------------------------------------------------------------------------
# Single task runner
# ---------------------------------------------------------------------------

def run_task(client: OpenAI, task_name: str) -> Dict[str, Any]:
    """Run one complete episode for a task. Returns summary dict."""
    rewards: List[float] = []
    steps_taken = 0
    success = False
    score = 0.0
    error_msg: Optional[str] = None
    
    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)
    
    try:
        # Reset — try setting task via env var approach; server uses FINREG_TASK env var
        # For multi-task, we call reset and work with whatever task is active
        obs = env_reset(task_name)
        
        for step in range(1, MAX_STEPS + 1):
            if obs.get("done", False):
                break
            
            # Get LLM decision
            action_dict = get_llm_decision(client, obs, step)
            action_str = action_dict.get("decision", "escalate")
            
            # Step environment
            try:
                obs = env_step(action_dict)
                reward = float(obs.get("reward", 0.0))
                done = bool(obs.get("done", False))
                error_msg = None
            except Exception as exc:
                reward = 0.0
                done = True
                error_msg = str(exc)
                obs = {"done": True, "reward": 0.0, "feedback": f"Error: {exc}"}
            
            rewards.append(reward)
            steps_taken = step
            
            log_step(step=step, action=action_str, reward=reward, done=done, error=error_msg)
            
            if done:
                # Extract final score from observation
                breakdown = obs.get("score_breakdown", {})
                raw_score = breakdown.get("raw_grader_score", reward)
                score = float(raw_score)
                break
        
        if not rewards:
            score = 0.0
        else:
            # Use last reward as grader score for success determination
            score = max(rewards) if rewards else 0.0
        
        success = score >= SUCCESS_THRESHOLD
        
    except Exception as exc:
        print(f"[DEBUG] Task {task_name} failed: {exc}", flush=True)
        error_msg = str(exc)
        score = 0.0
        success = False
    
    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    
    return {
        "task": task_name,
        "success": success,
        "score": score,
        "steps": steps_taken,
        "rewards": rewards,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def wait_for_server(max_retries: int = 30) -> bool:
    """Poll /health until server is ready."""
    for i in range(max_retries):
        try:
            r = requests.get(f"{ENV_BASE_URL}/health", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main() -> None:
    print(f"[DEBUG] Waiting for environment at {ENV_BASE_URL}...", flush=True)
    if not wait_for_server():
        print(f"[DEBUG] WARNING: Could not connect to {ENV_BASE_URL}. Proceeding anyway.", flush=True)
    
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    
    results = []
    for task_name in TASKS:
        result = run_task(client, task_name)
        results.append(result)
        time.sleep(1)  # Brief pause between tasks
    
    # Summary
    print("\n[DEBUG] === BASELINE RESULTS ===", flush=True)
    for r in results:
        status = "✓ SUCCESS" if r["success"] else "✗ FAILED"
        print(
            f"[DEBUG]  {status} | {r['task']:30s} | score={r['score']:.3f} | steps={r['steps']}",
            flush=True,
        )
    
    avg_score = sum(r["score"] for r in results) / len(results)
    print(f"[DEBUG] Average score: {avg_score:.3f}", flush=True)


if __name__ == "__main__":
    main()
