import yfinance as yf
import pandas as pd
from trader.config import FINNHUB_API_KEY, US_SYMBOLS, UK_SYMBOLS, INDEX_SYMBOLS


def get_stock_data(symbol: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if not df.empty:
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
    return df


def get_stock_quote(symbol: str) -> dict:
    df = get_stock_data(symbol, period="5d")
    if df.empty:
        return {"error": f"No data for {symbol}"}
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    change_pct = ((last["Close"] - prev["Close"]) / prev["Close"]) * 100
    return {
        "symbol": symbol,
        "price": round(last["Close"], 2),
        "change_pct": round(change_pct, 2),
        "volume": int(last["Volume"]),
        "high": round(last["High"], 2),
        "low": round(last["Low"], 2),
        "open": round(last["Open"], 2),
    }


def get_finnhub_quote(symbol: str) -> dict:
    if not FINNHUB_API_KEY:
        return get_stock_quote(symbol)
    try:
        import finnhub
        client = finnhub.Client(api_key=FINNHUB_API_KEY)
        quote = client.quote(symbol)
        return {
            "symbol": symbol,
            "price": quote.get("c", 0),
            "change": quote.get("d", 0),
            "change_pct": quote.get("dp", 0),
            "high": quote.get("h", 0),
            "low": quote.get("l", 0),
            "open": quote.get("o", 0),
            "prev_close": quote.get("pc", 0),
        }
    except Exception:
        return get_stock_quote(symbol)


def get_us_stocks(symbols: list[str] = None) -> dict[str, dict]:
    symbols = symbols or US_SYMBOLS
    results = {}
    for symbol in symbols:
        try:
            results[symbol] = get_stock_quote(symbol)
        except Exception as e:
            results[symbol] = {"error": str(e)}
    return results


def get_uk_stocks(symbols: list[str] = None) -> dict[str, dict]:
    symbols = symbols or UK_SYMBOLS
    results = {}
    for symbol in symbols:
        try:
            results[symbol] = get_stock_quote(symbol)
        except Exception as e:
            results[symbol] = {"error": str(e)}
    return results


def get_index_data(index_key: str) -> dict:
    symbol = INDEX_SYMBOLS.get(index_key, index_key)
    return get_stock_quote(symbol)


def get_stock_history(symbol: str, period: str = "3mo", interval: str = "1d") -> list[dict]:
    df = get_stock_data(symbol, period=period, interval=interval)
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
