# LUMINA — AI Agents Package

> Financial reasoning engine. Consented. Auditable. Composable.

## Architecture

```
ai_agents/
├── core/           Base agent class, types, consent gate
├── graph/          Wealth graph client (Neo4j abstraction)
├── memory/         Session memory for multi-agent reasoning
├── agents/
│   ├── house_purchase/   Affordability + EMI stress test
│   ├── portfolio_agent/  Allocation drift + rebalancing
│   ├── tax_agent/        Old vs New regime optimiser
│   ├── retirement_agent/ Corpus projection + SIP calculator
│   └── risk_agent/       Multi-dimensional risk scoring
├── planner/        Master orchestrator (FinancialPlanner)
├── tools/          Shared formatters + utilities
└── tests/          Pytest integration tests
```

## Quickstart

```python
from lumina.packages.ai_agents.graph.wealth_graph import WealthGraph, UserFinancialProfile
from lumina.packages.ai_agents.planner.financial_planner import FinancialPlanner, PlannerIntent, PlannerRequest

graph = WealthGraph()
graph.load_fixture(your_profile)

planner = FinancialPlanner(graph)
response = planner.run(PlannerRequest(
    user_id="user_001",
    intent=PlannerIntent.FULL_REVIEW,
))

print(response.executive_summary)
```

## Design Principles

1. **Consent-first** — every agent checks consent level before reasoning
2. **Typed I/O** — all inputs/outputs are Pydantic models
3. **Traceable** — every reasoning step is logged in `reasoning_trace`
4. **Composable** — agents are independent; planner composes them
5. **Auditable** — every invocation logs to structured audit trail
