def run():
    print("\n========== CLIENT PITCH ==========")
    print("""
Chandan, with a ₹3Cr loan and ₹2Cr investment,
an aggressive strategy could expose you to large drawdowns.

We recommend a balanced approach that protects capital while enabling growth.
""")

    print("\n========== LUMINA DECISION ==========")
    print("""
Status: CONDITIONAL APPROVAL
Conditions:
- Equity <= 65%
- Small cap <= 15%
- Maintain 6+ months liquidity
""")

    print("\n========== RECOMMENDED PORTFOLIO ==========")
    print({
        "equity": 0.65,
        "debt": 0.25,
        "gold": 0.10
    })

    print("\n========== EXPECTED OUTCOME ==========")
    print("""
5-Year Projection:
- Expected CAGR: 10–12%
- Portfolio Growth: ₹2Cr → ₹3.2–₹3.5Cr

Risk:
- Expected drawdown: 15–20%
""")

    print("\n========== IF WRONG STRATEGY USED ==========")
    print("""
Aggressive Allocation Scenario:
- Drawdown: 30–40%
- Potential Loss: ₹60L–₹80L

With ₹3Cr loan:
- Financial stress risk: HIGH
- Recovery time: 4–6 years
""")

    print("\n“Every ₹ deployed is first approved by Lumina.”")

if __name__ == "__main__":
    run()
