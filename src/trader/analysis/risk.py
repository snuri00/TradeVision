"""Portfolio risk metrics: VaR, Sharpe, Sortino, drawdown, beta."""
import numpy as np
import pandas as pd
import yfinance as yf
from trader.db import get_db, get_local_positions


RISK_FREE_RATE_ANNUAL = 0.05  # ~5% risk-free (can be adjusted)
TRADING_DAYS = 252


def get_portfolio_risk_metrics(lookback_period: str = "1y") -> dict:
    """
    Calculate comprehensive risk metrics for the current portfolio:
    - Value at Risk (VaR) at 95% and 99%
    - Sharpe Ratio
    - Sortino Ratio
    - Maximum Drawdown
    - Beta vs S&P 500
    - Portfolio volatility
    """
    with get_db() as conn:
        positions = get_local_positions(conn)

    if not positions:
        return {"error": "No open positions in portfolio", "metrics": {}}

    symbols = [p["symbol"] for p in positions]
    quantities = {p["symbol"]: p["quantity"] for p in positions}
    avg_costs = {p["symbol"]: p.get("avg_cost", 0) for p in positions}

    # Fetch historical data
    price_data = {}
    current_prices = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period=lookback_period)
            if not df.empty:
                price_data[sym] = df["Close"]
                current_prices[sym] = df["Close"].iloc[-1]
        except Exception:
            pass

    if not price_data:
        return {"error": "Could not fetch price data for positions"}

    # Build portfolio value series
    common_index = None
    for sym, prices in price_data.items():
        if common_index is None:
            common_index = prices.index
        else:
            common_index = common_index.intersection(prices.index)

    if common_index is None or len(common_index) < 20:
        return {"error": "Insufficient historical data (need at least 20 days)"}

    # Portfolio daily values
    portfolio_values = pd.Series(0.0, index=common_index)
    total_cost = 0.0
    total_market_value = 0.0
    position_details = []

    for sym in symbols:
        if sym not in price_data:
            continue
        qty = quantities.get(sym, 0)
        avg_cost = avg_costs.get(sym, 0)
        prices = price_data[sym].reindex(common_index).ffill()
        portfolio_values += prices * qty

        current_px = current_prices.get(sym, 0)
        market_val = current_px * qty
        cost_basis = avg_cost * qty
        unrealized_pnl = market_val - cost_basis
        pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0

        total_cost += cost_basis
        total_market_value += market_val

        position_details.append({
            "symbol": sym,
            "quantity": qty,
            "avg_cost": round(avg_cost, 4),
            "current_price": round(current_px, 4),
            "market_value": round(market_val, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "weight_pct": 0,  # will fill below
        })

    # Portfolio weights
    for pos in position_details:
        pos["weight_pct"] = round((pos["market_value"] / total_market_value * 100)
                                   if total_market_value > 0 else 0, 2)

    # Daily returns
    portfolio_returns = portfolio_values.pct_change().dropna()

    # --- VaR ---
    var_95 = float(np.percentile(portfolio_returns, 5))
    var_99 = float(np.percentile(portfolio_returns, 1))
    var_95_dollar = var_95 * total_market_value
    var_99_dollar = var_99 * total_market_value

    # --- Sharpe Ratio ---
    rf_daily = RISK_FREE_RATE_ANNUAL / TRADING_DAYS
    excess_returns = portfolio_returns - rf_daily
    sharpe = float(excess_returns.mean() / excess_returns.std() * np.sqrt(TRADING_DAYS)) if excess_returns.std() > 0 else 0

    # --- Sortino Ratio (downside deviation) ---
    downside_returns = portfolio_returns[portfolio_returns < 0]
    downside_std = float(downside_returns.std()) if len(downside_returns) > 0 else 0
    sortino = float(excess_returns.mean() / downside_std * np.sqrt(TRADING_DAYS)) if downside_std > 0 else 0

    # --- Max Drawdown ---
    cum_returns = (1 + portfolio_returns).cumprod()
    rolling_max = cum_returns.cummax()
    drawdown = (cum_returns - rolling_max) / rolling_max
    max_drawdown = float(drawdown.min()) * 100

    # --- Portfolio Volatility (annualized) ---
    annual_vol = float(portfolio_returns.std() * np.sqrt(TRADING_DAYS)) * 100

    # --- Beta vs S&P 500 ---
    beta = None
    try:
        sp500 = yf.Ticker("^GSPC")
        sp_df = sp500.history(period=lookback_period)
        if not sp_df.empty:
            sp_returns = sp_df["Close"].reindex(common_index).ffill().pct_change().dropna()
            aligned_port = portfolio_returns.reindex(sp_returns.index).dropna()
            aligned_sp = sp_returns.reindex(aligned_port.index).dropna()
            if len(aligned_port) > 10:
                cov = np.cov(aligned_port, aligned_sp)[0][1]
                sp_var = np.var(aligned_sp)
                beta = round(float(cov / sp_var), 3) if sp_var > 0 else None
    except Exception:
        pass

    # --- Calmar Ratio ---
    annual_return = float(portfolio_returns.mean() * TRADING_DAYS) * 100
    calmar = round(annual_return / abs(max_drawdown), 3) if max_drawdown != 0 else None

    # --- Summary label ---
    def sharpe_label(s):
        if s > 2: return "Excellent"
        if s > 1: return "Good"
        if s > 0: return "Acceptable"
        return "Poor"

    return {
        "lookback_period": lookback_period,
        "portfolio_summary": {
            "total_cost_basis": round(total_cost, 2),
            "total_market_value": round(total_market_value, 2),
            "total_unrealized_pnl": round(total_market_value - total_cost, 2),
            "total_pnl_pct": round((total_market_value - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0,
            "num_positions": len(position_details),
        },
        "risk_metrics": {
            "annual_volatility_pct": round(annual_vol, 2),
            "annual_return_pct": round(annual_return, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sharpe_label": sharpe_label(sharpe),
            "sortino_ratio": round(sortino, 3),
            "calmar_ratio": calmar,
            "beta_vs_sp500": beta,
            "max_drawdown_pct": round(max_drawdown, 2),
            "var_95_pct": round(var_95 * 100, 3),
            "var_99_pct": round(var_99 * 100, 3),
            "var_95_dollar": round(var_95_dollar, 2),
            "var_99_dollar": round(var_99_dollar, 2),
            "risk_free_rate_used": RISK_FREE_RATE_ANNUAL,
        },
        "positions": position_details,
        "interpretation": {
            "var_95": f"With 95% confidence, max daily loss is ${abs(var_95_dollar):,.2f} ({abs(var_95)*100:.2f}%)",
            "var_99": f"With 99% confidence, max daily loss is ${abs(var_99_dollar):,.2f} ({abs(var_99)*100:.2f}%)",
            "max_drawdown": f"Portfolio fell {abs(max_drawdown):.2f}% from its peak during this period",
            "sharpe": f"Sharpe: {sharpe:.2f} - {sharpe_label(sharpe)} risk-adjusted return",
        },
    }
