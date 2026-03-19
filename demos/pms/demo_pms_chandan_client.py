from datetime import datetime

def analyze_client():
    client = {
        "name": "Chandan",
        "age": 38,
        "monthly_income": 500000,   # ₹5L
        "home_loan": 30000000,      # ₹3Cr
        "investment_amount": 20000000,  # ₹2Cr
        "risk_profile": "moderate_aggressive",
        "liquidity_buffer_months": 3
    }
    return client


def evaluate_portfolio(client, allocation):
    risk_flags = []
    approved = True

    equity = allocation.get("equity", 0)
    small_cap = allocation.get("small_cap", 0)

    # Loan pressure check
    if client["home_loan"] > 2 * client["investment_amount"]:
        risk_flags.append("High leverage: Loan significantly exceeds investments")

    # Liquidity check
    if client["liquidity_buffer_months"] < 6:
        risk_flags.append("Low emergency buffer (<6 months)")

    # Equity check
    if equity > 0.75:
        risk_flags.append("Equity allocation too aggressive under high debt")
        approved = False

    # Small cap check
    if small_cap > 0.25:
        risk_flags.append("Excessive small-cap exposure (>25%)")
        approved = False

    confidence = 0.88 if approved else 0.64

    return {
        "approved": approved,
        "confidence": confidence,
        "risk_flags": risk_flags
    }


def run_demo():
    print("==========================================")
    print("LUMINA AI — PMS CLIENT DECISION ENGINE")
    print("==========================================\n")

    client = analyze_client()

    print("CLIENT PROFILE:")
    print(f"Name: {client['name']}")
    print(f"Age: {client['age']}")
    print(f"Monthly Income: ₹{client['monthly_income']:,}")
    print(f"Home Loan: ₹{client['home_loan']:,}")
    print(f"Investment Capital: ₹{client['investment_amount']:,}\n")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("PROPOSED PMS ALLOCATION")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    allocation = {
        "equity": 0.80,
        "debt": 0.10,
        "gold": 0.05,
        "small_cap": 0.30
    }

    print(allocation)

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("LUMINA DECISION REPORT")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    decision = evaluate_portfolio(client, allocation)

    status = "APPROVED" if decision["approved"] else "REJECTED"

    print(f"Status: {status}")
    print(f"Confidence: {decision['confidence']*100:.1f}%\n")

    print("KEY RISK INSIGHTS:")
    for flag in decision["risk_flags"]:
        print(f" - {flag}")

    print("\nIMPACT ANALYSIS:")
    print("→ High EMI pressure reduces risk-taking capacity")
    print("→ Capital volatility can impact loan servicing ability")
    print("→ Liquidity risk elevated\n")

    print("WHAT LUMINA RECOMMENDS:")
    print("✔ Reduce equity to 60–65%")
    print("✔ Cap small-cap exposure to 15%")
    print("✔ Increase debt allocation for stability")
    print("✔ Build 6–9 months emergency buffer\n")

    print("SUGGESTED PORTFOLIO:")
    print({
        "equity": 0.65,
        "debt": 0.25,
        "gold": 0.10,
        "small_cap": 0.15
    })

    print("\nFINAL DECISION:")
    if decision["approved"]:
        print("✅ APPROVED — Proceed with execution")
    else:
        print("🚫 BLOCKED — Reallocation required")

    print("\nAudit ID:", datetime.now().strftime("%Y%m%d%H%M%S"))
    print("\n“Every ₹ deployed is first approved by Lumina.”")


if __name__ == "__main__":
    run_demo()
