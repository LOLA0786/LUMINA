<div align="center">

```
██╗     ██╗   ██╗███╗   ███╗██╗███╗   ██╗ █████╗
██║     ██║   ██║████╗ ████║██║████╗  ██║██╔══██╗
██║     ██║   ██║██╔████╔██║██║██╔██╗ ██║███████║
██║     ██║   ██║██║╚██╔╝██║██║██║╚██╗██║██╔══██║
███████╗╚██████╔╝██║ ╚═╝ ██║██║██║ ╚████║██║  ██║
╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝
```

**Financial Intelligence Infrastructure**

*A consented wealth data graph with AI reasoning for advisors, banks, and fintech platforms.*

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-3%2F3%20passing-22c55e?style=flat-square)](./lumina/packages/ai_agents/tests)
[![Pydantic](https://img.shields.io/badge/Pydantic-V2-E92063?style=flat-square)](https://docs.pydantic.dev)
[![License](https://img.shields.io/badge/License-Proprietary-gray?style=flat-square)]()
[![Status](https://img.shields.io/badge/Status-Active%20Development-f59e0b?style=flat-square)]()

</div>

---

## What is LUMINA?

Most "AI finance apps" are ChatGPT with a money emoji.

LUMINA is not that.

LUMINA is **financial reasoning infrastructure** — a composable engine that ingests a user's complete wealth graph (assets, liabilities, goals, income, risk profile) and runs structured, auditable, consent-gated reasoning across every dimension of their financial life.

Built for the layer **beneath** the UI. The layer banks, advisors, and fintech platforms plug into.

---

## The Problem We're Solving

| Today | With LUMINA |
|---|---|
| Financial advice is locked inside expensive advisors | Systematic reasoning available at API scale |
| AI finance tools hallucinate numbers | Every output has a typed schema + reasoning trace |
| User data flows without consent tracking | Consent gate on every agent invocation |
| Generic chatbot responses | Domain-correct logic (RBI norms, Indian tax slabs, FOIR limits) |
| Black-box recommendations | Full audit trail — regulator friendly |

---

## Architecture

```
lumina/
├── packages/
│   └── ai_agents/
│       ├── core/               ← Base agent: consent gate, audit trail, typed I/O
│       ├── graph/              ← WealthGraph: Neo4j abstraction over user financial data
│       ├── memory/             ← SessionMemory: inter-agent context passing
│       ├── agents/
│       │   ├── house_purchase/ ← EMI calc, LTV check, stress test, affordability verdict
│       │   ├── portfolio_agent/← Drift analysis, rebalancing recommendations
│       │   ├── tax_agent/      ← Old vs New regime optimiser, 80C/80D/NPS tips
│       │   ├── retirement_agent← Corpus projection, SIP gap calculator
│       │   └── risk_agent/     ← Concentration, liquidity, leverage, insurance scoring
│       ├── planner/            ← FinancialPlanner: master orchestrator
│       ├── tools/              ← Shared formatters, INR notation, report renderer
│       └── tests/              ← Pytest integration suite
├── apps/                       ← API servers, frontends (coming)
├── domains/                    ← Core business domain logic
├── infrastructure/             ← Docker, cloud config
└── docker-compose.yml
```

---

## The Reasoning Engine

Every agent follows the same contract:

```
Input (typed Pydantic) → Consent Check → Domain Reasoning → Output (typed Pydantic + trace)
```

No magic strings. No silent failures. No hallucinated numbers.

### Agents

#### 🏠 House Purchase Agent
```
Can I afford this property?
```
- Computes max loan eligibility (60x income, RBI 75/80% LTV cap)
- Calculates EMI at requested rate
- Runs +200bps rate shock stress test
- Checks down-payment gap vs liquid assets
- Returns: `AFFORDABLE` | `STRETCH` | `NOT_ADVISED`

#### 📊 Portfolio Agent
```
Is my money allocated correctly?
```
- Computes current allocation across asset classes
- Derives target allocation from age + risk score (100-age rule, adjusted)
- Flags drift beyond configurable threshold
- Returns ranked rebalancing actions with INR amounts

#### 🧾 Tax Agent
```
Which regime should I choose, and what am I missing?
```
- Full FY 2024-25 slab calculations (old and new regime)
- 80C, 80D, HRA, NPS deduction optimisation
- LTCG / STCG tax on equity and debt
- Returns recommended regime + specific investment actions to reduce liability

#### 🌅 Retirement Agent
```
Can I retire at 55? What SIP do I need?
```
- Projects corpus at retirement using SIP FV + existing portfolio compounding
- Inflation-adjusts target spend over retirement horizon
- Uses real rate of return for sustainable withdrawal modelling
- Returns: on-track status, surplus/shortfall, recommended SIP correction

#### 🛡️ Risk Agent
```
Where am I exposed?
```
Four independent risk dimensions, scored 0→1:
- **Concentration** — single asset > 30% of portfolio
- **Liquidity** — liquid assets vs 6-month emergency fund
- **Leverage** — debt-to-income ratio against safe thresholds
- **Insurance** — life cover vs income replacement requirement

#### 🧠 Financial Planner (Master Orchestrator)
```python
planner.run(PlannerRequest(user_id="u001", intent=PlannerIntent.FULL_REVIEW))
```
- Selects and sequences relevant agents based on intent
- Passes shared context via `SessionMemory`
- Synthesises composite financial health score
- Returns executive summary + full agent result map

---

## Quickstart

```bash
git clone https://github.com/LOLA0786/LUMINA.git
cd LUMINA
pip install -e . --break-system-packages
```

```python
from lumina.packages.ai_agents.graph.wealth_graph import (
    WealthGraph, UserFinancialProfile, AssetNode, LiabilityNode
)
from lumina.packages.ai_agents.planner.financial_planner import (
    FinancialPlanner, PlannerIntent, PlannerRequest
)
from lumina.packages.ai_agents.core.base_agent import ConsentLevel

# Build a user profile
profile = UserFinancialProfile(
    user_id="user_001",
    monthly_income_inr=150000,
    monthly_expenses_inr=70000,
    age=32,
    risk_score=0.65,
    assets=[
        AssetNode("a1", "equity", 800000),
        AssetNode("a2", "cash", 200000),
        AssetNode("a3", "real_estate", 3000000),
    ],
    liabilities=[
        LiabilityNode("l1", "home_loan", 2000000, 8.5, 180),
    ],
)

# Load into graph
graph = WealthGraph()
graph.load_fixture(profile)

# Run full financial review
planner = FinancialPlanner(graph)
response = planner.run(PlannerRequest(
    user_id="user_001",
    intent=PlannerIntent.FULL_REVIEW,
    consent_level=ConsentLevel.READ_ONLY,
    params={"target_retirement_age": 55, "monthly_sip_inr": 20000},
))

print(response.executive_summary)
# → Financial Health: Good (72%) | Risk Flags: 1 active | Retirement: On Track ✓ | Tax: Use NEW regime | Potential saving ₹18,200
```

---

## Run Tests

```bash
cd ~/LUMINA
python -m pytest lumina/packages/ai_agents/tests/ -v
```

```
tests/test_planner.py::test_house_purchase_affordable   PASSED
tests/test_planner.py::test_full_financial_review       PASSED
tests/test_planner.py::test_consent_blocked             PASSED

3 passed, 0 warnings in 0.23s
```

---

## Design Principles

**1. Consent-first**
Every agent checks `ConsentLevel` before executing. `NONE` → blocked. No exceptions. Built for DPDP Act, SEBI, RBI compliance from day one.

**2. Typed everywhere**
Inputs and outputs are Pydantic V2 models. If data doesn't match the schema, it fails loudly at the boundary — not silently inside business logic.

**3. Reasoning traces**
Every agent output includes a `reasoning_trace: list[str]` — a step-by-step log of how the conclusion was reached. Auditable. Explainable. Regulator-ready.

**4. Graph-abstracted**
Agents never touch a database directly. They query `WealthGraph`. Swap Neo4j for Neptune for a JSON fixture for tests — zero agent code changes.

**5. Composable by design**
Agents are independent units. The planner composes them. `SessionMemory` lets them share context. Adding a new agent is additive — nothing breaks.

---

## Roadmap

```
✅ Phase 1 — Core Reasoning Engine       (complete)
   Base agent, WealthGraph, 5 agents, Planner, Tests

🔄 Phase 2 — API Layer                   (next)
   FastAPI endpoints, auth middleware, rate limiting

⬜ Phase 3 — LLM Bridge
   Natural language → PlannerRequest routing via Claude/GPT

⬜ Phase 4 — Data Ingestion
   Bank statement parser → WealthGraph population

⬜ Phase 5 — Platform SDK
   NPM + PyPI packages for advisor/bank integration
```

---

## Who This Is For

| Persona | How they use LUMINA |
|---|---|
| **Wealth advisors** | Run full financial review for clients in seconds, with traceable reasoning |
| **Fintech platforms** | Embed financial intelligence as an API — no ML team required |
| **Banks** | Consent-gated profile enrichment + automated advisory layer |
| **Investors** | A financial reasoning engine with Indian domain depth, not a chatbot |

---

## Built With

- **Python 3.12** — type hints throughout
- **Pydantic V2** — schema enforcement at every boundary
- **Pytest** — integration test suite
- **Neo4j-ready** — WealthGraph abstraction (swap driver, not code)
- **Google Cloud Shell** — developed and deployed on GCP

---

 

*LUMINA is infrastructure. Build on it.*

**[View Source](https://github.com/LOLA0786/LUMINA) · Built by [@LOLA0786](https://github.com/LOLA0786)**

 
