---
title: FinReg Compliance Env
emoji: 🏦
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
  - compliance
  - finance
  - aml
  - reinforcement-learning
---

# 🏦 AI Regulatory Compliance Simulator for Financial Transactions

**FinReg Compliance Env** is an [OpenEnv](https://github.com/meta-pytorch/OpenEnv)-compatible reinforcement learning environment where an AI agent acts as a **financial compliance officer**, reviewing suspicious financial transactions and making regulatory decisions across multiple international frameworks.

---

## 🎯 Motivation

Financial institutions process millions of transactions daily. Compliance officers must apply complex, overlapping regulatory frameworks — BSA, FATF, OFAC, MiFID2, GDPR, PCI DSS — to detect money laundering, sanctions violations, fraud, and market manipulation.

This environment trains and evaluates AI agents on this **genuinely difficult real-world task** with:
- Authentic transaction scenarios modeled on real financial crime typologies
- Multi-framework regulatory alert systems
- Graded scoring that rewards nuanced compliance reasoning

---

## 🌍 Action Space

The agent submits a **`ComplianceAction`**:

| Field | Type | Description |
|---|---|---|
| `decision` | enum | One of: `approve`, `reject`, `escalate`, `request_info`, `flag_aml`, `flag_fraud`, `flag_sanctions` |
| `reasoning` | string | Agent's detailed compliance analysis |
| `identified_risks` | list[str] | Risk factors the agent identified |
| `regulation_cited` | list[enum] | Regulations cited: `FATF`, `BSA`, `OFAC`, `MiFID2`, `GDPR`, `PCI_DSS` |
| `additional_info_requested` | string? | Required info (when `decision = request_info`) |

## 👁️ Observation Space

The agent receives a **`ComplianceObservation`**:

| Field | Type | Description |
|---|---|---|
| `transaction` | Transaction | Full transaction details (amount, parties, flags, velocity) |
| `alerts` | list[RegulatoryAlert] | Triggered regulatory alerts with severity and rule IDs |
| `task_description` | string | Task objective |
| `task_difficulty` | string | easy / medium / hard |
| `reward` | float | Reward for last action |
| `cumulative_reward` | float | Total episode reward |
| `done` | bool | Episode completion flag |
| `feedback` | string | Human-readable explanation of last decision quality |
| `score_breakdown` | dict | Detailed scoring breakdown (revealed on done=True) |

---

## 📋 Tasks

### Task 1: `easy_structuring` (Easy)
**BSA Structuring / Smurfing Detection**

A retail customer makes 4 wire transfers totaling $38,200 in 24 hours, all just below the $10,000 CTR reporting threshold, to a Cayman Islands shell company. One prior SAR on file.

- **Correct Decision**: `flag_aml`
- **Key Regulations**: BSA (31 CFR 1010.314), FATF R13
- **Target Score**: 0.80+

---

### Task 2: `medium_pep_sanctions` (Medium)
**Politically Exposed Person + OFAC Sanctions**

A $250,000 SWIFT transfer from a Russian national who is a Politically Exposed Person (PEP) to a Swiss holding company. Russia is under OFAC sectoral sanctions (Executive Order 13662). Enhanced Due Diligence required.

- **Correct Decision**: `flag_sanctions`
- **Key Regulations**: OFAC EO-13662, FATF R12
- **Target Score**: 0.65+

---

### Task 3: `hard_crypto_layering` (Hard)
**Multi-Framework Layered Financial Crime**

A German crypto-to-fiat firm sends $47K to a Luxembourg asset manager — but velocity data reveals $520K across 12 transactions in 24h (840% above 30-day average), with after-hours timing. Multiple simultaneous violations:
- **MiFID2**: Wash trading / market manipulation signals
- **FATF R15**: Crypto chain-hopping / layering
- **GDPR Art. 6**: Personal data transmitted without consent record
- **PCI DSS 4.0**: Tokenization standard gap

- **Correct Decision**: `escalate`
- **Key Regulations**: MiFID2, FATF, GDPR
- **Target Score**: 0.50+

---

## 🚀 Setup & Usage

### Option 1: Docker (Recommended)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/finreg-compliance-env
cd finreg-compliance-env

# Build and run (port 7860 — matches HuggingFace Spaces requirement)
docker build -t finreg-compliance-env .
docker run -p 7860:7860 -e FINREG_TASK=easy_structuring finreg-compliance-env
```

> ⚠️ **HuggingFace Spaces requires port 7860.** The Dockerfile is already configured for this.

### Option 2: Local Python

```bash
pip install -r requirements.txt
cd finreg_compliance_env
uvicorn server.app:app --port 7860
```

### API Endpoints

```bash
# Health check
curl http://localhost:7860/health

# Reset episode
curl -X POST http://localhost:7860/reset

# Step with compliance action
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "flag_aml",
    "reasoning": "Classic structuring pattern: multiple sub-$10k transactions",
    "identified_risks": ["structuring", "smurfing", "ctr threshold"],
    "regulation_cited": ["BSA", "FATF"]
  }'

# Get current state
curl http://localhost:7860/state
```

---

## 🤖 Running the Baseline Inference Script

```bash
# Set environment variables
export HF_TOKEN=your_hf_token_here
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
export FINREG_ENV_URL=http://localhost:8000

# Run inference against all 3 tasks
python inference.py
```
## 📁 Project Structure

```
finreg-compliance-env/
├── models.py              # Pydantic typed models (Action, Observation, State)
├── tasks.py               # Task definitions + graders (easy/medium/hard)
├── openenv.yaml           # OpenEnv spec manifest
├── requirements.txt       # Python dependencies
├── inference.py           # Baseline inference script (MANDATORY)
├── Dockerfile             # Container build
├── README.md              # This file
└── server/
    ├── app.py             # FastAPI server
    ├── finreg_environment.py  # Core environment logic
    └── requirements.txt   # Server dependencies
```

## 📊 Baseline Validation

```bash
# Install openenv-core
pip install openenv-core

# Validate
openenv validate
```

---

## 🏛️ Regulatory Frameworks Modelled

| Framework | Coverage |
|---|---|
| **BSA** (Bank Secrecy Act) | CTR thresholds, structuring, SAR filing |
| **FATF** | AML typologies, PEP rules, crypto guidance (R15) |
| **OFAC** | Sanctions lists, SDN checks, EO violations |
| **MiFID2** | Market manipulation, wash trading, MAR rules |
| **GDPR** | Art. 6 lawful basis, data minimization |
| **PCI DSS 4.0** | Tokenization requirements |

---

*Built for the Meta PyTorch Hackathon by Scaler — OpenEnv Round 1 Bootcamp*
