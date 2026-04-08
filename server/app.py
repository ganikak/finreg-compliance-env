"""
FastAPI server for FinReg Compliance Environment.
Exposes /reset, /step, /state, /health, /metadata endpoints.

NOTE: Runs on port 7860 to satisfy HuggingFace Spaces requirements.
"""

from __future__ import annotations

import os
import sys

# Ensure /app (project root) is always on the path regardless of how
# uvicorn is invoked (docker, local, HF Spaces).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import ComplianceAction, ComplianceObservation, ComplianceState
from server.finreg_environment import FinRegEnvironment

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FinReg Compliance Environment",
    description="AI Regulatory Compliance Simulator for Financial Transactions — OpenEnv compatible",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Environment instance — task configurable via env var
# ---------------------------------------------------------------------------

TASK_NAME = os.getenv("FINREG_TASK", "easy_structuring")
_env = FinRegEnvironment(task_name=TASK_NAME)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root() -> Dict[str, str]:
    """Root route — required by HuggingFace Spaces health check."""
    return {"status": "ok", "env": "finreg-compliance-env", "task": TASK_NAME, "version": "1.0.0"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "env": "finreg-compliance-env", "task": TASK_NAME}


@app.get("/metadata")
async def metadata() -> Dict[str, Any]:
    return _env.get_metadata()


@app.post("/reset", response_model=ComplianceObservation)
async def reset() -> ComplianceObservation:
    """Reset the environment and return the initial observation."""
    return _env.reset()


@app.post("/step", response_model=ComplianceObservation)
async def step(action: ComplianceAction) -> ComplianceObservation:
    """Take a compliance decision step."""
    return _env.step(action)


@app.get("/state", response_model=ComplianceState)
async def state() -> ComplianceState:
    """Return the full current state (for RL frameworks)."""
    return _env.state


# ---------------------------------------------------------------------------
# Gradio Web UI (optional — enabled when ENABLE_WEB_INTERFACE=1)
# ---------------------------------------------------------------------------

ENABLE_WEB = os.getenv("ENABLE_WEB_INTERFACE", "0") == "1"

if ENABLE_WEB:
    try:
        import gradio as gr

        def gradio_reset():
            obs = _env.reset()
            txn = obs.transaction
            txn_text = (
                f"**Transaction ID**: {txn.transaction_id}\n"
                f"**Amount**: ${txn.amount_usd:,.2f}\n"
                f"**Sender**: {txn.sender_name} ({txn.sender_country})\n"
                f"**Receiver**: {txn.receiver_name} ({txn.receiver_country})\n"
                f"**Type**: {txn.transaction_type}\n"
                f"**Purpose**: {txn.purpose}\n"
                f"**PEP**: {txn.is_pep} | **Sanctioned Country**: {txn.is_sanctioned_country}\n"
                f"**Structuring Flag**: {txn.structuring_flag}\n"
                f"**Velocity 24h**: {txn.velocity_24h} txns / ${txn.velocity_amount_24h:,.2f}\n"
            )
            alerts_text = "\n".join(
                f"⚠️ [{a.framework.value}] {a.description}" for a in obs.alerts
            )
            return txn_text, alerts_text, obs.feedback

        def gradio_step(decision, reasoning, risks, regulations):
            from models import ComplianceDecision, RegulationFramework
            try:
                action = ComplianceAction(
                    decision=ComplianceDecision(decision),
                    reasoning=reasoning,
                    identified_risks=[r.strip() for r in risks.split(",") if r.strip()],
                    regulation_cited=[RegulationFramework(r.strip()) for r in regulations.split(",") if r.strip()],
                )
                obs = _env.step(action)
                status = f"Reward: {obs.reward:.4f} | Cumulative: {obs.cumulative_reward:.4f} | Done: {obs.done}"
                score_info = str(obs.score_breakdown) if obs.score_breakdown else ""
                return obs.feedback, status, score_info
            except Exception as e:
                return f"Error: {e}", "", ""

        with gr.Blocks(title="FinReg Compliance Simulator") as demo:
            gr.Markdown("# 🏦 AI Regulatory Compliance Simulator\n*Financial Transaction Review Environment*")
            with gr.Row():
                reset_btn = gr.Button("🔄 Reset Episode", variant="primary")
            txn_display = gr.Markdown(label="Transaction Details")
            alerts_display = gr.Markdown(label="Regulatory Alerts")
            feedback_out = gr.Textbox(label="Feedback", interactive=False)

            with gr.Row():
                decision_dd = gr.Dropdown(
                    choices=["approve", "reject", "escalate", "request_info", "flag_aml", "flag_fraud", "flag_sanctions"],
                    label="Decision",
                    value="escalate",
                )
                regulations_box = gr.Textbox(label="Regulations Cited (comma-separated, e.g. FATF,OFAC)", value="FATF")
            reasoning_box = gr.Textbox(label="Reasoning", lines=3, placeholder="Explain your compliance decision...")
            risks_box = gr.Textbox(label="Identified Risks (comma-separated)", placeholder="structuring, velocity, pep")
            step_btn = gr.Button("📋 Submit Decision", variant="secondary")

            step_feedback = gr.Textbox(label="Step Feedback", interactive=False)
            step_status = gr.Textbox(label="Reward / Status", interactive=False)
            score_box = gr.Textbox(label="Score Breakdown", interactive=False)

            reset_btn.click(gradio_reset, outputs=[txn_display, alerts_display, feedback_out])
            step_btn.click(
                gradio_step,
                inputs=[decision_dd, reasoning_box, risks_box, regulations_box],
                outputs=[step_feedback, step_status, score_box],
            )

        app = gr.mount_gradio_app(app, demo, path="/web")

    except ImportError:
        pass  # Gradio not installed — skip UI

def main():
    print("Server is running...")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
    main()
