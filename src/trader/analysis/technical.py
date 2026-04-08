import pandas as pd
import pandas_ta as ta

from trader.analysis.volatility import calculate_volatility_metrics, calculate_volatility_position_size
from trader.config import VOLATILITY_LOOKBACK_DAYS, BASE_POSITION_PCT, MIN_POSITION_PCT, MAX_POSITION_PCT


def calculate_indicators(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 20:
        return {"error": "Insufficient data for technical analysis"}

    result = {}

    rsi = ta.rsi(df["Close"], length=14)
    if rsi is not None and not rsi.empty:
        result["rsi"] = round(rsi.iloc[-1], 2)
        result["rsi_signal"] = (
            "oversold" if result["rsi"] < 30
            else "overbought" if result["rsi"] > 70
            else "neutral"
        )

    macd = ta.macd(df["Close"])
    if macd is not None and not macd.empty:
        result["macd"] = round(macd.iloc[-1, 0], 4)
        result["macd_signal"] = round(macd.iloc[-1, 1], 4)
        result["macd_histogram"] = round(macd.iloc[-1, 2], 4)
        result["macd_trend"] = "bullish" if result["macd"] > result["macd_signal"] else "bearish"

    for period in [20, 50, 200]:
        sma = ta.sma(df["Close"], length=period)
        if sma is not None and not sma.empty and not pd.isna(sma.iloc[-1]):
            result[f"sma_{period}"] = round(sma.iloc[-1], 2)

    bb = ta.bbands(df["Close"], length=20, std=2)
    if bb is not None and not bb.empty:
        result["bb_upper"] = round(bb.iloc[-1, 0], 2)
        result["bb_middle"] = round(bb.iloc[-1, 1], 2)
        result["bb_lower"] = round(bb.iloc[-1, 2], 2)
        current_price = df["Close"].iloc[-1]
        bb_width = result["bb_upper"] - result["bb_lower"]
        if bb_width > 0:
            result["bb_position"] = round(
                (current_price - result["bb_lower"]) / bb_width, 2
            )

    if "Volume" in df.columns and len(df) >= 20:
        vol_sma = df["Volume"].rolling(20).mean()
        if not vol_sma.empty and not pd.isna(vol_sma.iloc[-1]):
            current_vol = df["Volume"].iloc[-1]
            avg_vol = vol_sma.iloc[-1]
            result["volume_current"] = int(current_vol)
            result["volume_avg_20"] = int(avg_vol)
            result["volume_ratio"] = round(current_vol / avg_vol, 2) if avg_vol > 0 else 0

    result["current_price"] = round(df["Close"].iloc[-1], 2)
    result["price_change_5d"] = round(
        ((df["Close"].iloc[-1] - df["Close"].iloc[-5]) / df["Close"].iloc[-5]) * 100, 2
    ) if len(df) >= 5 else None

    return result


def analyze_stock(symbol: str, period: str = "3mo") -> dict:
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period)
    if df.empty:
        return {"symbol": symbol, "error": "No data available"}

    indicators = calculate_indicators(df)
    indicators["symbol"] = symbol

    signals = []
    if "rsi" in indicators:
        if indicators["rsi"] < 30:
            signals.append("RSI oversold - potential buy")
        elif indicators["rsi"] > 70:
            signals.append("RSI overbought - potential sell")

    if "macd_trend" in indicators:
        if indicators["macd_trend"] == "bullish":
            signals.append("MACD bullish crossover")
        else:
            signals.append("MACD bearish crossover")

    if "bb_position" in indicators:
        if indicators["bb_position"] < 0.1:
            signals.append("Price near lower Bollinger Band - potential bounce")
        elif indicators["bb_position"] > 0.9:
            signals.append("Price near upper Bollinger Band - potential resistance")

    price = indicators.get("current_price", 0)
    if "sma_20" in indicators and "sma_50" in indicators:
        if indicators["sma_20"] > indicators["sma_50"] and price > indicators["sma_20"]:
            signals.append("Price above SMA20 > SMA50 - bullish trend")
        elif indicators["sma_20"] < indicators["sma_50"] and price < indicators["sma_20"]:
            signals.append("Price below SMA20 < SMA50 - bearish trend")

    if "volume_ratio" in indicators and indicators["volume_ratio"] > 1.5:
        signals.append(f"High volume ({indicators['volume_ratio']}x average)")

    vol_metrics = calculate_volatility_metrics(df, VOLATILITY_LOOKBACK_DAYS)
    indicators["volatility"] = vol_metrics
    if "annualized_volatility" in vol_metrics:
        suggested_size = calculate_volatility_position_size(
            vol_metrics["annualized_volatility"],
            BASE_POSITION_PCT, MIN_POSITION_PCT, MAX_POSITION_PCT,
        )
        indicators["suggested_position_pct"] = round(suggested_size * 100, 1)

    indicators["signals"] = signals
    return indicators
