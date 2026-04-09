import yfinance as yf
import pandas as pd
from trader.analysis.technical import calculate_indicators


TIMEFRAME_MAP = {
    "15m": {"period": "5d", "interval": "15m"},
    "1h": {"period": "1mo", "interval": "1h"},
    "4h": {"period": "3mo", "interval": "1h"},
    "1d": {"period": "6mo", "interval": "1d"},
    "1w": {"period": "2y", "interval": "1wk"},
}


def _resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    resampled = df.resample("4h").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()
    return resampled


def get_timeframe_data(symbol: str, timeframe: str) -> pd.DataFrame:
    if timeframe not in TIMEFRAME_MAP:
        return pd.DataFrame()

    config = TIMEFRAME_MAP[timeframe]
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=config["period"], interval=config["interval"])

    if not df.empty:
        df.index = df.index.tz_localize(None) if df.index.tz else df.index

    if timeframe == "4h" and not df.empty:
        df = _resample_to_4h(df)

    return df


def analyze_timeframe(symbol: str, timeframe: str) -> dict:
    df = get_timeframe_data(symbol, timeframe)
    if df.empty:
        return {"timeframe": timeframe, "error": "No data available"}

    indicators = calculate_indicators(df)
    indicators["timeframe"] = timeframe
    indicators["bars"] = len(df)
    return indicators


def _classify_bias(indicators: dict) -> str:
    if "error" in indicators:
        return "neutral"

    score = 0

    rsi = indicators.get("rsi")
    if rsi is not None:
        if rsi < 30:
            score += 2
        elif rsi < 40:
            score += 1
        elif rsi > 70:
            score -= 2
        elif rsi > 60:
            score -= 1

    if indicators.get("macd_trend") == "bullish":
        score += 1
    elif indicators.get("macd_trend") == "bearish":
        score -= 1

    price = indicators.get("current_price", 0)
    sma20 = indicators.get("sma_20")
    sma50 = indicators.get("sma_50")
    if price and sma20 and sma50:
        if price > sma20 > sma50:
            score += 2
        elif price < sma20 < sma50:
            score -= 2

    if score >= 3:
        return "strong_bullish"
    elif score >= 1:
        return "bullish"
    elif score <= -3:
        return "strong_bearish"
    elif score <= -1:
        return "bearish"
    return "neutral"


def multi_timeframe_analysis(symbol: str,
                              timeframes: list[str] = None) -> dict:
    if timeframes is None:
        timeframes = ["1d", "4h", "1h"]

    results = {}
    biases = {}
    for tf in timeframes:
        analysis = analyze_timeframe(symbol, tf)
        bias = _classify_bias(analysis)
        analysis["bias"] = bias
        results[tf] = analysis
        biases[tf] = bias

    alignment = _check_alignment(biases)

    return {
        "symbol": symbol,
        "timeframes": results,
        "alignment": alignment,
    }


def _check_alignment(biases: dict[str, str]) -> dict:
    bias_values = list(biases.values())

    bullish_count = sum(1 for b in bias_values if "bullish" in b)
    bearish_count = sum(1 for b in bias_values if "bearish" in b)
    total = len(bias_values)

    if bullish_count == total:
        direction = "all_bullish"
        strength = "strong"
    elif bearish_count == total:
        direction = "all_bearish"
        strength = "strong"
    elif bullish_count > bearish_count:
        direction = "mostly_bullish"
        strength = "moderate"
    elif bearish_count > bullish_count:
        direction = "mostly_bearish"
        strength = "moderate"
    else:
        direction = "mixed"
        strength = "weak"

    aligned = bullish_count == total or bearish_count == total

    return {
        "direction": direction,
        "strength": strength,
        "aligned": aligned,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": total - bullish_count - bearish_count,
        "recommendation": (
            "Strong entry signal - all timeframes agree"
            if aligned and strength == "strong"
            else "Moderate signal - majority agrees"
            if strength == "moderate"
            else "No clear signal - timeframes conflict"
        ),
    }
