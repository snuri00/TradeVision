import pandas as pd
import pandas_ta as ta
from dataclasses import dataclass, field
from typing import Callable

from trader.analysis.volatility import calculate_volatility_metrics, calculate_volatility_position_size
from trader.analysis.correlation import get_correlation_risk
from trader.analysis.fundamental import get_fundamentals, score_fundamentals
from trader.config import (
    VOLATILITY_LOOKBACK_DAYS, BASE_POSITION_PCT,
    MIN_POSITION_PCT, MAX_POSITION_PCT, CORRELATION_LOOKBACK_DAYS,
    MARKETS, detect_market,
)


@dataclass
class Signal:
    action: str
    symbol: str
    confidence: float
    reasoning: list[str]
    agent: str


@dataclass
class AgentState:
    name: str
    log: list[str] = field(default_factory=list)


class TraderAgent:
    def __init__(self):
        self.state = AgentState(name="Trader")

    def analyze(self, symbol: str, df: pd.DataFrame, day_data: dict) -> Signal:
        if df.empty or len(df) < 50:
            return Signal("hold", symbol, 0, ["Insufficient data"], self.state.name)

        reasons = []
        buy_points = 0
        sell_points = 0
        price = df["Close"].iloc[-1]

        rsi = ta.rsi(df["Close"], length=14)
        if rsi is not None and len(rsi) >= 2:
            rsi_val = rsi.iloc[-1]
            rsi_prev = rsi.iloc[-2]
            if rsi_val < 30:
                buy_points += 2
                reasons.append(f"RSI {rsi_val:.1f} oversold")
            elif rsi_val < 40 and rsi_val > rsi_prev:
                buy_points += 1
                reasons.append(f"RSI {rsi_val:.1f} recovering")
            elif rsi_val > 70:
                sell_points += 2
                reasons.append(f"RSI {rsi_val:.1f} overbought")
            elif rsi_val > 60 and rsi_val < rsi_prev:
                sell_points += 1
                reasons.append(f"RSI {rsi_val:.1f} weakening")

        macd = ta.macd(df["Close"])
        if macd is not None and len(macd) >= 3:
            hist = macd.iloc[-1, 2]
            prev_hist = macd.iloc[-2, 2]
            prev2_hist = macd.iloc[-3, 2]

            if hist > 0 and prev_hist <= 0 and prev2_hist <= 0:
                buy_points += 2
                reasons.append("MACD confirmed bullish crossover")
            elif hist < 0 and prev_hist >= 0 and prev2_hist >= 0:
                sell_points += 2
                reasons.append("MACD confirmed bearish crossover")

            if hist > prev_hist > prev2_hist and hist > 0:
                buy_points += 1
                reasons.append("MACD histogram accelerating up")
            elif hist < prev_hist < prev2_hist and hist < 0:
                sell_points += 1
                reasons.append("MACD histogram accelerating down")

        adx = ta.adx(df["High"], df["Low"], df["Close"], length=14)
        if adx is not None and not adx.empty:
            adx_val = adx.iloc[-1, 0]
            plus_di = adx.iloc[-1, 1]
            minus_di = adx.iloc[-1, 2]

            if adx_val > 25:
                if plus_di > minus_di:
                    buy_points += 2
                    reasons.append(f"ADX {adx_val:.0f} strong uptrend")
                else:
                    sell_points += 2
                    reasons.append(f"ADX {adx_val:.0f} strong downtrend")
            elif adx_val < 20:
                reasons.append(f"ADX {adx_val:.0f} no trend - avoid")

        sma20 = ta.sma(df["Close"], length=20)
        sma50 = ta.sma(df["Close"], length=50)
        ema9 = ta.ema(df["Close"], length=9)
        ema21 = ta.ema(df["Close"], length=21)

        if all(x is not None and not x.empty for x in [sma20, sma50, ema9, ema21]):
            s20, s50 = sma20.iloc[-1], sma50.iloc[-1]
            e9, e21 = ema9.iloc[-1], ema21.iloc[-1]

            if not pd.isna(s20) and not pd.isna(s50):
                if price > s20 > s50 and e9 > e21:
                    buy_points += 2
                    reasons.append("All MAs aligned bullish")
                elif price < s20 < s50 and e9 < e21:
                    sell_points += 2
                    reasons.append("All MAs aligned bearish")

            if len(ema9) >= 2 and len(ema21) >= 2:
                e9_prev, e21_prev = ema9.iloc[-2], ema21.iloc[-2]
                if e9.item() > e21.item() and e9_prev.item() <= e21_prev.item():
                    buy_points += 1
                    reasons.append("EMA9/21 golden cross")
                elif e9.item() < e21.item() and e9_prev.item() >= e21_prev.item():
                    sell_points += 1
                    reasons.append("EMA9/21 death cross")

        bb = ta.bbands(df["Close"], length=20, std=2)
        if bb is not None and not bb.empty:
            bb_lower = bb.iloc[-1, 0]
            bb_upper = bb.iloc[-1, 2]
            bb_mid = bb.iloc[-1, 1]
            bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid > 0 else 0

            if price <= bb_lower and bb_width > 0.04:
                buy_points += 1
                reasons.append("Price at lower BB with wide bands")
            elif price >= bb_upper:
                sell_points += 1
                reasons.append("Price at upper BB")

        if len(df) >= 20 and "Volume" in df.columns:
            vol_avg = df["Volume"].rolling(20).mean().iloc[-1]
            if vol_avg > 0:
                vol_ratio = df["Volume"].iloc[-1] / vol_avg
                change = day_data.get("change_pct", 0)
                if vol_ratio > 1.5 and change > 1:
                    buy_points += 1
                    reasons.append(f"Volume confirmation ({vol_ratio:.1f}x) on up day")
                elif vol_ratio > 1.5 and change < -1:
                    sell_points += 1
                    reasons.append(f"Volume confirmation ({vol_ratio:.1f}x) on down day")
                elif vol_ratio < 0.5:
                    reasons.append("Low volume - weak conviction")

        net_score = buy_points - sell_points
        max_possible = max(buy_points + sell_points, 1)
        confidence = min(abs(net_score) / max_possible, 1.0)

        if net_score >= 5:
            action = "strong_buy"
        elif net_score >= 3:
            action = "buy"
        elif net_score <= -5:
            action = "strong_sell"
        elif net_score <= -3:
            action = "sell"
        else:
            action = "hold"

        return Signal(action, symbol, confidence, reasons, self.state.name)


class NewsAnalystAgent:
    def __init__(self):
        self.state = AgentState(name="Analyst")
        self.vix_history: list[float] = []

    def analyze(self, macro_data: dict, symbol: str) -> Signal:
        reasons = []
        score = 0

        vix = macro_data.get("^VIX", {})
        if vix:
            vix_close = vix.get("close", 0)
            vix_change = vix.get("change_pct", 0)
            self.vix_history.append(vix_close)

            if vix_close > 35:
                score -= 3
                reasons.append(f"VIX {vix_close:.1f} - extreme panic, NO BUYING")
            elif vix_close > 28:
                score -= 2
                reasons.append(f"VIX {vix_close:.1f} - high fear")
            elif vix_close > 22:
                score -= 1
                reasons.append(f"VIX {vix_close:.1f} - elevated caution")
            elif vix_close < 14:
                score += 2
                reasons.append(f"VIX {vix_close:.1f} - complacent, bullish")
            elif vix_close < 18:
                score += 1
                reasons.append(f"VIX {vix_close:.1f} - calm market")

            if vix_change > 20:
                score -= 3
                reasons.append(f"VIX panic spike +{vix_change:.1f}%")
            elif vix_change > 10:
                score -= 1
                reasons.append(f"VIX rising +{vix_change:.1f}%")
            elif vix_change < -10:
                score += 1
                reasons.append(f"VIX dropping {vix_change:.1f}% - relief")

            if len(self.vix_history) >= 5:
                vix_5d_avg = sum(self.vix_history[-5:]) / 5
                if vix_close > vix_5d_avg * 1.15:
                    score -= 1
                    reasons.append("VIX trending up vs 5d avg")

        oil = macro_data.get("CL=F", {})
        if oil:
            oil_change = oil.get("change_pct", 0)
            oil_close = oil.get("close", 0)

            if oil_change > 5:
                score -= 2
                reasons.append(f"Oil surging +{oil_change:.1f}%")
            elif oil_change > 3:
                score -= 1
                reasons.append(f"Oil rising +{oil_change:.1f}%")
            elif oil_change < -5:
                score += 1
                reasons.append(f"Oil dropping {oil_change:.1f}%")

            if oil_close > 95:
                score -= 1
                reasons.append(f"Oil ${oil_close:.0f} - stagflation risk")

        gold = macro_data.get("GC=F", {})
        if gold:
            gold_change = gold.get("change_pct", 0)
            if gold_change > 3:
                score -= 2
                reasons.append(f"Gold surging +{gold_change:.1f}% - flight to safety")
            elif gold_change > 1.5:
                score -= 1
                reasons.append(f"Gold rising +{gold_change:.1f}%")

        sp500 = macro_data.get("^GSPC", {})
        if sp500:
            sp_change = sp500.get("change_pct", 0)
            if sp_change > 2:
                score += 2
                reasons.append(f"S&P 500 strong rally +{sp_change:.1f}%")
            elif sp_change > 1:
                score += 1
                reasons.append(f"S&P 500 up +{sp_change:.1f}%")
            elif sp_change < -2:
                score -= 2
                reasons.append(f"S&P 500 sharp drop {sp_change:.1f}%")
            elif sp_change < -1:
                score -= 1
                reasons.append(f"S&P 500 down {sp_change:.1f}%")

        market_key = detect_market(symbol)
        market_config = MARKETS.get(market_key)
        if market_config and market_config.currency_pair:
            fx_data = macro_data.get(market_config.currency_pair, {})
            if fx_data:
                fx_change = fx_data.get("change_pct", 0)
                pair_name = market_config.currency_pair.replace("=X", "")
                if fx_change > 2:
                    score -= 2
                    reasons.append(f"{pair_name} crash +{fx_change:.1f}% - {market_config.name} danger")
                elif fx_change > 0.5:
                    score -= 1
                    reasons.append(f"{pair_name} weakening +{fx_change:.1f}%")

        if not reasons:
            reasons.append("No significant macro signals")

        confidence = min(abs(score) / 6.0, 1.0)
        if score >= 3:
            action = "bullish"
        elif score >= 1:
            action = "slightly_bullish"
        elif score <= -3:
            action = "bearish"
        elif score <= -1:
            action = "slightly_bearish"
        else:
            action = "neutral"

        return Signal(action, symbol, confidence, reasons, self.state.name)


class FundamentalAgent:
    def __init__(self):
        self.state = AgentState(name="Fundamental")
        self.cache: dict[str, dict] = {}

    def preload(self, symbols: list[str]):
        for symbol in symbols:
            if symbol not in self.cache:
                self.cache[symbol] = get_fundamentals(symbol)

    def analyze(self, symbol: str) -> Signal:
        if symbol not in self.cache:
            self.cache[symbol] = get_fundamentals(symbol)

        fundamentals = self.cache[symbol]
        result = score_fundamentals(fundamentals)

        action_map = {
            "fundamentally_strong": "bullish",
            "fundamentally_positive": "slightly_bullish",
            "neutral": "neutral",
            "fundamentally_negative": "slightly_bearish",
            "fundamentally_weak": "bearish",
        }

        action = action_map.get(result["action"], "neutral")
        confidence = min(abs(result["score"]) / 5.0, 1.0)

        return Signal(action, symbol, confidence, result["signals"], self.state.name)


class PortfolioManagerAgent:
    def __init__(self, initial_capital: float, max_position_pct: float = 0.08,
                 max_total_exposure: float = 0.50, stop_loss_pct: float = -0.05,
                 take_profit_pct: float = 0.10,
                 data_source: Callable[[str, str], pd.DataFrame] = None):
        self.state = AgentState(name="Patron")
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, dict] = {}
        self.trade_history: list[dict] = []
        self.max_position_pct = max_position_pct
        self.max_total_exposure = max_total_exposure
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.daily_values: list[dict] = []
        self.cooldown: dict[str, int] = {}
        self.consecutive_losses: int = 0
        self.data_source = data_source

    def get_portfolio_value(self, current_prices: dict[str, float]) -> float:
        positions_value = 0
        for symbol, pos in self.positions.items():
            price = current_prices.get(symbol, pos["avg_cost"])
            positions_value += pos["quantity"] * price
        return self.cash + positions_value

    def get_exposure(self, current_prices: dict[str, float]) -> float:
        total = self.get_portfolio_value(current_prices)
        if total == 0:
            return 0
        positions_value = sum(
            pos["quantity"] * current_prices.get(sym, pos["avg_cost"])
            for sym, pos in self.positions.items()
        )
        return positions_value / total

    def check_exit_conditions(self, symbol: str, current_price: float) -> str:
        if symbol not in self.positions:
            return "none"
        pos = self.positions[symbol]
        pnl_pct = (current_price - pos["avg_cost"]) / pos["avg_cost"]

        if pnl_pct <= self.stop_loss_pct:
            return "stop_loss"

        if "trailing_stop" in pos:
            if current_price > pos["peak_price"]:
                pos["peak_price"] = current_price
                pos["trailing_stop"] = current_price * 0.96
            elif current_price <= pos["trailing_stop"]:
                return "trailing_stop"

        if pnl_pct >= self.take_profit_pct:
            if "trailing_stop" not in pos:
                pos["peak_price"] = current_price
                pos["trailing_stop"] = current_price * 0.96
            return "none"

        return "none"

    def decide(self, trader_signal: Signal, analyst_signal: Signal,
               current_prices: dict[str, float], date: str,
               fundamental_signal: Signal = None) -> dict:
        symbol = trader_signal.symbol
        current_price = current_prices.get(symbol, 0)
        if current_price == 0:
            return {"action": "hold", "symbol": symbol, "reason": "No price data"}

        if symbol in self.cooldown:
            self.cooldown[symbol] -= 1
            if self.cooldown[symbol] <= 0:
                del self.cooldown[symbol]
            else:
                return {"action": "hold", "symbol": symbol,
                        "reason": f"Cooldown {self.cooldown[symbol]} days remaining"}

        exit_cond = self.check_exit_conditions(symbol, current_price)
        if exit_cond in ("stop_loss", "trailing_stop"):
            qty = self.positions[symbol]["quantity"]
            result = self._execute_sell(symbol, qty, current_price, date,
                                         f"{exit_cond.upper()} triggered")
            if result.get("pnl", 0) < 0:
                self.consecutive_losses += 1
                self.cooldown[symbol] = 5
            return result

        trader_score = self._action_to_score(trader_signal.action)
        analyst_score = self._action_to_score(analyst_signal.action)

        if fundamental_signal:
            fund_score = self._action_to_score(fundamental_signal.action)
            combined = (trader_score * 0.50) + (analyst_score * 0.30) + (fund_score * 0.20)
            avg_confidence = (
                trader_signal.confidence * 0.50 +
                analyst_signal.confidence * 0.30 +
                fundamental_signal.confidence * 0.20
            )
        else:
            combined = (trader_score * 0.6) + (analyst_score * 0.4)
            avg_confidence = (trader_signal.confidence * 0.6 + analyst_signal.confidence * 0.4)

        exposure = self.get_exposure(current_prices)

        if analyst_score <= -2:
            if symbol in self.positions and combined <= -1:
                qty = self.positions[symbol]["quantity"]
                return self._execute_sell(symbol, qty, current_price, date,
                                           "Analyst bearish override - risk off")
            return {"action": "hold", "symbol": symbol, "reason": "Analyst bearish - no entry"}

        buy_threshold = 2.5 if self.consecutive_losses >= 2 else 2.0

        if combined >= buy_threshold and avg_confidence >= 0.5:
            if symbol in self.positions:
                return {"action": "hold", "symbol": symbol, "reason": "Already in position"}
            if exposure >= self.max_total_exposure:
                return {"action": "hold", "symbol": symbol,
                        "reason": f"Max exposure {exposure:.0%} reached"}

            position_size = self._calculate_adjusted_position_size(symbol, date)

            if self.consecutive_losses >= 2:
                position_size *= 0.5

            portfolio_value = self.get_portfolio_value(current_prices)
            max_spend = portfolio_value * position_size
            qty = int(max_spend / current_price)
            if qty <= 0:
                return {"action": "hold", "symbol": symbol, "reason": "Position too small"}

            vol_info = ""
            corr_info = ""
            if self.data_source:
                df = self.data_source(symbol, date)
                if not df.empty:
                    from trader.analysis.volatility import calculate_volatility_metrics
                    metrics = calculate_volatility_metrics(df, VOLATILITY_LOOKBACK_DAYS)
                    vol_info = f", vol={metrics['annualized_volatility']:.0%}"

                if self.positions:
                    corr_risk = self._get_correlation_risk(symbol, date)
                    corr_info = f", corr_adj={corr_risk['multiplier']}"

            self.consecutive_losses = 0
            fund_info = ""
            if fundamental_signal:
                fund_info = f", fund={fundamental_signal.action}"
            return self._execute_buy(
                symbol, qty, current_price, date,
                f"Score {combined:.1f}, conf {avg_confidence:.0%}{vol_info}{corr_info}{fund_info}"
            )

        elif combined <= -2.0 and symbol in self.positions:
            qty = self.positions[symbol]["quantity"]
            return self._execute_sell(symbol, qty, current_price, date,
                                       f"Score {combined:.1f} - bearish consensus")

        return {
            "action": "hold",
            "symbol": symbol,
            "reason": f"Score {combined:.1f}, conf {avg_confidence:.0%} - no action",
        }

    def _calculate_adjusted_position_size(self, symbol: str, date: str) -> float:
        base_size = self.max_position_pct

        if not self.data_source:
            return base_size

        df = self.data_source(symbol, date)
        if df.empty:
            return base_size

        metrics = calculate_volatility_metrics(df, VOLATILITY_LOOKBACK_DAYS)
        vol = metrics.get("annualized_volatility", 0.30)
        position_size = calculate_volatility_position_size(
            vol, BASE_POSITION_PCT, MIN_POSITION_PCT, MAX_POSITION_PCT
        )

        if self.positions:
            corr_risk = self._get_correlation_risk(symbol, date)
            position_size *= corr_risk["multiplier"]

            if corr_risk["max_correlation"] >= 0.90:
                position_size *= 0.5

        return max(MIN_POSITION_PCT, min(MAX_POSITION_PCT, position_size))

    def _get_correlation_risk(self, symbol: str, date: str) -> dict:
        if not self.data_source or not self.positions:
            return {"avg_correlation": 0, "max_correlation": 0, "top_correlated": [], "multiplier": 1.0}

        portfolio_symbols = list(self.positions.keys())
        all_symbols = list(set([symbol] + portfolio_symbols))

        price_data = {}
        for sym in all_symbols:
            df = self.data_source(sym, date)
            if not df.empty:
                price_data[sym] = df

        return get_correlation_risk(symbol, portfolio_symbols, price_data, CORRELATION_LOOKBACK_DAYS)

    def _action_to_score(self, action: str) -> float:
        mapping = {
            "strong_buy": 3, "buy": 2, "bullish": 2.5, "slightly_bullish": 1,
            "hold": 0, "neutral": 0,
            "sell": -2, "strong_sell": -3, "bearish": -2.5, "slightly_bearish": -1,
        }
        return mapping.get(action, 0)

    def _execute_buy(self, symbol: str, quantity: int, price: float,
                      date: str, reason: str) -> dict:
        cost = quantity * price
        if cost > self.cash:
            quantity = int(self.cash / price)
            cost = quantity * price
        if quantity <= 0:
            return {"action": "hold", "symbol": symbol, "reason": "No cash"}

        self.cash -= cost

        if symbol in self.positions:
            pos = self.positions[symbol]
            total_qty = pos["quantity"] + quantity
            pos["avg_cost"] = ((pos["avg_cost"] * pos["quantity"]) + cost) / total_qty
            pos["quantity"] = total_qty
        else:
            self.positions[symbol] = {
                "quantity": quantity, "avg_cost": price, "entry_date": date,
                "peak_price": price,
            }

        trade = {
            "date": date, "symbol": symbol, "side": "buy",
            "quantity": quantity, "price": price, "total": cost, "reason": reason,
        }
        self.trade_history.append(trade)
        return {"action": "buy", **trade}

    def _execute_sell(self, symbol: str, quantity: int, price: float,
                       date: str, reason: str) -> dict:
        if symbol not in self.positions:
            return {"action": "hold", "symbol": symbol, "reason": "No position"}

        pos = self.positions[symbol]
        quantity = min(quantity, pos["quantity"])
        revenue = quantity * price
        pnl = (price - pos["avg_cost"]) * quantity

        self.cash += revenue

        pos["quantity"] -= quantity
        if pos["quantity"] <= 0:
            del self.positions[symbol]

        trade = {
            "date": date, "symbol": symbol, "side": "sell",
            "quantity": quantity, "price": price, "total": revenue,
            "pnl": round(pnl, 2), "reason": reason,
        }
        self.trade_history.append(trade)
        return {"action": "sell", **trade}

    def record_daily_value(self, date: str, current_prices: dict[str, float]):
        total = self.get_portfolio_value(current_prices)
        pnl = total - self.initial_capital
        pnl_pct = (pnl / self.initial_capital) * 100

        self.daily_values.append({
            "date": date,
            "total_value": round(total, 2),
            "cash": round(self.cash, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "num_positions": len(self.positions),
            "exposure": round(self.get_exposure(current_prices) * 100, 1),
        })
