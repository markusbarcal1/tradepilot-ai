"""Global, append-only market expectation persistence models."""
from sqlalchemy import JSON, Float, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PersistedExpectationSnapshot(Base):
    __tablename__ = "expectation_snapshots"
    __table_args__ = (
        UniqueConstraint("observation_fingerprint", name="uq_expectation_snapshots_fingerprint"),
        Index("ix_expectation_snapshots_lookup", "ticker", "fiscal_year", "fiscal_period", "metric_key", "captured_at"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    observation_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[str] = mapped_column(Text, nullable=False)
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(Text, nullable=False)
    period_end: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_key: Mapped[str] = mapped_column(Text, nullable=False)
    expected_amount: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyst_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    low_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[str] = mapped_column(Text, nullable=False)
    provider_as_of_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    temporal_status: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    reporting_identity: Mapped[dict] = mapped_column(JSON, nullable=False)
    metric_identity: Mapped[dict] = mapped_column(JSON, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False)
