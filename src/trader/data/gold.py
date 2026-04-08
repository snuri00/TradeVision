import yfinance as yf
import pandas as pd
from trader.config import GOLD_SYMBOLS


def get_gold_price(period: str = "1mo", interval: str = "1d") -> dict:
    results = {}
    for name, symbol in GOLD_SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                results[name] = {"error": "No data"}
                continue
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            change_pct = ((last["Close"] - prev["Close"]) / prev["Close"]) * 100
            results[name] = {
                "symbol": symbol,
                "price": round(last["Close"], 2),
                "change_pct": round(change_pct, 2),
                "high": round(last["High"], 2),
                "low": round(last["Low"], 2),
            }
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def get_gold_history(symbol: str = None, period: str = "3mo", interval: str = "1d") -> list[dict]:
    symbol = symbol or GOLD_SYMBOLS["futures"]
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        return []
    df.index = df.index.tz_localize(None) if df.index.tz else df.index
    rows = []
    for date, row in df.iterrows():
        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]),
        })
    return rows


def get_gold_dataframe(symbol: str = None, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    symbol = symbol or GOLD_SYMBOLS["futures"]
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if not df.empty:
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
    return df
