from pathlib import Path
from datetime import datetime, timezone
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.market_data import get_price_history


STARTING_CASH = 10_000.0
DB_PATH = Path(__file__).resolve().parent / "paper_trading.db"

router = APIRouter(prefix="/paper", tags=["paper trading"])


class PaperTradeRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    shares: float = Field(..., gt=0)
    price: float = Field(..., gt=0)


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def init_paper_trading_db():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_account (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_balance REAL NOT NULL,
                starting_cash REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                shares REAL NOT NULL,
                avg_cost REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                shares REAL NOT NULL,
                price REAL NOT NULL,
                total_value REAL NOT NULL,
                realized_pnl REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        account = connection.execute(
            "SELECT id FROM paper_account ORDER BY id LIMIT 1"
        ).fetchone()
        if account is None:
            connection.execute(
                """
                INSERT INTO paper_account (cash_balance, starting_cash)
                VALUES (?, ?)
                """,
                (STARTING_CASH, STARTING_CASH),
            )


def normalize_symbol(symbol: str):
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status_code=400, detail="Symbol is required")
    return normalized


def get_default_account(connection):
    account = connection.execute(
        "SELECT * FROM paper_account ORDER BY id LIMIT 1"
    ).fetchone()
    if account is None:
        raise HTTPException(status_code=500, detail="Paper account is not initialized")
    return account


def get_position(connection, symbol: str):
    return connection.execute(
        "SELECT * FROM paper_positions WHERE symbol = ?",
        (symbol,),
    ).fetchone()


def get_trade(connection, trade_id: int):
    return connection.execute(
        "SELECT * FROM paper_trades WHERE id = ?",
        (trade_id,),
    ).fetchone()


def round_money(value):
    return round(float(value), 2)


def round_percent(value):
    return round(float(value), 2)


def calculate_percent(numerator, denominator):
    if abs(denominator) <= 1e-9:
        return 0
    return (numerator / denominator) * 100


def get_position_market_prices(symbol: str):
    try:
        history = get_price_history(symbol, "5d", "1d")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch current market price for {symbol}",
        ) from exc

    closes = history["Close"].dropna()
    if closes.empty:
        raise HTTPException(
            status_code=400,
            detail=f"No closing price data found for {symbol}",
        )

    current_price = float(closes.iloc[-1])
    previous_close = float(closes.iloc[-2]) if len(closes) > 1 else None

    return current_price, previous_close


def parse_sqlite_timestamp(value: str):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def is_opened_today(created_at: str):
    opened_at = parse_sqlite_timestamp(created_at)
    if opened_at is None:
        return False

    return opened_at.date() == datetime.now(timezone.utc).date()


@router.get("/account")
def read_account():
    with get_connection() as connection:
        return row_to_dict(get_default_account(connection))


@router.get("/positions")
def read_positions():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM paper_positions ORDER BY symbol"
        ).fetchall()
        return [row_to_dict(row) for row in rows]


@router.get("/trades")
def read_trades():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM paper_trades ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [row_to_dict(row) for row in rows]


@router.get("/portfolio")
def read_portfolio():
    with get_connection() as connection:
        account = get_default_account(connection)
        rows = connection.execute(
            "SELECT * FROM paper_positions ORDER BY symbol"
        ).fetchall()

    cash_balance = float(account["cash_balance"])
    starting_cash = float(account["starting_cash"])
    positions = []
    market_value = 0.0
    cost_basis = 0.0
    open_pnl = 0.0
    day_change = 0.0
    day_reference_value = 0.0

    for row in rows:
        symbol = row["symbol"]
        shares = float(row["shares"])
        avg_cost = float(row["avg_cost"])
        current_price, previous_close = get_position_market_prices(symbol)

        position_market_value = shares * current_price
        position_cost_basis = shares * avg_cost
        unrealized_pnl = position_market_value - position_cost_basis
        unrealized_pnl_percent = calculate_percent(
            unrealized_pnl,
            position_cost_basis,
        )
        day_reference_price = (
            avg_cost
            if is_opened_today(row["created_at"])
            else previous_close or avg_cost
        )
        position_day_change = (current_price - day_reference_price) * shares
        position_day_reference_value = day_reference_price * shares

        market_value += position_market_value
        cost_basis += position_cost_basis
        open_pnl += unrealized_pnl
        day_change += position_day_change
        day_reference_value += position_day_reference_value

        positions.append(
            {
                "symbol": symbol,
                "shares": shares,
                "avg_cost": round_money(avg_cost),
                "current_price": round_money(current_price),
                "market_value": round_money(position_market_value),
                "unrealized_pnl": round_money(unrealized_pnl),
                "unrealized_pnl_percent": round_percent(unrealized_pnl_percent),
            }
        )

    account_equity = cash_balance + market_value

    return {
        "cash_balance": round_money(cash_balance),
        "starting_cash": round_money(starting_cash),
        "positions_count": len(positions),
        "positions": positions,
        "market_value": round_money(market_value),
        "account_equity": round_money(account_equity),
        "open_pnl": round_money(open_pnl),
        "open_pnl_percent": round_percent(calculate_percent(open_pnl, cost_basis)),
        "day_change": round_money(day_change),
        "day_change_percent": round_percent(
            calculate_percent(day_change, day_reference_value)
        ),
    }


@router.post("/buy")
def buy(request: PaperTradeRequest):
    symbol = normalize_symbol(request.symbol)
    shares = request.shares
    price = request.price
    total_value = shares * price

    with get_connection() as connection:
        account = get_default_account(connection)
        cash_balance = account["cash_balance"]

        if total_value > cash_balance:
            raise HTTPException(
                status_code=400,
                detail="Insufficient cash balance for this paper trade",
            )

        position = get_position(connection, symbol)
        if position is None:
            connection.execute(
                """
                INSERT INTO paper_positions (symbol, shares, avg_cost)
                VALUES (?, ?, ?)
                """,
                (symbol, shares, price),
            )
        else:
            current_shares = position["shares"]
            current_cost_basis = current_shares * position["avg_cost"]
            new_shares = current_shares + shares
            new_avg_cost = (current_cost_basis + total_value) / new_shares
            connection.execute(
                """
                UPDATE paper_positions
                SET shares = ?, avg_cost = ?, updated_at = CURRENT_TIMESTAMP
                WHERE symbol = ?
                """,
                (new_shares, new_avg_cost, symbol),
            )

        connection.execute(
            """
            UPDATE paper_account
            SET cash_balance = cash_balance - ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (total_value, account["id"]),
        )
        cursor = connection.execute(
            """
            INSERT INTO paper_trades
                (symbol, side, shares, price, total_value, realized_pnl)
            VALUES (?, 'BUY', ?, ?, ?, 0)
            """,
            (symbol, shares, price, total_value),
        )

        updated_account = get_default_account(connection)
        updated_position = get_position(connection, symbol)
        trade = get_trade(connection, cursor.lastrowid)

    return {
        "message": "Paper buy executed",
        "account": row_to_dict(updated_account),
        "position": row_to_dict(updated_position),
        "trade": row_to_dict(trade),
    }


@router.post("/sell")
def sell(request: PaperTradeRequest):
    symbol = normalize_symbol(request.symbol)
    shares = request.shares
    price = request.price
    total_value = shares * price

    with get_connection() as connection:
        account = get_default_account(connection)
        position = get_position(connection, symbol)

        if position is None or position["shares"] < shares:
            raise HTTPException(
                status_code=400,
                detail="Not enough shares available for this paper trade",
            )

        remaining_shares = position["shares"] - shares
        realized_pnl = (price - position["avg_cost"]) * shares

        if remaining_shares <= 1e-9:
            connection.execute(
                "DELETE FROM paper_positions WHERE symbol = ?",
                (symbol,),
            )
            updated_position = None
        else:
            connection.execute(
                """
                UPDATE paper_positions
                SET shares = ?, updated_at = CURRENT_TIMESTAMP
                WHERE symbol = ?
                """,
                (remaining_shares, symbol),
            )
            updated_position = get_position(connection, symbol)

        connection.execute(
            """
            UPDATE paper_account
            SET cash_balance = cash_balance + ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (total_value, account["id"]),
        )
        cursor = connection.execute(
            """
            INSERT INTO paper_trades
                (symbol, side, shares, price, total_value, realized_pnl)
            VALUES (?, 'SELL', ?, ?, ?, ?)
            """,
            (symbol, shares, price, total_value, realized_pnl),
        )

        updated_account = get_default_account(connection)
        trade = get_trade(connection, cursor.lastrowid)

    return {
        "message": "Paper sell executed",
        "account": row_to_dict(updated_account),
        "position": row_to_dict(updated_position),
        "trade": row_to_dict(trade),
    }
