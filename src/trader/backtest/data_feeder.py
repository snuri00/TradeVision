import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from trader.config import get_all_macro_symbols


class DataFeeder:
    def __init__(self, symbols: list[str], start_date: str, end_date: str):
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.all_data: dict[str, pd.DataFrame] = {}
        self.trading_days: list[str] = []
        self.current_day_index: int = 0

    def fetch_all_history(self):
        print(f"Fetching historical data: {self.start_date} -> {self.end_date}")
        lookback_start = (datetime.strptime(self.start_date, "%Y-%m-%d") - timedelta(days=120)).strftime("%Y-%m-%d")

        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=lookback_start, end=self.end_date)
                if not df.empty:
                    df.index = df.index.tz_localize(None) if df.index.tz else df.index
                    self.all_data[symbol] = df
                    print(f"  {symbol}: {len(df)} bars loaded")
                else:
                    print(f"  {symbol}: NO DATA")
            except Exception as e:
                print(f"  {symbol}: ERROR - {e}")

        if self.all_data:
            ref_symbol = list(self.all_data.keys())[0]
            ref_df = self.all_data[ref_symbol]
            mask = ref_df.index >= self.start_date
            self.trading_days = [d.strftime("%Y-%m-%d") for d in ref_df.index[mask]]
            print(f"\n{len(self.trading_days)} trading days to simulate")

    def get_data_up_to(self, symbol: str, date: str) -> pd.DataFrame:
        if symbol not in self.all_data:
            return pd.DataFrame()
        df = self.all_data[symbol]
        return df[df.index <= date].copy()

    def get_day_data(self, symbol: str, date: str) -> dict:
        df = self.get_data_up_to(symbol, date)
        if df.empty:
            return {}
        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else row
        change_pct = ((row["Close"] - prev["Close"]) / prev["Close"]) * 100

        return {
            "date": date,
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]),
            "change_pct": round(change_pct, 2),
        }

    def get_daily_feed(self, date: str, watchlist: list[str]) -> dict:
        feed = {"date": date, "stocks": {}, "macro": {}}

        for symbol in watchlist:
            data = self.get_day_data(symbol, date)
            if data:
                feed["stocks"][symbol] = data

        for macro_symbol in get_all_macro_symbols():
            data = self.get_day_data(macro_symbol, date)
            if data:
                feed["macro"][macro_symbol] = data

        return feed

    def iterate_days(self, watchlist: list[str]):
        for date in self.trading_days:
            feed = self.get_daily_feed(date, watchlist)
            yield feed
