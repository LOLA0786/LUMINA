import requests

API_KEY = "YOUR_API_KEY"

def get_news(query="Reliance"):
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={API_KEY}&pageSize=3"

    response = requests.get(url)
    articles = response.json().get("articles", [])

    return [
        {
            "title": a["title"],
            "source": a["source"]["name"]
        }
        for a in articles
    ]

if __name__ == "__main__":
    print(get_news())
