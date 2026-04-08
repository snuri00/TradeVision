import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trader.backtest.engine import BacktestEngine


def main():
    us_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM"]
    bist_symbols = ["THYAO.IS", "GARAN.IS", "AKBNK.IS", "ASELS.IS", "EREGL.IS", "TUPRS.IS"]
    gold_symbols = ["GC=F"]

    all_symbols = us_symbols + bist_symbols + gold_symbols

    engine = BacktestEngine(
        symbols=all_symbols,
        start_date="2025-03-19",
        end_date="2026-03-18",
        initial_capital=100_000.0,
    )

    results = engine.run(verbose=True)

    print("\n\nJSON Results:")
    import json
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
