from datetime import datetime, timedelta
from trader.db import get_db, get_trade_history, save_performance_snapshot
from trader.trading.portfolio import get_portfolio_status
from trader.config import MARKETS


def calculate_trade_stats(trades: list[dict]) -> dict:
    if not trades:
        return {"total_trades": 0}

    buy_trades = [t for t in trades if t["side"] == "buy"]
    sell_trades = [t for t in trades if t["side"] == "sell"]

    symbols_traded = set(t["symbol"] for t in trades)
    realized_pnl = {}

    for symbol in symbols_traded:
        sym_buys = [t for t in buy_trades if t["symbol"] == symbol]
        sym_sells = [t for t in sell_trades if t["symbol"] == symbol]

        if sym_buys and sym_sells:
            avg_buy = sum(t["price"] * t["quantity"] for t in sym_buys) / sum(t["quantity"] for t in sym_buys)
            for sell in sym_sells:
                pnl = (sell["price"] - avg_buy) * sell["quantity"]
                realized_pnl[symbol] = realized_pnl.get(symbol, 0) + pnl

    profitable = sum(1 for v in realized_pnl.values() if v > 0)
    losing = sum(1 for v in realized_pnl.values() if v < 0)
    total_realized = sum(realized_pnl.values())

    win_rate = (profitable / (profitable + losing) * 100) if (profitable + losing) > 0 else 0

    return {
        "total_trades": len(trades),
        "buy_trades": len(buy_trades),
        "sell_trades": len(sell_trades),
        "symbols_traded": list(symbols_traded),
        "realized_pnl": round(total_realized, 2),
        "realized_by_symbol": {k: round(v, 2) for k, v in realized_pnl.items()},
        "profitable_trades": profitable,
        "losing_trades": losing,
        "win_rate": round(win_rate, 2),
    }


def get_performance_report(period: str = "daily") -> dict:
    now = datetime.now()
    if period == "daily":
        start_date = now.strftime("%Y-%m-%d")
    elif period == "weekly":
        start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "monthly":
        start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        start_date = (now - timedelta(days=365)).strftime("%Y-%m-%d")

    with get_db() as conn:
        all_trades = conn.execute(
            "SELECT * FROM paper_trades WHERE executed_at >= ? ORDER BY executed_at DESC",
            (start_date,),
        ).fetchall()
        trades = [dict(t) for t in all_trades]

    portfolio = get_portfolio_status()
    report = {
        "period": period,
        "start_date": start_date,
        "end_date": now.strftime("%Y-%m-%d"),
    }

    for market_key in MARKETS:
        if market_key not in portfolio:
            continue
        market_trades = [t for t in trades if t["market"] == market_key]
        report[market_key] = {
            "trade_stats": calculate_trade_stats(market_trades),
            "portfolio_value": portfolio[market_key]["total_value"],
            "pnl": portfolio[market_key]["pnl"],
            "pnl_pct": portfolio[market_key]["pnl_pct"],
        }

    return report


def save_daily_snapshot():
    portfolio = get_portfolio_status()
    today = datetime.now().strftime("%Y-%m-%d")

    with get_db() as conn:
        for market_key in MARKETS:
            if market_key not in portfolio:
                continue
            market_data = portfolio[market_key]
            trades = get_trade_history(conn, market=market_key, limit=1000)
            stats = calculate_trade_stats(trades)
            save_performance_snapshot(
                conn,
                snapshot_date=today,
                period_type="daily",
                market=market_key,
                total_value=market_data["total_value"],
                total_pnl=market_data["pnl"],
                pnl_pct=market_data["pnl_pct"],
                win_rate=stats.get("win_rate"),
            )
