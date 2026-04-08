from trader.analysis.technical import analyze_stock
from trader.analysis.fundamental import get_fundamentals, score_fundamentals
from trader.db import get_db, get_watchlist


def scan_watchlist_signals(symbols: list[str] = None) -> dict:
    if not symbols:
        with get_db() as conn:
            watchlist = get_watchlist(conn)
            symbols = [w["symbol"] for w in watchlist]

    buy_signals = []
    sell_signals = []
    neutral = []
    errors = []

    for symbol in symbols:
        try:
            analysis = analyze_stock(symbol)
            if "error" in analysis:
                errors.append({"symbol": symbol, "error": analysis["error"]})
                continue

            signals = analysis.get("signals", [])
            buy_count = sum(1 for s in signals if "buy" in s.lower() or "bullish" in s.lower() or "bounce" in s.lower())
            sell_count = sum(1 for s in signals if "sell" in s.lower() or "bearish" in s.lower() or "resistance" in s.lower())

            fundamentals = get_fundamentals(symbol)
            fund_result = score_fundamentals(fundamentals)
            fund_score = fund_result["score"]

            if fund_score >= 1:
                buy_count += 1
            elif fund_score <= -1:
                sell_count += 1

            entry = {
                "symbol": symbol,
                "price": analysis.get("current_price"),
                "rsi": analysis.get("rsi"),
                "macd_trend": analysis.get("macd_trend"),
                "volatility": analysis.get("volatility"),
                "suggested_position_pct": analysis.get("suggested_position_pct"),
                "fundamental_score": fund_score,
                "fundamental_action": fund_result["action"],
                "fundamental_signals": fund_result["signals"],
                "signals": signals,
                "buy_score": buy_count,
                "sell_score": sell_count,
            }

            if buy_count > sell_count:
                buy_signals.append(entry)
            elif sell_count > buy_count:
                sell_signals.append(entry)
            else:
                neutral.append(entry)
        except Exception as e:
            errors.append({"symbol": symbol, "error": str(e)})

    buy_signals.sort(key=lambda x: x["buy_score"], reverse=True)
    sell_signals.sort(key=lambda x: x["sell_score"], reverse=True)

    return {
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "neutral": neutral,
        "errors": errors,
        "total_scanned": len(symbols),
    }
