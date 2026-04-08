from trader.db import get_db, get_local_positions, get_capital
from trader.trading.alpaca_client import _is_configured, get_alpaca_account, get_alpaca_positions
from trader.config import INITIAL_CAPITAL, MARKETS
import yfinance as yf


def update_position_prices(conn, positions: list[dict]) -> list[dict]:
    for pos in positions:
        try:
            ticker = yf.Ticker(pos["symbol"])
            df = ticker.history(period="1d")
            if not df.empty:
                pos["current_price"] = round(df["Close"].iloc[-1], 2)
                pos["market_value"] = round(pos["quantity"] * pos["current_price"], 2)
                pos["unrealized_pnl"] = round(
                    (pos["current_price"] - pos["avg_cost"]) * pos["quantity"], 2
                )
                pos["unrealized_pnl_pct"] = round(
                    ((pos["current_price"] - pos["avg_cost"]) / pos["avg_cost"]) * 100, 2
                ) if pos["avg_cost"] > 0 else 0

                conn.execute(
                    "UPDATE local_positions SET current_price=?, last_updated=datetime('now') WHERE symbol=?",
                    (pos["current_price"], pos["symbol"]),
                )
        except Exception:
            pos["current_price"] = pos.get("current_price", pos["avg_cost"])
            pos["market_value"] = round(pos["quantity"] * pos["current_price"], 2)
            pos["unrealized_pnl"] = round(
                (pos["current_price"] - pos["avg_cost"]) * pos["quantity"], 2
            )
    return positions


def _build_market_status(conn, market_key: str) -> dict:
    market_config = MARKETS[market_key]
    positions = get_local_positions(conn, market_key)
    positions = update_position_prices(conn, positions)
    capital = get_capital(conn, market_key)

    positions_value = sum(p.get("market_value", 0) for p in positions)
    cash = capital.get("current_cash", market_config.initial_capital)
    initial = market_config.initial_capital
    total = cash + positions_value
    pnl = total - initial

    return {
        "positions": positions,
        "cash": cash,
        "positions_value": positions_value,
        "total_value": total,
        "pnl": pnl,
        "pnl_pct": round((pnl / initial) * 100, 2) if initial > 0 else 0,
        "currency": market_config.currency,
        "initial_capital": initial,
    }


def _build_alpaca_status() -> dict:
    account = get_alpaca_account()
    if "error" in account:
        return {
            "positions": [],
            "account": account,
            "total_value": INITIAL_CAPITAL["us"],
            "pnl": 0,
            "pnl_pct": 0,
            "currency": "USD",
            "initial_capital": INITIAL_CAPITAL["us"],
            "via": "alpaca (error)",
        }

    positions = get_alpaca_positions()
    has_error = any("error" in p for p in positions)

    return {
        "positions": [] if has_error else positions,
        "account": account,
        "cash": account.get("cash", 0),
        "total_value": account.get("portfolio_value", INITIAL_CAPITAL["us"]),
        "pnl": account.get("pnl", 0),
        "pnl_pct": account.get("pnl_pct", 0),
        "currency": "USD",
        "initial_capital": INITIAL_CAPITAL["us"],
        "via": "alpaca",
    }


def get_portfolio_status() -> dict:
    result = {}

    with get_db() as conn:
        for market_key in MARKETS:
            if market_key == "us":
                continue
            result[market_key] = _build_market_status(conn, market_key)

    if _is_configured():
        result["us"] = _build_alpaca_status()
    else:
        with get_db() as conn:
            result["us"] = _build_market_status(conn, "us")

    return result
