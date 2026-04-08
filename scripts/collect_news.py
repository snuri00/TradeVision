import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trader.db import init_db, get_db, save_news_article
from trader.data.news import fetch_all_news, fetch_bist_news, fetch_gold_news, fetch_geopolitical_news


def collect_news():
    init_db()
    all_articles = []

    all_articles.extend(fetch_all_news(max_results=10))
    all_articles.extend(fetch_bist_news(max_results=5))
    all_articles.extend(fetch_gold_news(max_results=5))
    all_articles.extend(fetch_geopolitical_news(max_results=5))

    with get_db() as conn:
        saved = 0
        for a in all_articles:
            try:
                save_news_article(
                    conn, a["title"], a.get("source", ""), a["url"],
                    a.get("published_at", ""), a.get("category"),
                )
                saved += 1
            except Exception:
                pass
        print(f"Saved {saved} news articles")


def main():
    collect_news()


if __name__ == "__main__":
    main()
