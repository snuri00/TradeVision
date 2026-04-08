import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trader.db import init_db, get_db, get_watchlist, save_market_data
from trader.data.bist import get_stock_history as bist_history
from trader.data.us_uk import get_stock_history as us_uk_history
from trader.data.gold import get_gold_history


def collect_market_data():
    init_db()
    with get_db() as conn:
        watchlist = get_watchlist(conn)

        for item in watchlist:
            symbol = item["symbol"]
            market = item["market"]
            try:
                if market == "bist":
                    rows = bist_history(symbol, period="5d")
                elif market == "gold":
                    rows = get_gold_history(symbol, period="5d")
                else:
                    rows = us_uk_history(symbol, period="5d")

                save_market_data(conn, symbol, rows)
                print(f"Collected {len(rows)} bars for {symbol}")
            except Exception as e:
                print(f"Error collecting {symbol}: {e}")


def main():
    collect_market_data()


if __name__ == "__main__":
    main()
