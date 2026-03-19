def generate_campaign(client):

    if client["loan"] > client["investment"]:
        return {
            "strategy": "Capital Protection + Balanced Growth",
            "message": "Given your high liabilities, we recommend a strategy that balances growth with strong downside protection.",
            "portfolio": {
                "equity": 0.6,
                "debt": 0.3,
                "gold": 0.1
            }
        }

    return {
        "strategy": "Growth",
        "message": "Maximize long-term wealth creation with equity-focused allocation."
    }


def run():
    client = {
        "age": 38,
        "salary": 500000,
        "loan": 30000000,
        "investment": 20000000
    }

    result = generate_campaign(client)

    print("CLIENT ANALYSIS → CAMPAIGN OUTPUT\n")
    print(result)

if __name__ == "__main__":
    run()
