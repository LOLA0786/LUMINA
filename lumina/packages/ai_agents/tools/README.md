# packages/ai-agents/tools

All reusable LangChain/LangGraph tools live here.

## Current tools
- graph_query.py → safe read access to the financial knowledge graph

## Rules (enforced)
- Tools must be @tool decorated
- Never hard-code credentials — use .env + os.getenv()
- Prefer read-only for agents unless explicit write tool is created
- Always parametrize queries ($var syntax)

## Where bugs hide (most common)
- Missing .env variables → connection fails
- Cypher syntax error → agent gets cryptic Neo4j error
- Forgetting to close driver → connection leaks in long-running processes
- Writing Cypher without $userId → security hole

## Testing
Add tests in packages/ai-agents/tests/test_tools.py
Example: mock driver + assert forbidden keywords rejected
