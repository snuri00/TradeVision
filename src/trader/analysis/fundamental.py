import yfinance as yf


def get_fundamentals(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

    if not info or info.get("trailingPE") is None and info.get("marketCap") is None:
        return {"symbol": symbol, "error": "No fundamental data available"}

    fields = {
        "pe_ratio": "trailingPE",
        "forward_pe": "forwardPE",
        "pb_ratio": "priceToBook",
        "ps_ratio": "priceToSalesTrailing12Months",
        "roe": "returnOnEquity",
        "roa": "returnOnAssets",
        "debt_to_equity": "debtToEquity",
        "current_ratio": "currentRatio",
        "dividend_yield": "dividendYield",
        "market_cap": "marketCap",
        "profit_margins": "profitMargins",
        "revenue_growth": "revenueGrowth",
        "earnings_growth": "earningsGrowth",
        "sector": "sector",
        "industry": "industry",
    }

    result = {"symbol": symbol}
    for key, yf_key in fields.items():
        result[key] = info.get(yf_key)

    return result


def score_fundamentals(fundamentals: dict) -> dict:
    if "error" in fundamentals:
        return {"score": 0, "signals": ["No data"], "action": "neutral"}

    score = 0
    signals = []

    pe = fundamentals.get("pe_ratio")
    if pe is not None:
        if pe < 0:
            score -= 1
            signals.append(f"P/E {pe:.1f} negative earnings")
        elif pe < 15:
            score += 1
            signals.append(f"P/E {pe:.1f} undervalued")
        elif pe > 40:
            score -= 2
            signals.append(f"P/E {pe:.1f} very expensive")
        elif pe > 25:
            score -= 1
            signals.append(f"P/E {pe:.1f} expensive")

    pb = fundamentals.get("pb_ratio")
    if pb is not None:
        if pb < 1.5:
            score += 1
            signals.append(f"P/B {pb:.2f} attractive")
        elif pb > 5:
            score -= 1
            signals.append(f"P/B {pb:.2f} overvalued")

    roe = fundamentals.get("roe")
    if roe is not None:
        if roe > 0.20:
            score += 2
            signals.append(f"ROE {roe:.1%} excellent")
        elif roe > 0.15:
            score += 1
            signals.append(f"ROE {roe:.1%} strong")
        elif roe < 0.05:
            score -= 1
            signals.append(f"ROE {roe:.1%} weak")

    dte = fundamentals.get("debt_to_equity")
    if dte is not None:
        if dte > 200:
            score -= 2
            signals.append(f"D/E {dte:.0f} very high leverage")
        elif dte > 100:
            score -= 1
            signals.append(f"D/E {dte:.0f} high leverage")
        elif dte < 30:
            score += 1
            signals.append(f"D/E {dte:.0f} low leverage")

    margins = fundamentals.get("profit_margins")
    if margins is not None:
        if margins > 0.20:
            score += 1
            signals.append(f"Margins {margins:.1%} strong")
        elif margins < 0:
            score -= 1
            signals.append(f"Margins {margins:.1%} negative")

    rev_growth = fundamentals.get("revenue_growth")
    if rev_growth is not None:
        if rev_growth > 0.15:
            score += 1
            signals.append(f"Revenue growth {rev_growth:.1%} strong")
        elif rev_growth < -0.05:
            score -= 1
            signals.append(f"Revenue growth {rev_growth:.1%} declining")

    earn_growth = fundamentals.get("earnings_growth")
    if earn_growth is not None:
        if earn_growth > 0.20:
            score += 1
            signals.append(f"Earnings growth {earn_growth:.1%} strong")
        elif earn_growth < -0.10:
            score -= 1
            signals.append(f"Earnings growth {earn_growth:.1%} declining")

    if not signals:
        signals.append("Insufficient fundamental data")

    if score >= 3:
        action = "fundamentally_strong"
    elif score >= 1:
        action = "fundamentally_positive"
    elif score <= -3:
        action = "fundamentally_weak"
    elif score <= -1:
        action = "fundamentally_negative"
    else:
        action = "neutral"

    return {
        "score": score,
        "signals": signals,
        "action": action,
    }
