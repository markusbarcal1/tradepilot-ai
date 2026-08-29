from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.paper_trading import PaperAccount, PaperPosition, PaperTrade


class PaperTradingRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_default_account(self):
        return self.session.scalars(
            select(PaperAccount).order_by(PaperAccount.id).limit(1)
        ).first()

    def create_account(self, starting_cash: float):
        account = PaperAccount(
            cash_balance=starting_cash,
            starting_cash=starting_cash,
        )
        self.session.add(account)
        self.session.flush()
        return account

    def list_positions(self):
        return list(
            self.session.scalars(select(PaperPosition).order_by(PaperPosition.symbol))
        )

    def get_position(self, symbol: str):
        return self.session.scalar(
            select(PaperPosition).where(PaperPosition.symbol == symbol)
        )

    def create_position(self, symbol: str, shares: float, avg_cost: float):
        position = PaperPosition(symbol=symbol, shares=shares, avg_cost=avg_cost)
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

    def list_trades(self):
        return list(
            self.session.scalars(
                select(PaperTrade).order_by(
                    PaperTrade.created_at.desc(), PaperTrade.id.desc()
                )
            )
        )

    def get_trade(self, trade_id: int):
        return self.session.get(PaperTrade, trade_id)

    def create_trade(
        self,
        *,
        symbol: str,
        side: str,
        shares: float,
        price: float,
        total_value: float,
        realized_pnl: float,
    ):
        trade = PaperTrade(
            symbol=symbol,
            side=side,
            shares=shares,
            price=price,
            total_value=total_value,
            realized_pnl=realized_pnl,
        )
        self.session.add(trade)
        self.session.flush()
        return trade

    def update_account_balance(self, account, cash_balance: float):
        account.cash_balance = cash_balance
        account.updated_at = func.current_timestamp()
        self.session.flush()
        self.session.refresh(account)
        return account
