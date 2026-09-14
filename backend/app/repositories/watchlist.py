from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.user import WatchlistItem


class WatchlistRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_symbols(self, user_id: UUID):
        return list(self.session.scalars(select(WatchlistItem.symbol).where(WatchlistItem.user_id == user_id).order_by(WatchlistItem.symbol)))

    def add(self, user_id: UUID, symbol: str):
        existing = self.session.get(WatchlistItem, (user_id, symbol))
        if existing is not None:
            return existing
        item = WatchlistItem(user_id=user_id, symbol=symbol)
        self.session.add(item)
        self.session.flush()
        return item

    def remove(self, user_id: UUID, symbol: str):
        result = self.session.execute(delete(WatchlistItem).where(WatchlistItem.user_id == user_id, WatchlistItem.symbol == symbol))
        self.session.flush()
        return result.rowcount > 0
