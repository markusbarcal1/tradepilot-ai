from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.paper_trading import PaperAccount, PaperPosition, PaperTrade


class PaperTradingRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_account_for_user(self, user_id: UUID):
        return self.session.scalar(select(PaperAccount).where(PaperAccount.user_id == user_id))

    def create_account(self, user_id: UUID, starting_cash: float):
        account = PaperAccount(user_id=user_id, cash_balance=starting_cash, starting_cash=starting_cash)
        self.session.add(account)
        self.session.flush()
        return account

    def list_positions_for_account(self, account_id: int):
        return list(self.session.scalars(select(PaperPosition).where(PaperPosition.account_id == account_id).order_by(PaperPosition.symbol)))

    def get_position(self, account_id: int, symbol: str):
        return self.session.scalar(select(PaperPosition).where(PaperPosition.account_id == account_id, PaperPosition.symbol == symbol))

    def create_position(self, account_id: int, symbol: str, shares: float, avg_cost: float):
        position = PaperPosition(account_id=account_id, symbol=symbol, shares=shares, avg_cost=avg_cost)
        self.session.add(position)
        self.session.flush()
        return position

    def update_position(self, position, *, shares: float, avg_cost=None):
        position.shares = shares
        if avg_cost is not None:
            position.avg_cost = avg_cost
        position.updated_at = func.current_timestamp()
        self.session.flush()
        self.session.refresh(position)
        return position

    def delete_position(self, position):
        self.session.delete(position)
        self.session.flush()

    def list_trades_for_account(self, account_id: int):
        return list(self.session.scalars(select(PaperTrade).where(PaperTrade.account_id == account_id).order_by(PaperTrade.created_at.desc(), PaperTrade.id.desc())))

    def get_trade(self, account_id: int, trade_id: int):
        return self.session.scalar(select(PaperTrade).where(PaperTrade.account_id == account_id, PaperTrade.id == trade_id))

    def create_trade(self, *, account_id: int, symbol: str, side: str, shares: float, price: float, total_value: float, realized_pnl: float):
        trade = PaperTrade(account_id=account_id, symbol=symbol, side=side, shares=shares, price=price, total_value=total_value, realized_pnl=realized_pnl)
        self.session.add(trade)
        self.session.flush()
        return trade

    def update_account_balance(self, account, cash_balance: float):
        account.cash_balance = cash_balance
        account.updated_at = func.current_timestamp()
        self.session.flush()
        self.session.refresh(account)
        return account
