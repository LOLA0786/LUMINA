import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI  # native xAI compatible

from packages.ai_agents.tools.graph_query import query_user_financials

load_dotenv()

# Load API key FIRST
GROK_API_KEY = os.getenv("GROK_API_KEY")
if not GROK_API_KEY:
    raise ValueError("GROK_API_KEY not found in .env — check that it's set correctly")

# Use native xAI endpoint (for xai- prefixed keys)
llm = ChatOpenAI(
    model="grok-4-latest",           # or "grok-beta", "grok-4-0709" — check console.x.ai/models for exact name
    api_key=GROK_API_KEY,
    base_url="https://api.x.ai/v1",
    temperature=0.7
)

def get_user_financial_summary(user_id: str):
    # Get person details
    person_data = query_user_financials.invoke({
        'user_id': user_id,
        'cypher': 'MATCH (p:Person {userId: $userId}) RETURN p'
    })
    person = person_data[0]['p'] if person_data else {}

    # Get all owned assets + rel properties
    assets_data = query_user_financials.invoke({
        'user_id': user_id,
        'cypher': 'MATCH (u:Person {userId: $userId})-[r:OWNS]->(a) RETURN a, type(r), properties(r)'
    })

    summary = {
        "person": person,
        "owned_assets": [
            {
                "asset": row['a'],
                "relationship": row['type(r)'],
                "props": row['properties(r)']
            } for row in assets_data
        ]
    }
    return summary

def analyze_house_purchase(user_id: str, house_price: int = 30000000):
    summary = get_user_financial_summary(user_id)

    prompt = ChatPromptTemplate.from_template("""
    You are an AI CFO advising Chandan Galani in Mumbai.

    Analyze whether he can realistically buy a house worth ₹{house_price:,} in Bandra West.

    Current financial snapshot from his knowledge graph:
    {financial_summary}

    Key factors to consider:
    - Monthly income vs estimated EMI (~₹185,000 for this property)
    - Existing net worth (stocks, other assets)
    - Risk tolerance: moderate
    - Concentration risk (e.g. heavy equity exposure)
    - Indian tax implications (home loan interest deduction up to ₹2 lakh/year, capital gains if selling assets)
    - Liquidity and emergency buffer

    Give a brutally honest recommendation:
    - Yes / No / Maybe
    - One-sentence rationale
    - 2–3 concrete actions if needed (e.g. "Sell 15% of small-cap stocks", "Take ₹2cr loan for tax benefits")

    Keep response concise, professional, and data-backed.
    """)

    chain = prompt | llm

    response = chain.invoke({
        "house_price": house_price,
        "financial_summary": str(summary).replace("'", '"')  # clean for prompt
    })

    return response.content
