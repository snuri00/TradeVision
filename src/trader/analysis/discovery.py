import yfinance as yf
import pandas as pd
from trader.config import MARKETS


def scan_volume_anomalies(market: str = None, min_ratio: float = 2.0,
                           top_n: int = 10) -> list[dict]:
    symbols = _get_symbols(market)
    results = []

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1mo")
            if df.empty or len(df) < 10:
                continue

            avg_vol = df["Volume"].iloc[:-1].rolling(20).mean().iloc[-1]
            if avg_vol <= 0 or pd.isna(avg_vol):
                continue

            current_vol = df["Volume"].iloc[-1]
            ratio = current_vol / avg_vol
            if ratio >= min_ratio:
                change_pct = ((df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100
                results.append({
                    "symbol": symbol,
                    "volume_ratio": round(ratio, 2),
                    "price": round(df["Close"].iloc[-1], 2),
                    "change_pct": round(change_pct, 2),
                    "avg_volume": int(avg_vol),
                    "current_volume": int(current_vol),
                    "direction": "up" if change_pct > 0 else "down",
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["volume_ratio"], reverse=True)
    return results[:top_n]


def scan_gap_moves(market: str = None, min_gap_pct: float = 2.0,
                    top_n: int = 10) -> list[dict]:
    symbols = _get_symbols(market)
    results = []

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="5d")
            if df.empty or len(df) < 2:
                continue

            prev_close = df["Close"].iloc[-2]
            today_open = df["Open"].iloc[-1]
            gap_pct = ((today_open - prev_close) / prev_close) * 100

            if abs(gap_pct) >= min_gap_pct:
                current_price = df["Close"].iloc[-1]
                filled = (
                    (gap_pct > 0 and current_price <= prev_close) or
                    (gap_pct < 0 and current_price >= prev_close)
                )
                results.append({
                    "symbol": symbol,
                    "gap_pct": round(gap_pct, 2),
                    "type": "gap_up" if gap_pct > 0 else "gap_down",
                    "prev_close": round(prev_close, 2),
                    "open": round(today_open, 2),
                    "current": round(current_price, 2),
                    "gap_filled": filled,
                })
        except Exception:
            continue

    results.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)
    return results[:top_n]


def scan_top_movers(market: str = None, top_n: int = 10) -> dict:
    symbols = _get_symbols(market)
    movers = []

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="5d")
            if df.empty or len(df) < 2:
                continue

            change_pct = ((df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100
            movers.append({
                "symbol": symbol,
                "price": round(df["Close"].iloc[-1], 2),
                "change_pct": round(change_pct, 2),
                "volume": int(df["Volume"].iloc[-1]),
            })
        except Exception:
            continue

    movers.sort(key=lambda x: x["change_pct"], reverse=True)
    return {
        "gainers": movers[:top_n],
        "losers": movers[-top_n:][::-1] if len(movers) >= top_n else list(reversed(movers)),
    }


def scan_near_support_resistance(market: str = None, top_n: int = 10) -> list[dict]:
    symbols = _get_symbols(market)
    results = []

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="3mo")
            if df.empty or len(df) < 20:
                continue

            price = df["Close"].iloc[-1]
            high_52w = df["High"].max()
            low_52w = df["Low"].min()
            sma_50 = df["Close"].rolling(50).mean().iloc[-1] if len(df) >= 50 else None

            near_high = ((high_52w - price) / price) * 100
            near_low = ((price - low_52w) / price) * 100

            entry = {
                "symbol": symbol,
                "price": round(price, 2),
                "high_3m": round(high_52w, 2),
                "low_3m": round(low_52w, 2),
                "pct_from_high": round(near_high, 2),
                "pct_from_low": round(near_low, 2),
            }

            if sma_50 and not pd.isna(sma_50):
                entry["sma_50"] = round(sma_50, 2)
                entry["pct_from_sma50"] = round(((price - sma_50) / sma_50) * 100, 2)

            if near_high < 3:
                entry["level"] = "near_resistance"
                results.append(entry)
            elif near_low < 3:
                entry["level"] = "near_support"
                results.append(entry)
        except Exception:
            continue

    results.sort(key=lambda x: min(x["pct_from_high"], x["pct_from_low"]))
    return results[:top_n]


def _get_symbols(market: str = None) -> list[str]:
    if market and market in MARKETS:
        return MARKETS[market].symbols
    symbols = []
    for m in MARKETS.values():
        symbols.extend(m.symbols)
    return symbols
