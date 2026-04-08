import yfinance as yf
from trader.db import get_db, record_trade, get_capital
from trader.config import MARKETS, detect_market


def get_current_price(symbol: str) -> float:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="1d")
    if df.empty:
        raise ValueError(f"Cannot fetch price for {symbol}")
    return round(df["Close"].iloc[-1], 2)


def execute_trade(symbol: str, side: str, quantity: float,
                   price: float = None, market: str = None) -> dict:
    if market is None:
        market = detect_market(symbol)

    market_config = MARKETS.get(market)
    if not market_config:
        return {"error": f"Unknown market: {market}"}

    if market_config.suffix and not symbol.endswith(market_config.suffix):
        symbol = market_config.normalize_symbol(symbol)

    if market == "us":
        from trader.trading.alpaca_client import _is_configured, place_alpaca_order
        if _is_configured():
            result = place_alpaca_order(symbol, side, quantity)
            if "error" not in result:
                result["via"] = "alpaca"
                return result

    if price is None:
        price = get_current_price(symbol)

    with get_db() as conn:
        capital = get_capital(conn, market)
        if side == "buy":
            total_cost = quantity * price
            if total_cost > capital.get("current_cash", 0):
                return {
                    "error": f"Insufficient cash. Need {total_cost:.2f} {market_config.currency}, "
                             f"have {capital['current_cash']:.2f} {market_config.currency}"
                }

        result = record_trade(conn, symbol, market, side, quantity, price)
        updated_capital = get_capital(conn, market)
        result["remaining_cash"] = updated_capital["current_cash"]
        result["currency"] = market_config.currency
    return result


def execute_bist_trade(symbol: str, side: str, quantity: float, price: float = None) -> dict:
    return execute_trade(symbol, side, quantity, price, market="bist")


def execute_us_trade(symbol: str, side: str, quantity: float, price: float = None) -> dict:
    return execute_trade(symbol, side, quantity, price, market="us")


def execute_uk_trade(symbol: str, side: str, quantity: float, price: float = None) -> dict:
    return execute_trade(symbol, side, quantity, price, market="uk")


def execute_gold_trade(symbol: str, side: str, quantity: float, price: float = None) -> dict:
    if symbol is None:
        symbol = "GC=F"
    return execute_trade(symbol, side, quantity, price, market="gold")
