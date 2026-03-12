import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from packages.ai_agents.tools.graph_query import query_user_financials

load_dotenv()

class BaseFinancialAgent:
    def __init__(self):
        self.api_key = os.getenv("GROK_API_KEY")
        if not self.api_key:
            raise ValueError("GROK_API_KEY missing in .env")

        self.llm = ChatOpenAI(
            model="grok-4-latest",           # change to exact model name from console.x.ai
            api_key=self.api_key,
            base_url="https://api.x.ai/v1",
            temperature=0.6
        )

    def get_user_summary(self, user_id: str) -> dict:
        person = query_user_financials.invoke({
            'user_id': user_id,
            'cypher': 'MATCH (p:Person {userId: $userId}) RETURN p'
        })

        assets = query_user_financials.invoke({
            'user_id': user_id,
            'cypher': 'MATCH (u:Person {userId: $userId})-[r:OWNS]->(a) RETURN a, type(r), properties(r)'
        })

        return {
            "person": person[0]['p'] if person else {},
            "assets": assets
        }
