# House Purchase Analyzer Agent

First production agent: answers "Can I buy a ₹3 crore house?"

## Flow (LangGraph)
1. Retrieve user financial graph snapshot
2. Calculate affordability (salary + cashflow + existing EMIs + risk)
3. Simulate tax impact + portfolio rebalance
4. Return yes/no + concrete actions

## Where bugs hide
- Wrong risk tolerance pull from graph
- Decimal precision in EMI calcs
- Stale graph data → always refresh before query

Run: see tests/
