import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trader.db import init_db, get_db, get_local_positions, get_capital, get_trade_history
from trader.trading.executor import execute_bist_trade, execute_gold_trade


def test_bist_paper_trade():
    init_db()
    result = execute_bist_trade("THYAO.IS", "buy", 100)
    print(f"BIST Buy: {result}")
    assert "error" not in result or result.get("symbol")

    with get_db() as conn:
        positions = get_local_positions(conn, "bist")
        print(f"BIST Positions: {positions}")

        capital = get_capital(conn, "bist")
        print(f"BIST Capital: {capital}")


def test_gold_paper_trade():
    init_db()
    result = execute_gold_trade("GC=F", "buy", 1)
    print(f"Gold Buy: {result}")
    assert "error" not in result or result.get("symbol")

    with get_db() as conn:
        positions = get_local_positions(conn, "gold")
        print(f"Gold Positions: {positions}")


def test_trade_history():
    init_db()
    with get_db() as conn:
        trades = get_trade_history(conn, limit=10)
        print(f"Trade History ({len(trades)} trades):")
        for t in trades:
            print(f"  {t['executed_at']} {t['side']} {t['quantity']} {t['symbol']} @ {t['price']}")


if __name__ == "__main__":
    tests = [test_bist_paper_trade, test_gold_paper_trade, test_trade_history]
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
        print()
