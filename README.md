<div align="center">
```
██╗     ██╗   ██╗███╗   ███╗██╗███╗   ██╗ █████╗
██║     ██║   ██║████╗ ████║██║████╗  ██║██╔══██╗
██║     ██║   ██║██╔████╔██║██║██╔██╗ ██║███████║
██║     ██║   ██║██║╚██╔╝██║██║██║╚██╗██║██╔══██║
███████╗╚██████╔╝██║ ╚═╝ ██║██║██║ ╚████║██║  ██║
╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝
```

**Financial Operating System**

*Not a robo-advisor. Not a chatbot. Financial infrastructure.*

[![CI](https://github.com/LOLA0786/LUMINA/actions/workflows/ci.yml/badge.svg)](https://github.com/LOLA0786/LUMINA/actions)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-58%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## What is LUMINA?

Most fintech is advice software:
```
User → Agents → Advice
```

LUMINA is financial infrastructure:
```
User → Financial Digital Twin → Event Reactor → Agent Debate
     → PrivateVault Governance → Merkle Audit Log → Execution
```

Every financial event in a person's life triggers an immediate,
governed, auditable AI response. Not a chatbot reply. An action.

---

## Architecture
```
┌─────────────────────────────────────────────────────────┐
│                  LUMINA FINANCIAL OS                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  FinancialTwin          EventReactor                    │
│  ├── bank_accounts      ├── salary_credited             │
│  ├── demat_holdings     ├── market_crash                │
│  ├── property_assets    ├── goal_at_risk                │
│  ├── loans              └── loan_closed                 │
│  ├── insurance                   │                      │
│  ├── income_streams              ▼                      │
│  ├── tax_profile        AgentDebate                     │
│  └── financial_goals    ├── RiskAgent      (priority 1) │
│           │             ├── RetirementAgent (priority 2) │
│           │             ├── PortfolioAgent  (priority 3) │
│     Git-for-money       └── TaxAgent       (priority 4) │
│     Hash-linked                  │                      │
│     Tamper-evident               ▼                      │
│                         PolicyEngine (PrivateVault)     │
│                         ├── Consent check               │
│                         ├── Liquidity check             │
│                         ├── Concentration check         │
│                         └── Fiduciary check             │
│                                  │                      │
│                                  ▼                      │
│                         AuditLedger (Merkle)            │
│                         └── Tamper-evident receipt      │
│                                                         │
│  FastAPI Layer          AdvisorBrief                    │
│  ├── 10 endpoints       ├── P0/P1/P2 alerts             │
│  ├── Pydantic V2        ├── Portfolio drift             │
│  └── Auto docs          └── Merkle root display         │
└─────────────────────────────────────────────────────────┘
```

---

## Quickstart
```bash
git clone https://github.com/LOLA0786/LUMINA.git
cd LUMINA
pip install -e ".[dev]"

# Run the full demo — 3 clients, 6 events, full pipeline
python -m lumina.scripts.seed_demo

# Start the API
uvicorn lumina.api.app:app --reload --port 8000
# Docs: http://localhost:8000/docs
```

---

## Live Demo Output
```
STEP 1 — Building Financial Digital Twins
  ✓ rohan_mehta       net_worth=₹0.10Cr   snapshots=8
  ✓ sunita_krishnan   net_worth=₹3.13Cr   snapshots=11
  ✓ vikram_nair       net_worth=₹-0.01Cr  snapshots=6

STEP 2 — Event Reactor (event → agent → decision < 0.5ms)
  ✓ salary_credited  → 3 agents → unanimous → allowed
  ✓ market_crash     → 3 agents → unanimous → allowed
  ✓ goal_at_risk     → 2 agents → majority  → flagged
  ✓ loan_closed      → 2 agents → majority  → flagged

STEP 3 — AI Advice Engine
  rohan_mehta      Health: NEEDS WORK (53%)
  sunita_krishnan  Health: GOOD      (70%)
  vikram_nair      Health: NEEDS WORK (43%)

STEP 4 — PrivateVault Merkle Governance
  Decisions : 12
  Merkle root: 23dd32db8933c82e...
  Chain      : ✓ VALID
  Allowed/Flagged/Blocked: 10 / 2 / 0

STEP 5 — Advisor Morning Brief
  P0: vikram_nair LIQUIDITY_RISK — ₹1.5L at stake
```

---

## Key Design Decisions

**1. Immutable Digital Twin**
Every financial change creates a new hash-linked snapshot.
The chain is cryptographically verifiable. Nothing is deleted.
Think: Git for money.

**2. Event-Driven Agents**
Agents don't wait to be asked. They react automatically.
`salary_credited` → tax + retirement + risk agents run in <0.5ms.

**3. Multi-Agent Debate**
Agents disagree. The system arbitrates by priority weight.
RiskAgent always has the loudest voice.

**4. PrivateVault Governance**
Every AI action goes through 6 policy checks before execution.
Every decision is Merkle-hashed and tamper-evident.
Compatible with [PrivateVault-AI-Agent-Architecture](https://github.com/LOLA0786/PrivateVault-AI-Agent-Architecture).

**5. Explainable by design**
Every recommendation includes reasoning trace, confidence,
assumptions, and a cryptographic audit receipt.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/users` | Onboard a user |
| GET | `/api/v1/users/{id}` | Get twin status |
| POST | `/api/v1/users/{id}/accounts` | Add bank account |
| POST | `/api/v1/users/{id}/holdings` | Add demat holding |
| POST | `/api/v1/users/{id}/loans` | Add loan |
| POST | `/api/v1/users/{id}/events` | Fire financial event |
| POST | `/api/v1/users/{id}/advice` | Get AI advice |
| GET | `/api/v1/advisor/{id}/brief` | RM morning brief |
| GET | `/api/v1/health` | System health |

---

## Test Suite
```bash
python -m pytest lumina/ -v
# 58 tests | 4 test classes | 0 warnings
```
```
TestFinancialTwin    ✓ 6 tests  — chain validity, mutations, tamper detection
TestEventEngine      ✓ 5 tests  — event routing, handler firing, severity
TestGovernance       ✓ 7 tests  — policy checks, Merkle integrity, tamper detection
TestFinancialOS      ✓ 10 tests — full pipeline, advisor brief, session tracking
```

---

## Roadmap

- [x] Financial Digital Twin (immutable, hash-linked)
- [x] Event Engine (12 event types)
- [x] Multi-Agent Debate Engine
- [x] PrivateVault Governance Layer
- [x] Merkle Audit Ledger
- [x] FastAPI layer (10 endpoints)
- [x] SQLite persistence (Postgres-ready)
- [x] Structured logging + health checks
- [x] Event Reactor (event→agent<0.5ms)
- [ ] Cloud Run deployment
- [ ] Bank statement parser → Digital Twin
- [ ] LLM natural language interface
- [ ] Real-time market feed integration
- [ ] Mobile SDK

---

## Related

[PrivateVault-AI-Agent-Architecture](https://github.com/LOLA0786/PrivateVault-AI-Agent-Architecture)
— Runtime governance and Merkle transparency log that powers LUMINA's policy engine.

---

<div align="center">
Built with Python 3.12 · FastAPI · Pydantic V2 · SQLite/Postgres · PrivateVault
</div>
