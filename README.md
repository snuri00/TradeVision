# TradeVision

AI-powered multi-market trading analysis system with 12 global markets, technical/fundamental/correlation analysis, and paper trading via MCP integration.

## Markets

| Market | Currency | Symbols | Index |
|--------|----------|---------|-------|
| BIST (Turkey) | TRY | 16 stocks | XU100 |
| US | USD | 10 stocks | S&P 500 |
| UK | GBP | 10 stocks | FTSE 100 |
| Germany | EUR | 10 stocks | DAX |
| France | EUR | 10 stocks | CAC 40 |
| Japan | JPY | 10 stocks | Nikkei 225 |
| Hong Kong | HKD | 10 stocks | Hang Seng |
| India | INR | 10 stocks | NIFTY 50 |
| Australia | AUD | 10 stocks | ASX 200 |
| Gold | USD | 3 instruments | - |
| Commodities | USD | 5 instruments | - |
| Crypto | USD | 10 coins | - |

Adding a new market is a single config entry - no code changes needed.

## Features

### Analysis
- **Technical Analysis** - RSI, MACD, SMA/EMA, Bollinger Bands, ADX, Volume
- **Fundamental Analysis** - P/E, P/B, ROE, D/E, margins, growth rates with scoring
- **Volatility Analysis** - 60-day rolling volatility, annualized, position sizing recommendations
- **Correlation Analysis** - Cross-asset correlation matrix, portfolio concentration risk detection
- **Signal Scanner** - Watchlist scanning with combined technical + fundamental signals

### Trading
- **Paper Trading** - All markets with local SQLite tracking
- **Alpaca Integration** - US market paper trading via Alpaca API
- **Position Management** - Per-market capital, positions, P&L tracking
- **Risk Management** - Stop loss, trailing stop, cooldown periods, exposure limits

### Backtesting
- **3-Agent System** - TraderAgent (technical) + NewsAnalystAgent (macro) + FundamentalAgent
- **Volatility-Based Sizing** - Dynamic position sizing based on stock volatility
- **Correlation-Adjusted** - Position size reduced for highly correlated holdings
- **Signal Blending** - 50% technical + 30% macro + 20% fundamental weighted scoring

### MCP Integration
18 tools exposed to Claude via Model Context Protocol:
- Market data, technical analysis, fundamental analysis
- Volatility and correlation analysis
- Paper trading across all markets
- Portfolio status, trade history, performance reports
- News aggregation (Google News + MarketAux)

## Setup

### Requirements
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
git clone https://github.com/snuri00/TradeVision.git
cd TradeVision
uv sync
```

### Environment Variables

Create a `.env` file:

```env
# Optional - for enhanced data
FINNHUB_API_KEY=your_key
MARKETAUX_API_KEY=your_key

# Optional - for US paper trading via Alpaca
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2
```

No API keys are required - the system works with yfinance (free) by default.

## Usage

### MCP Server (Claude Integration)

```bash
uv run trader-mcp
```

Add to your MCP config:

```json
{
  "mcpServers": {
    "tradevision": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/TradeVision", "trader-mcp"]
    }
  }
}
```

### CLI Commands

```bash
# Collect market data
uv run trader-collect-data

# Collect news
uv run trader-collect-news

# Daily performance snapshot
uv run trader-daily-report

# Run backtest
uv run python -m scripts.run_backtest
```

### Backtest Example

```python
from trader.backtest.engine import BacktestEngine

engine = BacktestEngine(
    symbols=["AAPL", "MSFT", "NVDA", "THYAO.IS", "7203.T", "BTC-USD"],
    start_date="2025-01-01",
    end_date="2025-12-31",
    initial_capital=100_000.0,
)
results = engine.run()
```

## Adding a New Market

Add a single entry to `MARKETS` in `src/trader/config.py`:

```python
MARKETS["switzerland"] = MarketConfig(
    name="Switzerland",
    currency="CHF",
    suffix=".SW",
    initial_capital=100_000.0,
    symbols=["NESN.SW", "NOVN.SW", "ROG.SW"],
    index_symbol="^SSMI",
    currency_pair="USDCHF=X",
)
```

That's it. All systems (trading, analysis, backtesting, MCP tools, portfolio tracking) pick it up automatically.

## Architecture

```
src/trader/
├── config.py              # Market registry & configuration
├── db.py                  # SQLite database layer
├── mcp_server/server.py   # 18 MCP tools for Claude
├── analysis/
│   ├── technical.py       # RSI, MACD, SMA, BB, ADX
│   ├── fundamental.py     # P/E, ROE, margins scoring
│   ├── volatility.py      # Vol metrics & position sizing
│   ├── correlation.py     # Correlation matrix & risk
│   └── signals.py         # Watchlist signal scanner
├── trading/
│   ├── executor.py        # Trade execution (generic)
│   ├── portfolio.py       # Portfolio status
│   └── alpaca_client.py   # Alpaca API integration
├── backtest/
│   ├── engine.py          # Backtest orchestrator
│   ├── agents.py          # Trader, Analyst, Fundamental, Portfolio Manager
│   └── data_feeder.py     # Historical data provider
├── data/
│   ├── bist.py            # BIST data fetcher
│   ├── us_uk.py           # US/UK data fetcher
│   ├── gold.py            # Gold data fetcher
│   └── news.py            # News aggregation
└── reports/
    └── performance.py     # Performance metrics
```

## License

MIT
