def generate_campaign(client):

    high_leverage = client["loan"] > client["investment"]

    if high_leverage:
        return {
            "client_pitch": f"""
Chandan, with a ₹{client['loan']/1e7:.1f}Cr loan and ₹{client['investment']/1e7:.1f}Cr investment,
an aggressive strategy could expose you to large drawdowns.

We recommend a balanced approach that protects capital while enabling growth.
""",

            "advisor_insight": {
                "client_type": "High Income + High Leverage",
                "risk_level": "Elevated",
                "priority": [
                    "Capital Protection",
                    "Liquidity Buffer",
                    "Controlled Growth"
                ]
            },

            "decision": {
                "status": "CONDITIONAL APPROVAL",
                "conditions": [
                    "Equity <= 65%",
                    "Small cap <= 15%",
                    "Minimum 6 month liquidity buffer"
                ]
            },

            "portfolio": {
                "equity": 0.65,
                "debt": 0.25,
                "gold": 0.10
            }
        }

    return {"message": "Standard growth strategy"}


def run():
    client = {
        "name": "Chandan",
        "age": 38,
        "salary": 500000,
        "loan": 30000000,
        "investment": 20000000
    }

    result = generate_campaign(client)

    print("\n========== CLIENT PITCH ==========")
    print(result["client_pitch"])

    print("\n========== ADVISOR INSIGHT ==========")
    print(result["advisor_insight"])

    print("\n========== LUMINA DECISION ==========")
    print(result["decision"])

    print("\n========== PORTFOLIO ==========")
    print(result["portfolio"])


if __name__ == "__main__":
    run()
