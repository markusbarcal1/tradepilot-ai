from uuid import UUID

from sqlalchemy import Float, ForeignKey, Index, Integer, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_paper_accounts_user_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    cash_balance: Mapped[float] = mapped_column(Float, nullable=False)
    starting_cash: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("account_id", "symbol", name="uq_paper_positions_account_symbol"),
        Index("ix_paper_positions_account_id", "account_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    __table_args__ = (
        Index("ix_paper_trades_account_created_at", "account_id", "created_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    side: Mapped[str] = mapped_column(Text, nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0")
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
