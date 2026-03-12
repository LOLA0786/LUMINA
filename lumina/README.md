# LUMINA

AI Financial Life Operating System  
"Bloomberg Terminal for humans" — India-first, advisor-first, then retail.

## How to navigate this codebase (2040-proof)
1. Want business logic? → domains/
2. Want AI agents? → packages/ai-agents/
3. Want shared types/contracts? → packages/core/
4. Want the knowledge graph? → packages/graph/
5. Want the actual API? → apps/backend/
6. Bug in taxes? → domains/taxes/ (not anywhere else)

Every folder has its own README.md telling you exactly what lives there.

## Architecture (Clean + DDD)
- domains/ = pure business truth (models + services)
- packages/ = reusable infrastructure
- apps/ = delivery mechanisms only

We will never let the codebase become spaghetti. Ever.

Current tech (2026):
- Backend: Python 3.12 + FastAPI + LangGraph
- Graph: Neo4j + pgvector
- Frontend: Next.js 15 + shadcn/ui (Apple-smooth)
- Observability: OpenTelemetry + Sentry everywhere

First command after this: `cd apps/backend && make setup`
