from lumina.apps.market_data import get_stock_data
from lumina.apps.news_feed import get_news

def run_demo():
    print("====== LUMINA PMS ENGINE ======\n")

    symbol = "RELIANCE.NS"

    market = get_stock_data(symbol)
    news = get_news("Reliance")

    print("MARKET DATA:")
    print(market)

    print("\nNEWS SIGNALS:")
    for n in news:
        print("-", n["title"])

    print("\n--- AI DECISION ---")

    # Replace later with real Lumina engine
    if market["price"] > 2400:
        decision = "APPROVED"
    else:
        decision = "REJECTED"

    print(f"Decision: {decision}")

if __name__ == "__main__":
    run_demo()
