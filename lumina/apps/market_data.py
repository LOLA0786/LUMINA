import yfinance as yf

def get_stock_data(symbol="RELIANCE.NS"):
    stock = yf.Ticker(symbol)
    data = stock.history(period="5d")

    latest = data.iloc[-1]

    return {
        "price": float(latest["Close"]),
        "volume": float(latest["Volume"]),
        "high": float(latest["High"]),
        "low": float(latest["Low"])
    }

if __name__ == "__main__":
    print(get_stock_data())
