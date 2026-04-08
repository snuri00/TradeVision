import json
from mcp.server.fastmcp import FastMCP

from trader.db import (
    init_db, get_db, get_watchlist, add_to_watchlist, remove_from_watchlist,
    get_trade_history, save_news_article, save_market_data, get_local_positions,
)
from trader.config import MARKETS, detect_market, get_all_index_symbols
from trader.data.bist import get_bist_stocks, get_bist100_index, get_stock_history as bist_history
from trader.data.us_uk import get_stock_quote, get_index_data, get_stock_history as us_uk_history
from trader.data.gold import get_gold_price, get_gold_history
from trader.data.news import fetch_all_news, fetch_article_text, fetch_bist_news, fetch_gold_news
from trader.analysis.technical import analyze_stock
from trader.analysis.signals import scan_watchlist_signals
from trader.analysis.fundamental import get_fundamentals, score_fundamentals
from trader.analysis.volatility import calculate_volatility_metrics, calculate_volatility_position_size
from trader.analysis.correlation import calculate_correlation_matrix, get_correlation_risk
from trader.trading.executor import execute_trade
from trader.trading.portfolio import get_portfolio_status
from trader.reports.performance import get_performance_report
from trader.config import VOLATILITY_LOOKBACK_DAYS, BASE_POSITION_PCT, MIN_POSITION_PCT, MAX_POSITION_PCT

mcp = FastMCP("trader", instructions="AI-Powered Trading Analysis System")
init_db()


@mcp.tool()
def get_market_overview() -> str:
    """BIST XU100, S&P 500, FTSE 100, Gold, USD/TRY snapshot - piyasa genel görünümü"""
    bist = get_bist100_index()
    sp500 = get_index_data("SP500")
    ftse = get_index_data("FTSE100")
    usdtry = get_index_data("USDTRY")
    gold = get_gold_price(period="5d")

    return json.dumps({
        "BIST100": bist,
        "SP500": sp500,
        "FTSE100": ftse,
        "USDTRY": usdtry,
        "gold": gold,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def get_stock_data(symbol: str, period: str = "1mo", interval: str = "1d") -> str:
    """Herhangi bir sembol için OHLCV verisi çeker. Örnek: THYAO.IS, AAPL, VOD.L, GC=F, 7203.T, SIE.DE"""
    market = detect_market(symbol)
    market_config = MARKETS[market]

    if market_config.suffix:
        symbol = market_config.normalize_symbol(symbol)

    if market == "bist":
        history = bist_history(symbol, period=period)
    else:
        history = us_uk_history(symbol, period=period, interval=interval)

    quote = get_stock_quote(symbol) if market != "bist" else None

    return json.dumps({
        "symbol": symbol,
        "market": market,
        "currency": market_config.currency,
        "quote": quote,
        "history": history[-10:],
        "total_bars": len(history),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def get_bist_stocks_data(symbols: str = "") -> str:
    """BIST hisselerini toplu çeker. symbols: virgülle ayrılmış (boş bırakılırsa default liste)"""
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else None
    data = get_bist_stocks(sym_list)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def get_gold_price_data(period: str = "1mo") -> str:
    """Altın fiyat verisi: futures (GC=F), ETF (GLD), spot (XAU/USD)"""
    prices = get_gold_price(period=period)
    history = get_gold_history(period=period)
    return json.dumps({
        "current": prices,
        "history_last_5": history[-5:] if history else [],
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def analyze_technical(symbol: str, period: str = "3mo") -> str:
    """Teknik analiz: RSI, MACD, SMA, Bollinger Bands hesaplar ve sinyalleri listeler"""
    result = analyze_stock(symbol, period=period)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def scan_signals(symbols: str = "") -> str:
    """Watchlist veya verilen sembollerde al/sat sinyali tarar"""
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else None
    result = scan_watchlist_signals(sym_list)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def fetch_news(query: str = "", max_results: int = 15) -> str:
    """Google News + MarketAux'dan haber çeker. query: arama terimi (boş=genel haberler)"""
    articles = fetch_all_news(query if query else None, max_results=max_results)

    with get_db() as conn:
        for a in articles:
            save_news_article(
                conn, a["title"], a.get("source", ""), a["url"],
                a.get("published_at", ""), a.get("category"),
            )

    return json.dumps(articles, indent=2, ensure_ascii=False)


@mcp.tool()
def fetch_article_text_tool(url: str) -> str:
    """Haber makalesinin tam metnini çeker ve döndürür"""
    text = fetch_article_text(url)
    return json.dumps({"url": url, "text": text}, indent=2, ensure_ascii=False)


@mcp.tool()
def get_news_summary(category: str = "general") -> str:
    """Son haberlerin yapılandırılmış özeti. category: general, bist, gold, geopolitical"""
    if category == "bist":
        articles = fetch_bist_news()
    elif category == "gold":
        articles = fetch_gold_news()
    elif category == "geopolitical":
        from trader.data.news import fetch_geopolitical_news
        articles = fetch_geopolitical_news()
    else:
        articles = fetch_all_news(max_results=15)

    return json.dumps({
        "category": category,
        "count": len(articles),
        "articles": articles,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def get_portfolio_status_tool() -> str:
    """Tüm pozisyonlar ve P&L birleşik görünüm - tüm pazarlar"""
    status = get_portfolio_status()
    return json.dumps(status, indent=2, default=str, ensure_ascii=False)


@mcp.tool()
def paper_trade(symbol: str, side: str, quantity: float,
                market: str = "", price: float = 0) -> str:
    """Sanal alım/satım - tüm pazarlar. symbol: THYAO.IS/AAPL/VOD.L/GC=F/BTC-USD/7203.T/SIE.DE, side: buy/sell, market: boş bırakılırsa otomatik tespit"""
    detected_market = market if market else None
    result = execute_trade(symbol, side, quantity,
                            price if price > 0 else None,
                            market=detected_market)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def paper_trade_bist(symbol: str, side: str, quantity: float, price: float = 0) -> str:
    """BIST sanal alım/satım. symbol: THYAO.IS, side: buy/sell, quantity: adet, price: 0=güncel fiyat"""
    return paper_trade(symbol, side, quantity, market="bist", price=price)


@mcp.tool()
def paper_trade_us(symbol: str, side: str, quantity: float, price: float = 0) -> str:
    """ABD hisse sanal alım/satım. symbol: AAPL, TSLA, side: buy/sell, quantity: adet"""
    return paper_trade(symbol, side, quantity, market="us", price=price)


@mcp.tool()
def paper_trade_uk(symbol: str, side: str, quantity: float, price: float = 0) -> str:
    """UK hisse sanal alım/satım. symbol: VOD.L, BP.L, side: buy/sell, quantity: adet"""
    return paper_trade(symbol, side, quantity, market="uk", price=price)


@mcp.tool()
def paper_trade_gold(side: str, quantity: float, symbol: str = "GC=F", price: float = 0) -> str:
    """Altın sanal alım/satım. side: buy/sell, quantity: ons, price: 0=güncel fiyat"""
    return paper_trade(symbol, side, quantity, market="gold", price=price)


@mcp.tool()
def get_available_markets() -> str:
    """Desteklenen tüm pazarları, sembollerini ve para birimlerini listeler"""
    result = {}
    for key, m in MARKETS.items():
        result[key] = {
            "name": m.name,
            "currency": m.currency,
            "suffix": m.suffix,
            "symbol_count": len(m.symbols),
            "symbols": m.symbols,
            "index": m.index_symbol,
            "initial_capital": m.initial_capital,
        }
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def get_performance_report_tool(period: str = "daily") -> str:
    """Performans raporu. period: daily, weekly, monthly"""
    report = get_performance_report(period)
    return json.dumps(report, indent=2, default=str, ensure_ascii=False)


@mcp.tool()
def get_trade_history_tool(symbol: str = "", market: str = "", limit: int = 50) -> str:
    """İşlem geçmişi. Filtre: symbol, market (bist/us/uk/gold/germany/japan/crypto...), limit"""
    with get_db() as conn:
        trades = get_trade_history(
            conn,
            symbol=symbol if symbol else None,
            market=market if market else None,
            limit=limit,
        )
    return json.dumps(trades, indent=2, ensure_ascii=False)


@mcp.tool()
def get_watchlist_tool() -> str:
    """Takip listesini görüntüler"""
    with get_db() as conn:
        wl = get_watchlist(conn)
    return json.dumps(wl, indent=2, ensure_ascii=False)


@mcp.tool()
def update_watchlist(symbol: str, action: str = "add", market: str = "") -> str:
    """Watchlist'e sembol ekle/çıkar. action: add/remove, market: boş bırakılırsa otomatik tespit"""
    with get_db() as conn:
        if action == "add":
            resolved_market = market if market else detect_market(symbol)
            add_to_watchlist(conn, symbol, resolved_market)
            return json.dumps({"status": "added", "symbol": symbol, "market": resolved_market})
        elif action == "remove":
            remove_from_watchlist(conn, symbol)
            return json.dumps({"status": "removed", "symbol": symbol})
        else:
            return json.dumps({"error": f"Unknown action: {action}"})


@mcp.tool()
def analyze_fundamentals(symbol: str) -> str:
    """Temel analiz: P/E, P/B, ROE, D/E, marjlar, büyüme oranları ve genel skor"""
    fundamentals = get_fundamentals(symbol)
    score_result = score_fundamentals(fundamentals)
    return json.dumps({
        "fundamentals": fundamentals,
        "scoring": score_result,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def analyze_volatility(symbol: str, period: str = "3mo") -> str:
    """Volatilite analizi: günlük/yıllık volatilite, yüzdelik dilim ve önerilen pozisyon büyüklüğü"""
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period)
    if df.empty:
        return json.dumps({"symbol": symbol, "error": "No data available"})

    metrics = calculate_volatility_metrics(df, VOLATILITY_LOOKBACK_DAYS)
    suggested_size = calculate_volatility_position_size(
        metrics.get("annualized_volatility", 0.30),
        BASE_POSITION_PCT, MIN_POSITION_PCT, MAX_POSITION_PCT,
    )

    return json.dumps({
        "symbol": symbol,
        "metrics": metrics,
        "suggested_position_pct": round(suggested_size * 100, 1),
        "interpretation": (
            "low" if metrics.get("annualized_volatility", 0) < 0.15
            else "medium" if metrics.get("annualized_volatility", 0) < 0.30
            else "high" if metrics.get("annualized_volatility", 0) < 0.50
            else "extreme"
        ),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def analyze_correlation(symbol: str, compare_with: str = "") -> str:
    """Korelasyon analizi: sembolün portföy veya belirtilen sembollerle korelasyonu. compare_with: virgülle ayrılmış"""
    import yfinance as yf

    if compare_with:
        other_symbols = [s.strip() for s in compare_with.split(",") if s.strip()]
    else:
        with get_db() as conn:
            positions = get_local_positions(conn)
            other_symbols = [p["symbol"] for p in positions if p["symbol"] != symbol]

    if not other_symbols:
        return json.dumps({
            "symbol": symbol,
            "message": "No symbols to compare with. Use compare_with parameter or have positions in portfolio.",
        })

    all_symbols = list(set([symbol] + other_symbols))
    price_data = {}
    for sym in all_symbols:
        ticker = yf.Ticker(sym)
        df = ticker.history(period="3mo")
        if not df.empty:
            price_data[sym] = df

    risk = get_correlation_risk(symbol, other_symbols, price_data)

    corr_matrix = calculate_correlation_matrix(price_data)
    matrix_dict = {}
    if not corr_matrix.empty:
        matrix_dict = {
            col: {row: round(float(corr_matrix.loc[row, col]), 3)
                  for row in corr_matrix.index}
            for col in corr_matrix.columns
        }

    return json.dumps({
        "symbol": symbol,
        "risk_assessment": risk,
        "correlation_matrix": matrix_dict,
    }, indent=2, ensure_ascii=False)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
