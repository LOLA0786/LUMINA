from datetime import datetime

def evaluate_portfolio(client, allocation):
    """
    Simple mock logic — replace with Lumina engine later
    """

    equity = allocation.get("equity", 0)
    debt = allocation.get("debt", 0)
    small_cap = allocation.get("small_cap", 0)

    risk_flags = []
    approved = True

    # Rule 1: High small-cap exposure
    if small_cap > 0.25:
        risk_flags.append("Excessive small-cap exposure (>25%)")
        approved = False

    # Rule 2: Equity too high for moderate profile
    if client["risk_profile"] == "moderate" and equity > 0.70:
        risk_flags.append("Equity allocation too high for moderate risk profile")
        approved = False

    # Rule 3: Emergency buffer missing
    if client["liquid_buffer_months"] < 6:
        risk_flags.append("Insufficient emergency buffer (<6 months)")

    confidence = 0.85 if approved else 0.62

    return {
        "approved": approved,
        "confidence": confidence,
        "risk_flags": risk_flags,
        "timestamp": datetime.now().isoformat()
    }


def run_demo():
    print("======================================")
    print("LUMINA PMS TEST SUITE — ₹1Cr INVESTOR")
    print("======================================\n")

    # 👤 Client profile (Digital Twin style)
    client = {
        "name": "Rohan Mehta",
        "age": 38,
        "monthly_income": 250000,
        "investment_amount": 10000000,  # ₹1Cr
        "risk_profile": "moderate",
        "liquid_buffer_months": 4
    }

    print("CLIENT PROFILE:")
    print(client)

    print("\n--- PROPOSED PORTFOLIO ---")

    allocation = {
        "equity": 0.75,
        "debt": 0.15,
        "gold": 0.05,
        "small_cap": 0.35
    }

    print(allocation)

    print("\n--- LUMINA DECISION ENGINE ---")

    decision = evaluate_portfolio(client, allocation)

    print(f"Decision: {'APPROVED' if decision['approved'] else 'REJECTED'}")
    print(f"Confidence: {decision['confidence']*100:.1f}%")

    if decision["risk_flags"]:
        print("Risk Flags:")
        for flag in decision["risk_flags"]:
            print(f" - {flag}")

    print("\n--- RECOMMENDED ACTION ---")

    if not decision["approved"]:
        print("❌ Portfolio Rejected — Adjust Allocation")

        print("\nSuggested Fix:")
        print({
            "equity": 0.60,
            "debt": 0.30,
            "gold": 0.10,
            "small_cap": 0.15
        })
    else:
        print("✅ Portfolio Approved — Execute")

if __name__ == "__main__":
    run_demo()
