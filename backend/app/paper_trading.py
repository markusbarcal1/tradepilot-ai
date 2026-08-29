from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import inspect

from app.bootstrap import (
    DEFAULT_DEV_USER_DISPLAY_NAME,
    DEFAULT_DEV_USER_EMAIL,
    DEFAULT_DEV_USER_ID,
)
from app.db import create_schema, engine, session_scope
from app.repositories.paper_trading import PaperTradingRepository
from app.repositories.users import UserRepository
from app.services.market_data import get_price_history


STARTING_CASH = 10_000.0
router = APIRouter(prefix="/paper", tags=["paper trading"])


class PaperTradeRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    shares: float = Field(..., gt=0)
    price: float = Field(..., gt=0)


def account_to_dict(account):
    if account is None:
        return None
    return {
        "id": account.id,
        "cash_balance": account.cash_balance,
        "starting_cash": account.starting_cash,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def position_to_dict(position):
    if position is None:
        return None
    return {
        "id": position.id,
        "symbol": position.symbol,
        "shares": position.shares,
        "avg_cost": position.avg_cost,
        "created_at": position.created_at,
        "updated_at": position.updated_at,
    }


def trade_to_dict(trade):
    if trade is None:
        return None
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "shares": trade.shares,
        "price": trade.price,
        "total_value": trade.total_value,
        "realized_pnl": trade.realized_pnl,
        "created_at": trade.created_at,
    }


def init_paper_trading_db(database_engine=None, session_factory=None):
    database_engine = database_engine or engine
    tables = set(inspect(database_engine).get_table_names())
    if "paper_account" in tables:
        raise RuntimeError(
            "The paper-trading database is at the Phase 1B schema. "
            "Back it up, stamp 20260828_01, and run Alembic upgrade head."
        )
    # Compatibility bootstrap is limited to genuinely empty local/test databases.
    if not tables:
        create_schema(database_engine)
    with session_scope(session_factory) as session:
        users = UserRepository(session)
        repository = PaperTradingRepository(session)
        if users.get(DEFAULT_DEV_USER_ID) is None:
            users.create(
                DEFAULT_DEV_USER_ID,
                email=DEFAULT_DEV_USER_EMAIL,
                display_name=DEFAULT_DEV_USER_DISPLAY_NAME,
            )
        if repository.get_account_for_user(DEFAULT_DEV_USER_ID) is None:
            repository.create_account(DEFAULT_DEV_USER_ID, STARTING_CASH)


def normalize_symbol(symbol: str):
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status_code=400, detail="Symbol is required")
    return normalized


def require_bootstrap_account(repository):
    account = repository.get_account_for_user(DEFAULT_DEV_USER_ID)
    if account is None:
        raise HTTPException(status_code=500, detail="Paper account is not initialized")
    return account


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
    with session_scope() as session:
        return account_to_dict(require_bootstrap_account(PaperTradingRepository(session)))


@router.get("/positions")
def read_positions():
    with session_scope() as session:
        repository = PaperTradingRepository(session)
        account = require_bootstrap_account(repository)
        positions = repository.list_positions_for_account(account.id)
        return [position_to_dict(position) for position in positions]


@router.get("/trades")
def read_trades():
    with session_scope() as session:
        repository = PaperTradingRepository(session)
        account = require_bootstrap_account(repository)
        trades = repository.list_trades_for_account(account.id)
        return [
            {
                "id": trade.id,
                "timestamp": trade.created_at,
                "created_at": trade.created_at,
                "symbol": trade.symbol,
                "side": trade.side,
                "shares": trade.shares,
                "price": trade.price,
                "total_value": trade.total_value,
            }
            for trade in trades
        ]


@router.get("/portfolio")
def read_portfolio():
    with session_scope() as session:
        repository = PaperTradingRepository(session)
        account_row = require_bootstrap_account(repository)
        account = account_to_dict(account_row)
        position_rows = [
            position_to_dict(item)
            for item in repository.list_positions_for_account(account_row.id)
        ]

    cash_balance = float(account["cash_balance"])
    starting_balance = float(account["starting_cash"])
    positions = []
    market_value = 0.0
    day_change = 0.0
    day_reference_value = 0.0

    for row in position_rows:
        symbol = row["symbol"]
        shares = float(row["shares"])
        avg_cost = float(row["avg_cost"])
        current_price, previous_close = get_position_market_prices(symbol)
        position_market_value = shares * current_price
        position_cost_basis = shares * avg_cost
        unrealized_pnl = position_market_value - position_cost_basis
        unrealized_pnl_percent = calculate_percent(unrealized_pnl, position_cost_basis)
        day_reference_price = (
            avg_cost if is_opened_today(row["created_at"]) else previous_close or avg_cost
        )
        position_day_change = (current_price - day_reference_price) * shares
        position_day_reference_value = day_reference_price * shares

        market_value += position_market_value
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
    total_pl = account_equity - starting_balance
    total_pl_percent = calculate_percent(total_pl, starting_balance)
    return {
        "cash": round_money(cash_balance),
        "cash_balance": round_money(cash_balance),
        "starting_balance": round_money(starting_balance),
        "starting_cash": round_money(starting_balance),
        "positions_count": len(positions),
        "positions": positions,
        "market_value": round_money(market_value),
        "account_equity": round_money(account_equity),
        "total_pl": round_money(total_pl),
        "total_pl_percent": round_percent(total_pl_percent),
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
    with session_scope() as session:
        repository = PaperTradingRepository(session)
        account = require_bootstrap_account(repository)
        if total_value > account.cash_balance:
            raise HTTPException(
                status_code=400, detail="Insufficient cash balance for this paper trade"
            )

        position = repository.get_position(account.id, symbol)
        if position is None:
            position = repository.create_position(account.id, symbol, shares, price)
        else:
            current_cost_basis = position.shares * position.avg_cost
            new_shares = position.shares + shares
            new_avg_cost = (current_cost_basis + total_value) / new_shares
            position = repository.update_position(
                position, shares=new_shares, avg_cost=new_avg_cost
            )

        repository.update_account_balance(account, account.cash_balance - total_value)
        trade = repository.create_trade(
            account_id=account.id,
            symbol=symbol,
            side="BUY",
            shares=shares,
            price=price,
            total_value=total_value,
            realized_pnl=0,
        )
        return {
            "message": "Paper buy executed",
            "account": account_to_dict(account),
            "position": position_to_dict(position),
            "trade": trade_to_dict(trade),
        }


@router.post("/sell")
def sell(request: PaperTradeRequest):
    symbol = normalize_symbol(request.symbol)
    shares = request.shares
    price = request.price
    total_value = shares * price
    with session_scope() as session:
        repository = PaperTradingRepository(session)
        account = require_bootstrap_account(repository)
        position = repository.get_position(account.id, symbol)
        if position is None or position.shares < shares:
            raise HTTPException(
                status_code=400,
                detail="Not enough shares available for this paper trade",
            )

        remaining_shares = position.shares - shares
        realized_pnl = (price - position.avg_cost) * shares
        if remaining_shares <= 1e-9:
            repository.delete_position(position)
            updated_position = None
        else:
            updated_position = repository.update_position(position, shares=remaining_shares)

        repository.update_account_balance(account, account.cash_balance + total_value)
        trade = repository.create_trade(
            account_id=account.id,
            symbol=symbol,
            side="SELL",
            shares=shares,
            price=price,
            total_value=total_value,
            realized_pnl=realized_pnl,
        )
        return {
            "message": "Paper sell executed",
            "account": account_to_dict(account),
            "position": position_to_dict(updated_position),
            "trade": trade_to_dict(trade),
        }
