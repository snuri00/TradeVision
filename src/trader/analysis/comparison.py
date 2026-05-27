"""Multi-stock side-by-side comparison analysis."""
import yfinance as yf
import pandas as pd
import numpy as np
from trader.analysis.technical import analyze_stock
from trader.analysis.fundamental import get_fundamentals


def compare_stocks(symbols: list[str], period: str = "3mo") -> dict:
    """
    Compare multiple stocks side by side across key metrics:
    return %, volatility, P/E, RSI, volume and momentum.
    """
    results = []

    for symbol in symbols:
        entry = {"symbol": symbol}
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)

            if df.empty or len(df) < 5:
                entry["error"] = "No data"
                results.append(entry)
                continue

            # Price performance
            first_close = df["Close"].iloc[0]
            last_close = df["Close"].iloc[-1]
            entry["current_price"] = round(last_close, 4)
            entry["return_pct"] = round(((last_close - first_close) / first_close) * 100, 2)

            # Volatility (annualized)
            daily_returns = df["Close"].pct_change().dropna()
            entry["volatility_annual_pct"] = round(daily_returns.std() * np.sqrt(252) * 100, 2)

            # Volume
            entry["avg_volume"] = int(df["Volume"].mean())
            entry["last_volume"] = int(df["Volume"].iloc[-1])

            # 5d / 1mo momentum
            if len(df) >= 6:
                entry["momentum_5d_pct"] = round(
                    ((df["Close"].iloc[-1] - df["Close"].iloc[-6]) / df["Close"].iloc[-6]) * 100, 2
                )
            if len(df) >= 22:
                entry["momentum_1mo_pct"] = round(
                    ((df["Close"].iloc[-1] - df["Close"].iloc[-22]) / df["Close"].iloc[-22]) * 100, 2
                )

            # Technical indicators (RSI, MACD)
            try:
                tech = analyze_stock(symbol, period=period)
                indicators = tech.get("indicators", {})
                entry["rsi"] = indicators.get("rsi")
                entry["above_sma20"] = indicators.get("above_sma20")
                entry["above_sma50"] = indicators.get("above_sma50")
                entry["macd_signal"] = indicators.get("macd_signal")
                entry["tech_signals"] = tech.get("signals", [])
            except Exception:
                pass

            # Fundamentals
            try:
                info = ticker.info
                entry["pe_ratio"] = info.get("trailingPE")
                entry["pb_ratio"] = info.get("priceToBook")
                entry["market_cap"] = info.get("marketCap")
                entry["dividend_yield"] = info.get("dividendYield")
                entry["roe"] = info.get("returnOnEquity")
                entry["sector"] = info.get("sector")
                entry["industry"] = info.get("industry")
            except Exception:
                pass

        except Exception as e:
            entry["error"] = str(e)

        results.append(entry)

    # Ranking: by return_pct
    ranked = sorted(
        [r for r in results if "return_pct" in r],
        key=lambda x: x["return_pct"],
        reverse=True,
    )
    # Add rank
    for i, r in enumerate(ranked, 1):
        r["rank_by_return"] = i

    # Build summary
    summary = {}
    if ranked:
        best = ranked[0]
        worst = ranked[-1]
        summary["best_performer"] = {"symbol": best["symbol"], "return_pct": best["return_pct"]}
        summary["worst_performer"] = {"symbol": worst["symbol"], "return_pct": worst["return_pct"]}

        returns = [r["return_pct"] for r in ranked]
        summary["avg_return_pct"] = round(sum(returns) / len(returns), 2)

        lowest_vol = min(ranked, key=lambda x: x.get("volatility_annual_pct", 999))
        summary["lowest_volatility"] = {"symbol": lowest_vol["symbol"],
                                         "volatility_pct": lowest_vol.get("volatility_annual_pct")}

    return {
        "period": period,
        "symbols": symbols,
        "comparison": results,
        "summary": summary,
    }
