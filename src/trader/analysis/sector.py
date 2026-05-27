"""Sector performance analysis using ETFs and index data."""
import yfinance as yf
import pandas as pd
import numpy as np


# US S&P 500 Sector ETFs (SPDR)
US_SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

# Global indices for broad sector overview
GLOBAL_INDICES = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "Dow Jones": "^DJI",
    "BIST 100": "XU100.IS",
    "FTSE 100": "^FTSE",
    "DAX": "^GDAXI",
    "CAC 40": "^FCHI",
    "Nikkei 225": "^N225",
    "Hang Seng": "^HSI",
    "Nifty 50": "^NSEI",
    "ASX 200": "^AXJO",
    "VIX": "^VIX",
}


def get_sector_performance(period: str = "1mo") -> dict:
    """
    Fetch US sector ETF performance and global index performance.
    Returns ranked sectors by return, momentum, and relative strength.
    """
    sector_data = []

    for sector_name, etf_symbol in US_SECTOR_ETFS.items():
        try:
            ticker = yf.Ticker(etf_symbol)
            df = ticker.history(period=period)

            if df.empty or len(df) < 3:
                continue

            first = df["Close"].iloc[0]
            last = df["Close"].iloc[-1]
            ret = ((last - first) / first) * 100

            # 5-day return (momentum)
            ret_5d = None
            if len(df) >= 6:
                ret_5d = ((df["Close"].iloc[-1] - df["Close"].iloc[-6]) / df["Close"].iloc[-6]) * 100

            # RSI
            delta = df["Close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty and len(rsi_series) >= 14 else None

            # Volume trend (last 5d vs avg)
            avg_vol = df["Volume"].mean()
            recent_vol = df["Volume"].iloc[-5:].mean() if len(df) >= 5 else avg_vol
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

            sector_data.append({
                "sector": sector_name,
                "etf": etf_symbol,
                "current_price": round(last, 2),
                "return_pct": round(ret, 2),
                "return_5d_pct": round(ret_5d, 2) if ret_5d is not None else None,
                "rsi": round(rsi, 1) if rsi and not pd.isna(rsi) else None,
                "volume_ratio": round(vol_ratio, 2),
                "trend": _classify_trend(ret, ret_5d),
            })

        except Exception:
            continue

    # Sort by return
    sector_data.sort(key=lambda x: x["return_pct"], reverse=True)

    # Add rank
    for i, s in enumerate(sector_data, 1):
        s["rank"] = i

    # Top / bottom sectors
    top_sectors = sector_data[:3] if len(sector_data) >= 3 else sector_data
    bottom_sectors = sector_data[-3:][::-1] if len(sector_data) >= 3 else []

    # Rotation signal (which sectors gaining/losing momentum)
    rotation = _detect_rotation(sector_data)

    # Global indices
    global_data = _get_global_indices(period)

    # Market breadth
    positive = sum(1 for s in sector_data if s["return_pct"] > 0)
    negative = sum(1 for s in sector_data if s["return_pct"] <= 0)
    breadth = "Bullish" if positive > negative else "Bearish" if negative > positive else "Neutral"

    return {
        "period": period,
        "sectors": sector_data,
        "top_sectors": top_sectors,
        "bottom_sectors": bottom_sectors,
        "rotation_signals": rotation,
        "market_breadth": {
            "positive_sectors": positive,
            "negative_sectors": negative,
            "breadth_label": breadth,
        },
        "global_indices": global_data,
    }


def _classify_trend(ret: float, ret_5d: float = None) -> str:
    """Classify sector trend based on returns."""
    if ret > 5:
        trend = "strong_up"
    elif ret > 1:
        trend = "up"
    elif ret > -1:
        trend = "neutral"
    elif ret > -5:
        trend = "down"
    else:
        trend = "strong_down"

    # Refine with 5d momentum
    if ret_5d is not None:
        if trend in ("up", "neutral") and ret_5d > 2:
            trend = "accelerating_up"
        elif trend in ("down", "neutral") and ret_5d < -2:
            trend = "accelerating_down"

    return trend


def _detect_rotation(sector_data: list[dict]) -> list[str]:
    """Detect sector rotation signals."""
    signals = []

    defensive = ["Utilities", "Consumer Staples", "Healthcare"]
    cyclical = ["Technology", "Consumer Discretionary", "Industrials", "Materials"]
    financial = ["Financials", "Real Estate"]

    def avg_return(names):
        vals = [s["return_pct"] for s in sector_data if s["sector"] in names]
        return sum(vals) / len(vals) if vals else 0

    def avg_return_5d(names):
        vals = [s["return_5d_pct"] for s in sector_data
                if s["sector"] in names and s.get("return_5d_pct") is not None]
        return sum(vals) / len(vals) if vals else 0

    def_ret = avg_return(defensive)
    cyc_ret = avg_return(cyclical)
    def_5d = avg_return_5d(defensive)
    cyc_5d = avg_return_5d(cyclical)

    if cyc_ret > def_ret + 2:
        signals.append("Risk-ON: Cyclicals outperforming defensives → bullish market sentiment")
    elif def_ret > cyc_ret + 2:
        signals.append("Risk-OFF: Defensives outperforming cyclicals → defensive positioning")

    if def_5d > cyc_5d + 1:
        signals.append("Short-term rotation INTO defensives (Utilities, Staples, Healthcare)")
    elif cyc_5d > def_5d + 1:
        signals.append("Short-term rotation INTO cyclicals (Tech, Discretionary, Industrials)")

    energy = next((s for s in sector_data if s["sector"] == "Energy"), None)
    if energy and energy["return_pct"] > 5:
        signals.append("Energy sector strength → commodity/inflation-driven market")
    elif energy and energy["return_pct"] < -5:
        signals.append("Energy sector weakness → lower commodity/oil environment")

    if not signals:
        signals.append("No clear sector rotation detected - market moving broadly")

    return signals


def _get_global_indices(period: str) -> list[dict]:
    """Fetch global index performance."""
    results = []
    for name, symbol in GLOBAL_INDICES.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            if df.empty or len(df) < 2:
                continue

            first = df["Close"].iloc[0]
            last = df["Close"].iloc[-1]
            ret = ((last - first) / first) * 100
            change_1d = ((df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100

            results.append({
                "name": name,
                "symbol": symbol,
                "current": round(last, 2),
                "return_pct": round(ret, 2),
                "change_1d_pct": round(change_1d, 2),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results
