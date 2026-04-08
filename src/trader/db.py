import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from trader.config import DB_PATH, DATA_DIR, INITIAL_CAPITAL, DEFAULT_WATCHLIST, MARKETS, detect_market


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol TEXT PRIMARY KEY,
                market TEXT NOT NULL,
                added_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(symbol, date)
            );

            CREATE TABLE IF NOT EXISTS news_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source TEXT,
                url TEXT UNIQUE,
                published_at TEXT,
                full_text TEXT,
                category TEXT,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                total_value REAL NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS local_positions (
                symbol TEXT PRIMARY KEY,
                market TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                avg_cost REAL NOT NULL DEFAULT 0,
                current_price REAL,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS performance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                period_type TEXT NOT NULL,
                market TEXT,
                total_value REAL,
                total_pnl REAL,
                pnl_pct REAL,
                win_rate REAL,
                max_drawdown REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS capital (
                market TEXT PRIMARY KEY,
                initial_amount REAL NOT NULL,
                current_cash REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)

        for market_key, market_config in MARKETS.items():
            conn.execute(
                "INSERT OR IGNORE INTO capital (market, initial_amount, current_cash) VALUES (?, ?, ?)",
                (market_key, market_config.initial_capital, market_config.initial_capital),
            )

        for symbol in DEFAULT_WATCHLIST:
            market = detect_market(symbol)
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (symbol, market) VALUES (?, ?)",
                (symbol, market),
            )


def save_market_data(conn: sqlite3.Connection, symbol: str, rows: list[dict]):
    for row in rows:
        conn.execute(
            """INSERT OR REPLACE INTO market_data (symbol, date, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (symbol, row["date"], row["open"], row["high"], row["low"], row["close"], row["volume"]),
        )


def save_news_article(conn: sqlite3.Connection, title: str, source: str, url: str,
                       published_at: str, category: str = None, full_text: str = None):
    conn.execute(
        """INSERT OR IGNORE INTO news_articles (title, source, url, published_at, category, full_text)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, source, url, published_at, category, full_text),
    )


def get_watchlist(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT symbol, market, added_at FROM watchlist ORDER BY market, symbol").fetchall()
    return [dict(r) for r in rows]


def add_to_watchlist(conn: sqlite3.Connection, symbol: str, market: str):
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (symbol, market) VALUES (?, ?)",
        (symbol, market),
    )


def remove_from_watchlist(conn: sqlite3.Connection, symbol: str):
    conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))


def record_trade(conn: sqlite3.Connection, symbol: str, market: str, side: str,
                  quantity: float, price: float) -> dict:
    total_value = quantity * price
    conn.execute(
        """INSERT INTO paper_trades (symbol, market, side, quantity, price, total_value)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (symbol, market, side, quantity, price, total_value),
    )

    position = conn.execute(
        "SELECT * FROM local_positions WHERE symbol = ?", (symbol,)
    ).fetchone()

    if side == "buy":
        if position:
            old_qty = position["quantity"]
            old_cost = position["avg_cost"]
            new_qty = old_qty + quantity
            new_avg = ((old_qty * old_cost) + (quantity * price)) / new_qty
            conn.execute(
                """UPDATE local_positions SET quantity=?, avg_cost=?, current_price=?, last_updated=datetime('now')
                   WHERE symbol=?""",
                (new_qty, new_avg, price, symbol),
            )
        else:
            conn.execute(
                """INSERT INTO local_positions (symbol, market, quantity, avg_cost, current_price, last_updated)
                   VALUES (?, ?, ?, ?, ?, datetime('now'))""",
                (symbol, market, quantity, price, price),
            )

        conn.execute(
            "UPDATE capital SET current_cash = current_cash - ? WHERE market = ?",
            (total_value, market),
        )
    elif side == "sell":
        if not position or position["quantity"] < quantity:
            raise ValueError(f"Insufficient position for {symbol}: have {position['quantity'] if position else 0}, want to sell {quantity}")
        new_qty = position["quantity"] - quantity
        if new_qty == 0:
            conn.execute("DELETE FROM local_positions WHERE symbol = ?", (symbol,))
        else:
            conn.execute(
                """UPDATE local_positions SET quantity=?, current_price=?, last_updated=datetime('now')
                   WHERE symbol=?""",
                (new_qty, price, symbol),
            )
        conn.execute(
            "UPDATE capital SET current_cash = current_cash + ? WHERE market = ?",
            (total_value, market),
        )

    return {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "total_value": total_value,
    }


def get_local_positions(conn: sqlite3.Connection, market: str = None) -> list[dict]:
    if market:
        rows = conn.execute(
            "SELECT * FROM local_positions WHERE market = ? AND quantity > 0", (market,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM local_positions WHERE quantity > 0"
        ).fetchall()
    return [dict(r) for r in rows]


def get_capital(conn: sqlite3.Connection, market: str) -> dict:
    row = conn.execute("SELECT * FROM capital WHERE market = ?", (market,)).fetchone()
    return dict(row) if row else {}


def get_trade_history(conn: sqlite3.Connection, symbol: str = None, market: str = None,
                       limit: int = 50) -> list[dict]:
    query = "SELECT * FROM paper_trades WHERE 1=1"
    params: list[Any] = []
    if symbol:
        query += " AND symbol = ?"
        params.append(symbol)
    if market:
        query += " AND market = ?"
        params.append(market)
    query += " ORDER BY executed_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def save_performance_snapshot(conn: sqlite3.Connection, snapshot_date: str, period_type: str,
                               market: str, total_value: float, total_pnl: float,
                               pnl_pct: float, win_rate: float = None, max_drawdown: float = None):
    conn.execute(
        """INSERT INTO performance_snapshots
           (snapshot_date, period_type, market, total_value, total_pnl, pnl_pct, win_rate, max_drawdown)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (snapshot_date, period_type, market, total_value, total_pnl, pnl_pct, win_rate, max_drawdown),
    )
