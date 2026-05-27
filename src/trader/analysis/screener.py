"""Custom multi-criteria stock screener."""
import yfinance as yf
import pandas as pd
from trader.config import MARKETS


def screen_stocks(
    market: str = "",
    min_pe: float = None,
    max_pe: float = None,
    min_pb: float = None,
    max_pb: float = None,
    min_roe: float = None,
    max_roe: float = None,
    min_rsi: float = None,
    max_rsi: float = None,
    min_volume: int = None,
    max_market_cap: float = None,
    min_market_cap: float = None,
    min_return_1mo: float = None,
    max_return_1mo: float = None,
    min_dividend_yield: float = None,
    above_sma50: bool = None,
    top_n: int = 20,
) -> dict:
    """
    Screen stocks across all (or specific) markets using custom criteria.

    Parameters (all optional):
      market: bist, us, uk, germany, france, japan, crypto, gold, commodities, etc.
      min_pe / max_pe: P/E ratio range
      min_pb / max_pb: P/B ratio range
      min_roe / max_roe: Return on Equity % range
      min_rsi / max_rsi: RSI range (e.g., max_rsi=30 for oversold)
      min_volume: minimum average daily volume
      min_market_cap / max_market_cap: market cap in USD
      min_return_1mo / max_return_1mo: 1-month price return %
      min_dividend_yield: minimum dividend yield %
      above_sma50: True = price above SMA50, False = below SMA50
      top_n: max results to return
    """
    # Collect symbols
    if market and market in MARKETS:
        symbols = MARKETS[market].symbols
    else:
        symbols = []
        for m in MARKETS.values():
            symbols.extend(m.symbols)

    passed = []
    screened = 0

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            df = ticker.history(period="2mo")

            if df.empty or len(df) < 10:
                continue

            screened += 1
            result = {"symbol": symbol}
            failed = False

            # --- Fundamental filters ---
            pe = info.get("trailingPE")
            pb = info.get("priceToBook")
            roe = info.get("returnOnEquity")
            div_yield = info.get("dividendYield")
            mkt_cap = info.get("marketCap")

            if pe is not None:
                result["pe_ratio"] = round(pe, 2)
            if pb is not None:
                result["pb_ratio"] = round(pb, 2)
            if roe is not None:
                result["roe_pct"] = round(roe * 100, 2)
            if div_yield is not None:
                result["dividend_yield_pct"] = round(div_yield * 100, 2)
            if mkt_cap is not None:
                result["market_cap"] = mkt_cap

            result["sector"] = info.get("sector", "")
            result["industry"] = info.get("industry", "")
            result["name"] = info.get("shortName", symbol)

            if min_pe is not None and (pe is None or pe < min_pe):
                failed = True
            if max_pe is not None and (pe is None or pe > max_pe):
                failed = True
            if min_pb is not None and (pb is None or pb < min_pb):
                failed = True
            if max_pb is not None and (pb is None or pb > max_pb):
                failed = True
            if min_roe is not None and (roe is None or roe * 100 < min_roe):
                failed = True
            if max_roe is not None and (roe is None or roe * 100 > max_roe):
                failed = True
            if min_dividend_yield is not None and (div_yield is None or div_yield * 100 < min_dividend_yield):
                failed = True
            if min_market_cap is not None and (mkt_cap is None or mkt_cap < min_market_cap):
                failed = True
            if max_market_cap is not None and (mkt_cap is None or mkt_cap > max_market_cap):
                failed = True

            if failed:
                continue

            # --- Technical filters ---
            current_price = df["Close"].iloc[-1]
            result["current_price"] = round(current_price, 4)

            # Average volume
            avg_vol = int(df["Volume"].mean())
            result["avg_volume"] = avg_vol
            if min_volume is not None and avg_vol < min_volume:
                continue

            # 1-month return
            if len(df) >= 22:
                ret_1mo = ((df["Close"].iloc[-1] - df["Close"].iloc[-22]) / df["Close"].iloc[-22]) * 100
                result["return_1mo_pct"] = round(ret_1mo, 2)
                if min_return_1mo is not None and ret_1mo < min_return_1mo:
                    continue
                if max_return_1mo is not None and ret_1mo > max_return_1mo:
                    continue

            # RSI
            delta = df["Close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else None
            if rsi is not None and not pd.isna(rsi):
                result["rsi"] = round(rsi, 1)
                if min_rsi is not None and rsi < min_rsi:
                    continue
                if max_rsi is not None and rsi > max_rsi:
                    continue

            # SMA50
            if len(df) >= 50:
                sma50 = df["Close"].rolling(50).mean().iloc[-1]
                result["sma50"] = round(sma50, 4)
                result["above_sma50"] = current_price > sma50
                if above_sma50 is True and current_price <= sma50:
                    continue
                if above_sma50 is False and current_price >= sma50:
                    continue

            passed.append(result)

        except Exception:
            continue

    # Sort by P/E (ascending) if available, else by return
    passed.sort(key=lambda x: x.get("return_1mo_pct", 0), reverse=True)

    criteria_used = {}
    if min_pe is not None: criteria_used["min_pe"] = min_pe
    if max_pe is not None: criteria_used["max_pe"] = max_pe
    if min_pb is not None: criteria_used["min_pb"] = min_pb
    if max_pb is not None: criteria_used["max_pb"] = max_pb
    if min_roe is not None: criteria_used["min_roe_pct"] = min_roe
    if max_roe is not None: criteria_used["max_roe_pct"] = max_roe
    if min_rsi is not None: criteria_used["min_rsi"] = min_rsi
    if max_rsi is not None: criteria_used["max_rsi"] = max_rsi
    if min_volume is not None: criteria_used["min_volume"] = min_volume
    if min_market_cap is not None: criteria_used["min_market_cap"] = min_market_cap
    if max_market_cap is not None: criteria_used["max_market_cap"] = max_market_cap
    if min_return_1mo is not None: criteria_used["min_return_1mo_pct"] = min_return_1mo
    if max_return_1mo is not None: criteria_used["max_return_1mo_pct"] = max_return_1mo
    if min_dividend_yield is not None: criteria_used["min_dividend_yield_pct"] = min_dividend_yield
    if above_sma50 is not None: criteria_used["above_sma50"] = above_sma50

    return {
        "market": market if market else "all",
        "screened_total": screened,
        "passed": len(passed),
        "criteria": criteria_used,
        "results": passed[:top_n],
    }
