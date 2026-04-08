import yfinance as yf
import pandas as pd
from trader.config import BIST_SYMBOLS, INDEX_SYMBOLS


def get_bist_stock(symbol: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
    if not symbol.endswith(".IS"):
        symbol = f"{symbol}.IS"
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    df.index = df.index.tz_localize(None) if df.index.tz else df.index
    return df


def get_bist_stocks(symbols: list[str] = None, period: str = "5d") -> dict[str, dict]:
    symbols = symbols or BIST_SYMBOLS
    results = {}
    for symbol in symbols:
        try:
            df = get_bist_stock(symbol, period=period)
            if df.empty:
                continue
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            change_pct = ((last["Close"] - prev["Close"]) / prev["Close"]) * 100
            results[symbol] = {
                "price": round(last["Close"], 2),
                "change_pct": round(change_pct, 2),
                "volume": int(last["Volume"]),
                "high": round(last["High"], 2),
                "low": round(last["Low"], 2),
                "open": round(last["Open"], 2),
            }
        except Exception as e:
            results[symbol] = {"error": str(e)}
    return results


def get_bist100_index() -> dict:
    symbol = INDEX_SYMBOLS["BIST100"]
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="5d")
    if df.empty:
        return {"error": "No data available"}
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    change_pct = ((last["Close"] - prev["Close"]) / prev["Close"]) * 100
    return {
        "symbol": symbol,
        "value": round(last["Close"], 2),
        "change_pct": round(change_pct, 2),
    }


def get_stock_history(symbol: str, period: str = "3mo", interval: str = "1d") -> list[dict]:
    if not symbol.endswith(".IS"):
        symbol = f"{symbol}.IS"
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
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
