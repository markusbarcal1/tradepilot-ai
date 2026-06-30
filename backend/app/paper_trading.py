from pathlib import Path
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


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
