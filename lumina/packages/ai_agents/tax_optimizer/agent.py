"""
Tax Optimization Agent for India (2026 tax regime)
Uses LangGraph for stateful reasoning + tool calling.
"""

import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from operator import add

from packages.ai_agents.core.base_agent import BaseFinancialAgent
from packages.ai_agents.tools.graph_query import query_user_financials

load_dotenv()

class TaxState(TypedDict):
    messages: Annotated[list[BaseMessage], add]
    user_id: str
    tax_year: str           # e.g. "AY 2026-27"
    regime: str             # "old" or "new"
    summary: dict
    recommendations: list[str]
    final_answer: str

class TaxOptimizationAgent(BaseFinancialAgent):
    def __init__(self):
        super().__init__()

    def get_tax_summary(self, state: TaxState) -> TaxState:
        user_id = state["user_id"]
        summary = self.get_user_summary(user_id)

        # Simple tax-relevant extraction
        income = summary["person"].get("monthlyIncomeINR", 0) * 12
        assets = [a["asset"]["currentValueINR"] for a in summary["assets"] if "currentValueINR" in a["asset"]]

        state["summary"] = {
            "annual_income": income,
            "total_assets_value": sum(assets),
            "asset_count": len(assets)
        }
        state["messages"].append(f"Retrieved tax-relevant summary for {user_id}")
        return state

    def analyze_tax(self, state: TaxState) -> TaxState:
        prompt = ChatPromptTemplate.from_template(
            """You are an Indian tax optimization expert (AY {tax_year}).

Current financial snapshot:
{summary}

User prefers regime: {regime}

Suggest optimizations under current Indian tax laws:
- 80C, 80D, HRA, NPS, home loan interest (old regime)
- Standard deduction, rebate u/s 87A (new regime)
- Capital gains (LTCG 12.5%, STCG slab rate)
- Tax-loss harvesting opportunities
- Any red flags (high income + no deductions)

Return concise list of recommendations.
"""
        )

        chain = prompt | self.llm

        response = chain.invoke({
            "tax_year": state["tax_year"],
            "summary": str(state["summary"]),
            "regime": state.get("regime", "new")
        })

        state["recommendations"] = response.content.split("\n")
        state["messages"].append("Tax analysis complete")
        return state

    def finalize(self, state: TaxState) -> TaxState:
        state["final_answer"] = "\n".join(state["recommendations"])
        return state

def build_tax_graph():
    workflow = StateGraph(TaxState)

    agent = TaxOptimizationAgent()

    workflow.add_node("get_summary", agent.get_tax_summary)
    workflow.add_node("analyze", agent.analyze_tax)
    workflow.add_node("finalize", agent.finalize)

    workflow.set_entry_point("get_summary")
    workflow.add_edge("get_summary", "analyze")
    workflow.add_edge("analyze", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()

# Quick test function
if __name__ == "__main__":
    graph = build_tax_graph()
    result = graph.invoke({
        "messages": [],
        "user_id": "user_123",
        "tax_year": "2026-27",
        "regime": "new"
    })
    print("Final Tax Recommendations:")
    print(result["final_answer"])
