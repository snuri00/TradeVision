import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trader.data.bist import get_bist_stocks, get_bist100_index
from trader.data.us_uk import get_stock_quote, get_index_data
from trader.data.gold import get_gold_price, get_gold_history
from trader.data.news import fetch_google_news


def test_bist_stocks():
    data = get_bist_stocks(["THYAO.IS"], period="5d")
    assert "THYAO.IS" in data
    print(f"THYAO: {data['THYAO.IS']}")


def test_bist100():
    data = get_bist100_index()
    assert "value" in data or "error" in data
    print(f"BIST100: {data}")


def test_us_stock():
    data = get_stock_quote("AAPL")
    assert "price" in data or "error" in data
    print(f"AAPL: {data}")


def test_sp500():
    data = get_index_data("SP500")
    assert "price" in data or "error" in data
    print(f"SP500: {data}")


def test_gold():
    data = get_gold_price(period="5d")
    assert "futures" in data
    print(f"Gold: {data}")


def test_gold_history():
    data = get_gold_history(period="1mo")
    assert len(data) > 0
    print(f"Gold history: {len(data)} bars")


def test_google_news():
    articles = fetch_google_news("stock market", max_results=5)
    assert len(articles) > 0
    print(f"News: {len(articles)} articles")
    for a in articles[:3]:
        print(f"  - {a['title']}")


if __name__ == "__main__":
    tests = [test_bist_stocks, test_bist100, test_us_stock, test_sp500,
             test_gold, test_gold_history, test_google_news]
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
        print()
