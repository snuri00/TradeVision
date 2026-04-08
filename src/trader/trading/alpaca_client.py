from trader.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, INITIAL_CAPITAL


def _is_configured() -> bool:
    return bool(ALPACA_API_KEY and ALPACA_SECRET_KEY
                and ALPACA_API_KEY != "your_key_here")


def get_alpaca_client():
    if not _is_configured():
        return None
    from alpaca.trading.client import TradingClient
    return TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)


def get_alpaca_account() -> dict:
    client = get_alpaca_client()
    if not client:
        return {"error": "Alpaca not configured"}
    try:
        account = client.get_account()
        equity = float(account.equity)
        return {
            "buying_power": float(account.buying_power),
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "equity": equity,
            "pnl": equity - INITIAL_CAPITAL["us"],
            "pnl_pct": ((equity - INITIAL_CAPITAL["us"]) / INITIAL_CAPITAL["us"]) * 100,
        }
    except Exception as e:
        return {"error": str(e)}


def get_alpaca_positions() -> list[dict]:
    client = get_alpaca_client()
    if not client:
        return []
    try:
        positions = client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "quantity": float(p.qty),
                "avg_cost": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pnl": float(p.unrealized_pl),
                "unrealized_pnl_pct": float(p.unrealized_plpc) * 100,
                "market": "us",
            }
            for p in positions
        ]
    except Exception as e:
        return [{"error": str(e)}]


def place_alpaca_order(symbol: str, side: str, quantity: float) -> dict:
    client = get_alpaca_client()
    if not client:
        return {"error": "Alpaca not configured"}
    try:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        request = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
        )
        order = client.submit_order(request)
        return {
            "order_id": str(order.id),
            "symbol": order.symbol,
            "side": str(order.side),
            "quantity": float(order.qty),
            "status": str(order.status),
            "type": str(order.type),
        }
    except Exception as e:
        return {"error": str(e)}
