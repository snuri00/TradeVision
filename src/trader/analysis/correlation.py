import pandas as pd
import numpy as np


def calculate_correlation_matrix(price_data: dict[str, pd.DataFrame],
                                  lookback_days: int = 60) -> pd.DataFrame:
    returns = {}
    for symbol, df in price_data.items():
        if df.empty or len(df) < 10:
            continue
        close = df["Close"].tail(lookback_days)
        ret = close.pct_change().dropna()
        if len(ret) >= 5:
            returns[symbol] = ret

    if len(returns) < 2:
        return pd.DataFrame()

    returns_df = pd.DataFrame(returns)
    returns_df = returns_df.dropna()

    if len(returns_df) < 5:
        return pd.DataFrame()

    return returns_df.corr()


def get_correlation_risk(candidate: str, portfolio_symbols: list[str],
                          price_data: dict[str, pd.DataFrame],
                          lookback_days: int = 60) -> dict:
    if not portfolio_symbols:
        return {
            "avg_correlation": 0.0,
            "max_correlation": 0.0,
            "top_correlated": [],
            "multiplier": 1.10,
        }

    all_symbols = list(set([candidate] + portfolio_symbols))
    relevant_data = {s: price_data[s] for s in all_symbols if s in price_data}

    corr_matrix = calculate_correlation_matrix(relevant_data, lookback_days)

    if corr_matrix.empty or candidate not in corr_matrix.columns:
        return {
            "avg_correlation": 0.0,
            "max_correlation": 0.0,
            "top_correlated": [],
            "multiplier": 1.0,
        }

    held_in_matrix = [s for s in portfolio_symbols if s in corr_matrix.columns]
    if not held_in_matrix:
        return {
            "avg_correlation": 0.0,
            "max_correlation": 0.0,
            "top_correlated": [],
            "multiplier": 1.0,
        }

    correlations = corr_matrix.loc[candidate, held_in_matrix]
    avg_corr = float(correlations.mean())
    max_corr = float(correlations.max())

    top_correlated = [
        {"symbol": sym, "correlation": round(float(correlations[sym]), 3)}
        for sym in correlations.nlargest(3).index
    ]

    multiplier = _correlation_multiplier(avg_corr)

    return {
        "avg_correlation": round(avg_corr, 3),
        "max_correlation": round(max_corr, 3),
        "top_correlated": top_correlated,
        "multiplier": round(multiplier, 2),
    }


def _correlation_multiplier(avg_correlation: float) -> float:
    if avg_correlation >= 0.80:
        return 0.65
    elif avg_correlation >= 0.60:
        return 0.80
    elif avg_correlation >= 0.40:
        return 0.95
    elif avg_correlation >= 0.20:
        return 1.05
    else:
        return 1.10
