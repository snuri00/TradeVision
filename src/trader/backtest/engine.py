import json
from datetime import datetime
from trader.backtest.data_feeder import DataFeeder
from trader.backtest.agents import (
    TraderAgent, NewsAnalystAgent, PortfolioManagerAgent,
    FundamentalAgent, Signal,
)
from trader.config import get_all_macro_symbols


class BacktestEngine:
    def __init__(self, symbols: list[str], start_date: str, end_date: str,
                 initial_capital: float = 100_000.0):
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital

        macro_symbols = get_all_macro_symbols()
        all_symbols = list(set(symbols + macro_symbols))
        self.feeder = DataFeeder(all_symbols, start_date, end_date)

        self.trader = TraderAgent()
        self.analyst = NewsAnalystAgent()
        self.fundamental = FundamentalAgent()
        self.patron = PortfolioManagerAgent(
            initial_capital=initial_capital,
            max_position_pct=0.10,
            max_total_exposure=0.60,
            stop_loss_pct=-0.07,
            take_profit_pct=0.12,
            data_source=lambda sym, date: self.feeder.get_data_up_to(sym, date),
        )

        self.daily_log: list[dict] = []

    def run(self, verbose: bool = True):
        print("=" * 70)
        print(f"BACKTEST: {self.start_date} -> {self.end_date}")
        print(f"Capital: ${self.initial_capital:,.0f} | Symbols: {len(self.symbols)}")
        print("=" * 70)

        self.feeder.fetch_all_history()

        print("Loading fundamental data...")
        self.fundamental.preload(self.symbols)
        print(f"  Fundamentals loaded for {len(self.fundamental.cache)} symbols")
        print()

        day_count = 0
        for feed in self.feeder.iterate_days(self.symbols):
            date = feed["date"]
            day_count += 1

            current_prices = {}
            for sym, data in feed["stocks"].items():
                current_prices[sym] = data["close"]

            day_actions = []
            discussions = []

            for symbol in self.symbols:
                if symbol not in feed["stocks"]:
                    continue

                df = self.feeder.get_data_up_to(symbol, date)
                day_data = feed["stocks"][symbol]
                macro = feed["macro"]

                trader_signal = self.trader.analyze(symbol, df, day_data)
                analyst_signal = self.analyst.analyze(macro, symbol)
                fundamental_signal = self.fundamental.analyze(symbol)

                discussions.append({
                    "symbol": symbol,
                    "trader": {"action": trader_signal.action, "confidence": trader_signal.confidence,
                               "reasons": trader_signal.reasoning},
                    "analyst": {"action": analyst_signal.action, "confidence": analyst_signal.confidence,
                                "reasons": analyst_signal.reasoning},
                    "fundamental": {"action": fundamental_signal.action, "confidence": fundamental_signal.confidence,
                                    "reasons": fundamental_signal.reasoning},
                })

                decision = self.patron.decide(
                    trader_signal, analyst_signal, current_prices, date,
                    fundamental_signal=fundamental_signal,
                )

                if decision["action"] != "hold":
                    day_actions.append(decision)
                    if verbose:
                        side = decision["action"].upper()
                        sym = decision["symbol"]
                        qty = decision.get("quantity", 0)
                        price = decision.get("price", 0)
                        pnl = decision.get("pnl", "")
                        pnl_str = f" P&L: {pnl}" if pnl != "" else ""
                        reason = decision.get("reason", "")
                        print(f"  [{date}] {side} {qty} {sym} @ ${price:.2f}{pnl_str} | {reason}")

            self.patron.record_daily_value(date, current_prices)

            self.daily_log.append({
                "date": date,
                "actions": day_actions,
                "discussions": discussions,
                "portfolio_value": self.patron.daily_values[-1]["total_value"],
            })

            if day_count % 50 == 0 and verbose:
                val = self.patron.daily_values[-1]
                print(f"\n--- Day {day_count} ({date}) | Value: ${val['total_value']:,.2f} | "
                      f"P&L: ${val['pnl']:,.2f} ({val['pnl_pct']:+.2f}%) | "
                      f"Positions: {val['num_positions']} | Exposure: {val['exposure']:.1f}% ---\n")

        print("\n" + "=" * 70)
        self.print_results()
        return self.get_results()

    def get_results(self) -> dict:
        trades = self.patron.trade_history
        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]
        profitable = [t for t in sell_trades if t.get("pnl", 0) > 0]
        losing = [t for t in sell_trades if t.get("pnl", 0) < 0]
        total_realized_pnl = sum(t.get("pnl", 0) for t in sell_trades)

        win_rate = (len(profitable) / len(sell_trades) * 100) if sell_trades else 0

        values = [d["total_value"] for d in self.patron.daily_values]
        peak = values[0]
        max_drawdown = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (v - peak) / peak * 100
            if dd < max_drawdown:
                max_drawdown = dd

        final = self.patron.daily_values[-1] if self.patron.daily_values else {}

        return {
            "period": f"{self.start_date} -> {self.end_date}",
            "initial_capital": self.initial_capital,
            "final_value": final.get("total_value", self.initial_capital),
            "total_pnl": final.get("pnl", 0),
            "total_pnl_pct": final.get("pnl_pct", 0),
            "total_trades": len(trades),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "profitable_trades": len(profitable),
            "losing_trades": len(losing),
            "win_rate": round(win_rate, 1),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "final_exposure": final.get("exposure", 0),
            "final_positions": final.get("num_positions", 0),
        }

    def print_results(self):
        r = self.get_results()
        print("BACKTEST RESULTS")
        print("=" * 70)
        print(f"Period:           {r['period']}")
        print(f"Initial Capital:  ${r['initial_capital']:>12,.2f}")
        print(f"Final Value:      ${r['final_value']:>12,.2f}")
        print(f"Total P&L:        ${r['total_pnl']:>12,.2f} ({r['total_pnl_pct']:+.2f}%)")
        print(f"Max Drawdown:     {r['max_drawdown_pct']:>12.2f}%")
        print("-" * 70)
        print(f"Total Trades:     {r['total_trades']:>6}")
        print(f"  Buy:            {r['buy_trades']:>6}")
        print(f"  Sell:           {r['sell_trades']:>6}")
        print(f"  Profitable:     {r['profitable_trades']:>6}")
        print(f"  Losing:         {r['losing_trades']:>6}")
        print(f"Win Rate:         {r['win_rate']:>6.1f}%")
        print(f"Realized P&L:     ${r['total_realized_pnl']:>12,.2f}")
        print("-" * 70)
        print(f"Open Positions:   {r['final_positions']:>6}")
        print(f"Final Exposure:   {r['final_exposure']:>6.1f}%")
        print("=" * 70)

        if self.patron.trade_history:
            print("\nTrade Log:")
            for t in self.patron.trade_history:
                side = t["side"].upper()
                pnl = t.get("pnl", "")
                pnl_str = f" | P&L: ${pnl:,.2f}" if pnl != "" else ""
                print(f"  {t['date']} {side:4s} {t['quantity']:>5} {t['symbol']:<10s} "
                      f"@ ${t['price']:>10,.2f} = ${t['total']:>12,.2f}{pnl_str}")
                print(f"           Reason: {t['reason']}")
