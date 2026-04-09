import yfinance as yf
import pandas as pd


def get_fear_greed_proxy() -> dict:
    vix = _get_latest("^VIX")
    sp500 = _get_latest("^GSPC")
    gold = _get_latest("GC=F")
    bonds = _get_latest("^TNX")

    score = 50
    signals = []

    if vix:
        vix_close = vix["close"]
        if vix_close > 35:
            score -= 30
            signals.append(f"VIX {vix_close:.1f} - extreme fear")
        elif vix_close > 25:
            score -= 15
            signals.append(f"VIX {vix_close:.1f} - fear")
        elif vix_close < 14:
            score += 20
            signals.append(f"VIX {vix_close:.1f} - extreme greed")
        elif vix_close < 18:
            score += 10
            signals.append(f"VIX {vix_close:.1f} - greed")

        vix_change = vix.get("change_pct", 0)
        if vix_change > 15:
            score -= 15
            signals.append(f"VIX spike +{vix_change:.1f}%")
        elif vix_change < -15:
            score += 10
            signals.append(f"VIX crash {vix_change:.1f}%")

    if sp500:
        sp_change = sp500.get("change_pct", 0)
        if sp_change > 2:
            score += 10
            signals.append(f"S&P 500 rally +{sp_change:.1f}%")
        elif sp_change < -2:
            score -= 10
            signals.append(f"S&P 500 drop {sp_change:.1f}%")

        sp_5d = sp500.get("change_5d_pct")
        if sp_5d is not None:
            if sp_5d > 5:
                score += 10
                signals.append(f"S&P 500 5d +{sp_5d:.1f}% momentum")
            elif sp_5d < -5:
                score -= 10
                signals.append(f"S&P 500 5d {sp_5d:.1f}% weakness")

    if gold:
        gold_change = gold.get("change_pct", 0)
        if gold_change > 3:
            score -= 10
            signals.append(f"Gold surge +{gold_change:.1f}% - flight to safety")
        elif gold_change < -2:
            score += 5
            signals.append(f"Gold drop {gold_change:.1f}% - risk on")

    score = max(0, min(100, score))

    if score >= 80:
        label = "Extreme Greed"
    elif score >= 60:
        label = "Greed"
    elif score >= 40:
        label = "Neutral"
    elif score >= 20:
        label = "Fear"
    else:
        label = "Extreme Fear"

    return {
        "score": score,
        "label": label,
        "signals": signals,
        "components": {
            "vix": vix,
            "sp500": sp500,
            "gold": gold,
            "bonds": bonds,
        },
    }


def get_insider_activity(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        insiders = ticker.insider_transactions
        if insiders is None or insiders.empty:
            return {"symbol": symbol, "transactions": [], "summary": "No insider data"}

        recent = insiders.head(10)
        transactions = []
        buys = 0
        sells = 0

        for _, row in recent.iterrows():
            tx_type = str(row.get("Transaction", "")).lower()
            shares = row.get("Shares", 0)
            insider = str(row.get("Insider Trading", row.get("Insider", "")))
            date = str(row.get("Start Date", row.get("Date", "")))

            is_buy = "purchase" in tx_type or "buy" in tx_type or "acquisition" in tx_type
            is_sell = "sale" in tx_type or "sell" in tx_type or "disposition" in tx_type

            if is_buy:
                buys += 1
            elif is_sell:
                sells += 1

            transactions.append({
                "insider": insider,
                "type": tx_type,
                "shares": int(shares) if pd.notna(shares) else 0,
                "date": date,
            })

        if buys > sells * 2:
            sentiment = "bullish"
        elif sells > buys * 2:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        return {
            "symbol": symbol,
            "transactions": transactions,
            "buy_count": buys,
            "sell_count": sells,
            "sentiment": sentiment,
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def get_analyst_sentiment(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        target_price = info.get("targetMeanPrice")
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        recommendation = info.get("recommendationKey", "none")
        num_analysts = info.get("numberOfAnalystOpinions", 0)
        target_high = info.get("targetHighPrice")
        target_low = info.get("targetLowPrice")

        upside = None
        if target_price and current_price and current_price > 0:
            upside = round(((target_price - current_price) / current_price) * 100, 2)

        return {
            "symbol": symbol,
            "recommendation": recommendation,
            "num_analysts": num_analysts,
            "current_price": current_price,
            "target_mean": target_price,
            "target_high": target_high,
            "target_low": target_low,
            "upside_pct": upside,
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def _get_latest(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1mo")
        if df.empty or len(df) < 2:
            return None
        last = df.iloc[-1]
        prev = df.iloc[-2]
        change_pct = ((last["Close"] - prev["Close"]) / prev["Close"]) * 100

        result = {
            "close": round(last["Close"], 2),
            "change_pct": round(change_pct, 2),
        }

        if len(df) >= 6:
            close_5d_ago = df["Close"].iloc[-6]
            result["change_5d_pct"] = round(((last["Close"] - close_5d_ago) / close_5d_ago) * 100, 2)

        return result
    except Exception:
        return None
