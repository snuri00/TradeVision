import re
import feedparser
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote
from googlenewsdecoder import new_decoderv1
from trader.config import MARKETAUX_API_KEY


def _resolve_google_news_url(google_url: str) -> str:
    if "news.google.com" not in google_url:
        return google_url
    try:
        result = new_decoderv1(google_url)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception:
        pass
    return google_url


def fetch_google_news(query: str = None, lang: str = "en", max_results: int = 15) -> list[dict]:
    if query:
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl={lang}&gl=US&ceid=US:{lang}"
    else:
        url = f"https://news.google.com/rss?hl={lang}&gl=US&ceid=US:{lang}"

    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:max_results]:
        source_obj = entry.get("source", {})
        source_name = source_obj.get("title", "Unknown")
        title = entry.get("title", "")
        raw_url = entry.get("link", "")
        real_url = _resolve_google_news_url(raw_url)

        articles.append({
            "title": title,
            "source": source_name,
            "url": real_url,
            "published_at": entry.get("published", ""),
            "category": "google_news",
        })
    return articles


def fetch_marketaux_news(query: str = None, limit: int = 10) -> list[dict]:
    if not MARKETAUX_API_KEY:
        return []

    params = {
        "api_token": MARKETAUX_API_KEY,
        "limit": limit,
        "language": "en",
    }
    if query:
        params["search"] = query

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get("https://api.marketaux.com/v1/news/all", params=params)
            resp.raise_for_status()
            data = resp.json()

        articles = []
        for item in data.get("data", []):
            articles.append({
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "published_at": item.get("published_at", ""),
                "category": "marketaux",
                "snippet": item.get("description", ""),
            })
        return articles
    except Exception:
        return []


def fetch_all_news(query: str = None, max_results: int = 20) -> list[dict]:
    google = fetch_google_news(query, max_results=max_results)
    marketaux = fetch_marketaux_news(query, limit=min(10, max_results))
    combined = google + marketaux
    seen_urls = set()
    unique = []
    for article in combined:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique.append(article)
    return unique[:max_results]


def fetch_article_text(url: str) -> str:
    if "news.google.com" in url:
        url = _resolve_google_news_url(url)
        if "news.google.com" in url:
            return "Could not resolve Google News URL to source article."

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()

        if "consent.google" in str(resp.url):
            return f"Blocked by consent page: {url}"

        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
            tag.decompose()

        article = soup.find("article")
        if not article:
            for selector in [
                {"class": re.compile(r"article.*(body|content|text)", re.I)},
                {"class": re.compile(r"(story|post).*(body|content)", re.I)},
                {"id": re.compile(r"article|story|content", re.I)},
            ]:
                article = soup.find("div", selector)
                if article:
                    break

        if article:
            text = article.get_text(separator="\n", strip=True)
        else:
            paragraphs = soup.find_all("p")
            text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)

        if len(cleaned) < 100:
            return f"Article too short or blocked. URL: {url}"

        return cleaned[:5000]
    except Exception as e:
        return f"Error fetching article: {str(e)}"


def fetch_bist_news(max_results: int = 10) -> list[dict]:
    queries = ["Borsa Istanbul", "BIST hisse", "Turkey stock market"]
    all_articles = []
    for q in queries:
        all_articles.extend(fetch_google_news(q, lang="tr", max_results=5))
    seen = set()
    unique = []
    for a in all_articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique[:max_results]


def fetch_gold_news(max_results: int = 10) -> list[dict]:
    return fetch_google_news("gold price market", max_results=max_results)


def fetch_geopolitical_news(max_results: int = 10) -> list[dict]:
    return fetch_google_news("war sanctions geopolitics economy", max_results=max_results)
