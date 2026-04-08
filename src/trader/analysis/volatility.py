import pandas as pd
import numpy as np


def calculate_volatility_metrics(df: pd.DataFrame, lookback_days: int = 60) -> dict:
    if df.empty or len(df) < 10:
        return {"error": "Insufficient data", "annualized_volatility": 0.30}

    close = df["Close"].tail(lookback_days)
    returns = close.pct_change().dropna()

    if len(returns) < 5:
        return {"error": "Not enough returns data", "annualized_volatility": 0.30}

    daily_vol = returns.std()
    annualized_vol = daily_vol * np.sqrt(252)

    rolling_30d = returns.rolling(30).std() * np.sqrt(252)
    rolling_30d = rolling_30d.dropna()
    if len(rolling_30d) > 0:
        current_30d = rolling_30d.iloc[-1]
        percentile = (rolling_30d < current_30d).sum() / len(rolling_30d) * 100
    else:
        percentile = 50.0

    return {
        "daily_volatility": round(float(daily_vol), 6),
        "annualized_volatility": round(float(annualized_vol), 4),
        "volatility_percentile": round(float(percentile), 1),
        "data_points": len(returns),
    }


def calculate_volatility_position_size(annualized_volatility: float,
                                        base_position_pct: float = 0.10,
                                        min_position_pct: float = 0.03,
                                        max_position_pct: float = 0.15) -> float:
    vol = annualized_volatility

    if vol < 0.15:
        multiplier = 1.5
    elif vol < 0.30:
        multiplier = 1.0 - ((vol - 0.15) / 0.15) * 0.3
    elif vol < 0.50:
        multiplier = 0.7 - ((vol - 0.30) / 0.20) * 0.3
    else:
        multiplier = 0.3

    position_pct = base_position_pct * multiplier
    return max(min_position_pct, min(max_position_pct, position_pct))
