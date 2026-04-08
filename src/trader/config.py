import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "trader.db"

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY", "")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")


@dataclass
class MarketConfig:
    name: str
    currency: str
    suffix: str
    initial_capital: float
    symbols: list[str]
    index_symbol: str = ""
    currency_pair: str = ""
    macro_symbols: list[str] = field(default_factory=list)
    special_symbols: dict[str, str] = field(default_factory=dict)

    def normalize_symbol(self, symbol: str) -> str:
        if self.suffix and not symbol.endswith(self.suffix):
            return f"{symbol}{self.suffix}"
        return symbol

    def owns_symbol(self, symbol: str) -> bool:
        if self.suffix:
            return symbol.endswith(self.suffix)
        if self.special_symbols:
            return symbol in self.special_symbols.values()
        return False


MARKETS: dict[str, MarketConfig] = {
    "bist": MarketConfig(
        name="BIST",
        currency="TRY",
        suffix=".IS",
        initial_capital=3_000_000.0,
        symbols=[
            "THYAO.IS", "GARAN.IS", "AKBNK.IS", "EREGL.IS",
            "SISE.IS", "KCHOL.IS", "TUPRS.IS", "SAHOL.IS",
            "BIMAS.IS", "ASELS.IS", "PGSUS.IS", "TAVHL.IS",
            "TOASO.IS", "FROTO.IS", "SASA.IS", "KOZAL.IS",
        ],
        index_symbol="XU100.IS",
        currency_pair="USDTRY=X",
    ),
    "us": MarketConfig(
        name="US",
        currency="USD",
        suffix="",
        initial_capital=100_000.0,
        symbols=[
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
            "NVDA", "META", "JPM", "V", "JNJ",
        ],
        index_symbol="^GSPC",
    ),
    "uk": MarketConfig(
        name="UK",
        currency="GBP",
        suffix=".L",
        initial_capital=500_000.0,
        symbols=[
            "VOD.L", "BP.L", "HSBA.L", "GSK.L", "SHEL.L",
            "AZN.L", "ULVR.L", "RIO.L", "LSEG.L", "DGE.L",
        ],
        index_symbol="^FTSE",
        currency_pair="GBPUSD=X",
    ),
    "germany": MarketConfig(
        name="Germany",
        currency="EUR",
        suffix=".DE",
        initial_capital=100_000.0,
        symbols=[
            "SIE.DE", "SAP.DE", "ALV.DE", "BAS.DE", "DTE.DE",
            "MBG.DE", "BMW.DE", "ADS.DE", "MUV2.DE", "DPW.DE",
        ],
        index_symbol="^GDAXI",
        currency_pair="EURUSD=X",
    ),
    "france": MarketConfig(
        name="France",
        currency="EUR",
        suffix=".PA",
        initial_capital=100_000.0,
        symbols=[
            "MC.PA", "TTE.PA", "OR.PA", "SAN.PA", "AI.PA",
            "AIR.PA", "SU.PA", "BNP.PA", "CS.PA", "DG.PA",
        ],
        index_symbol="^FCHI",
        currency_pair="EURUSD=X",
    ),
    "japan": MarketConfig(
        name="Japan",
        currency="JPY",
        suffix=".T",
        initial_capital=15_000_000.0,
        symbols=[
            "7203.T", "6758.T", "9984.T", "6861.T", "8306.T",
            "7267.T", "9432.T", "6501.T", "4502.T", "6902.T",
        ],
        index_symbol="^N225",
        currency_pair="USDJPY=X",
    ),
    "hongkong": MarketConfig(
        name="Hong Kong",
        currency="HKD",
        suffix=".HK",
        initial_capital=800_000.0,
        symbols=[
            "9988.HK", "0700.HK", "1299.HK", "0005.HK", "0941.HK",
            "2318.HK", "0388.HK", "1810.HK", "0011.HK", "0066.HK",
        ],
        index_symbol="^HSI",
        currency_pair="USDHKD=X",
    ),
    "india": MarketConfig(
        name="India",
        currency="INR",
        suffix=".NS",
        initial_capital=8_000_000.0,
        symbols=[
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
            "HINDUNILVR.NS", "ITC.NS", "BHARTIARTL.NS", "SBIN.NS", "LT.NS",
        ],
        index_symbol="^NSEI",
        currency_pair="USDINR=X",
    ),
    "australia": MarketConfig(
        name="Australia",
        currency="AUD",
        suffix=".AX",
        initial_capital=150_000.0,
        symbols=[
            "BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX", "WBC.AX",
            "ANZ.AX", "WES.AX", "MQG.AX", "FMG.AX", "WOW.AX",
        ],
        index_symbol="^AXJO",
        currency_pair="AUDUSD=X",
    ),
    "gold": MarketConfig(
        name="Gold",
        currency="USD",
        suffix="",
        initial_capital=100_000.0,
        symbols=["GC=F", "GLD", "XAUUSD=X"],
        special_symbols={"futures": "GC=F", "etf": "GLD", "spot_usd": "XAUUSD=X"},
    ),
    "commodities": MarketConfig(
        name="Commodities",
        currency="USD",
        suffix="",
        initial_capital=100_000.0,
        symbols=["SI=F", "CL=F", "HG=F", "NG=F", "PL=F"],
        special_symbols={
            "silver": "SI=F", "oil": "CL=F", "copper": "HG=F",
            "natural_gas": "NG=F", "platinum": "PL=F",
        },
    ),
    "crypto": MarketConfig(
        name="Crypto",
        currency="USD",
        suffix="-USD",
        initial_capital=50_000.0,
        symbols=[
            "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
            "ADA-USD", "AVAX-USD", "DOT-USD", "LINK-USD", "MATIC-USD",
        ],
    ),
}


def detect_market(symbol: str) -> str:
    for market_key, market in MARKETS.items():
        if market.suffix and symbol.endswith(market.suffix):
            return market_key
        if market.special_symbols and symbol in market.special_symbols.values():
            return market_key
    return "us"


def get_all_index_symbols() -> dict[str, str]:
    result = {}
    for key, market in MARKETS.items():
        if market.index_symbol:
            result[market.name] = market.index_symbol
    result.update({
        "BIST100": MARKETS["bist"].index_symbol,
        "SP500": MARKETS["us"].index_symbol,
        "FTSE100": MARKETS["uk"].index_symbol,
        "USDTRY": MARKETS["bist"].currency_pair,
        "DAX": MARKETS["germany"].index_symbol,
        "CAC40": MARKETS["france"].index_symbol,
        "NIKKEI": MARKETS["japan"].index_symbol,
        "HSI": MARKETS["hongkong"].index_symbol,
        "NIFTY": MARKETS["india"].index_symbol,
        "ASX": MARKETS["australia"].index_symbol,
    })
    return result


def get_all_macro_symbols() -> list[str]:
    macros = set()
    for market in MARKETS.values():
        if market.index_symbol:
            macros.add(market.index_symbol)
        if market.currency_pair:
            macros.add(market.currency_pair)
        for sym in market.macro_symbols:
            macros.add(sym)
    macros.update(["^VIX", "CL=F", "GC=F"])
    return list(macros)


INITIAL_CAPITAL = {key: m.initial_capital for key, m in MARKETS.items()}

BIST_SYMBOLS = MARKETS["bist"].symbols
US_SYMBOLS = MARKETS["us"].symbols
UK_SYMBOLS = MARKETS["uk"].symbols
GOLD_SYMBOLS = MARKETS["gold"].special_symbols
INDEX_SYMBOLS = get_all_index_symbols()

DEFAULT_WATCHLIST = BIST_SYMBOLS[:6] + US_SYMBOLS[:4] + ["GC=F"]

VOLATILITY_LOOKBACK_DAYS = 60
BASE_POSITION_PCT = 0.10
MIN_POSITION_PCT = 0.03
MAX_POSITION_PCT = 0.15
CORRELATION_LOOKBACK_DAYS = 60
