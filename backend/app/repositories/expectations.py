"""Append-only persistence for global market expectation observations."""
from __future__ import annotations

from hashlib import sha256
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.expectation import PersistedExpectationSnapshot
from app.models.outlook_event import EventSource, EventValue, ExpectationSnapshot
from app.models.outlook_reporting import ReportingIdentity


def _iso(value):
    return value.isoformat() if value else None


def _period(snapshot: ExpectationSnapshot):
    identity = snapshot.reporting_identity
    if not identity or identity.status != "authoritative":
        raise ValueError("Expectation persistence requires authoritative reporting identity")
    periods = [row for row in identity.periods if row.ticker == snapshot.ticker and row.fiscal_period != "FY"]
    if len(periods) != 1:
        raise ValueError("Expectation persistence requires one ticker quarter")
    return periods[0]


def observation_fingerprint(snapshot: ExpectationSnapshot) -> str:
    """Deduplicate the same provider observation without rewriting history."""
    period = _period(snapshot)
    payload = {
        "ticker": snapshot.ticker,
        "period": period.model_dump(mode="json"),
        "metric": snapshot.metric_identity.model_dump(mode="json") if snapshot.metric_identity else None,
        "expected": snapshot.expected_value.model_dump(mode="json") if snapshot.expected_value else None,
        "low": snapshot.low_estimate.model_dump(mode="json") if snapshot.low_estimate else None,
        "high": snapshot.high_estimate.model_dump(mode="json") if snapshot.high_estimate else None,
        "currency": snapshot.currency,
        "analyst_count": snapshot.analyst_count,
        "provider": snapshot.provider,
        "provider_as_of_at": _iso(snapshot.provider_as_of_at),
        "source_published_at": _iso(snapshot.provenance.published_at),
        "source_url": str(snapshot.provenance.source_url),
        "origin": snapshot.origin,
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ExpectationRepository:
    """Shared market data: no user ID and no user-specific copies."""
    def __init__(self, session: Session):
        self.session = session

    def persist(self, snapshot: ExpectationSnapshot) -> tuple[ExpectationSnapshot, bool]:
        if not (snapshot.ticker and snapshot.metric_identity and snapshot.expected_value
                and snapshot.expected_value.amount is not None and snapshot.captured_at
                and snapshot.provider):
            raise ValueError("Incomplete normalized expectation snapshot")
        if snapshot.provenance.retrieved_at > snapshot.captured_at:
            raise ValueError("Capture cannot precede provider retrieval")
        period = _period(snapshot)
        fingerprint = observation_fingerprint(snapshot)
        duplicate = self.session.scalar(select(PersistedExpectationSnapshot).where(
            PersistedExpectationSnapshot.observation_fingerprint == fingerprint))
        if duplicate:
            return self._snapshot(duplicate), False
        if self.session.get(PersistedExpectationSnapshot, snapshot.snapshot_id):
            raise ValueError("Snapshot ID is immutable and already exists")
        row = PersistedExpectationSnapshot(
            snapshot_id=snapshot.snapshot_id, observation_fingerprint=fingerprint,
            event_id=snapshot.event_id, ticker=snapshot.ticker, fiscal_year=period.fiscal_year,
            fiscal_period=period.fiscal_period, period_end=period.period_end.isoformat() if period.period_end else None,
            metric_key=snapshot.measurement_key or snapshot.metric_identity.metric,
            expected_amount=snapshot.expected_value.amount, unit=snapshot.expected_value.unit,
            currency=snapshot.currency, analyst_count=snapshot.analyst_count,
            low_amount=snapshot.low_estimate.amount if snapshot.low_estimate else None,
            high_amount=snapshot.high_estimate.amount if snapshot.high_estimate else None,
            captured_at=_iso(snapshot.captured_at), provider_as_of_at=_iso(snapshot.provider_as_of_at),
            expires_at=_iso(snapshot.expires_at), provider=snapshot.provider,
            temporal_status=snapshot.temporal_status, origin=snapshot.origin,
            reporting_identity=snapshot.reporting_identity.model_dump(mode="json"),
            metric_identity=snapshot.metric_identity.model_dump(mode="json"),
            provenance=snapshot.provenance.model_dump(mode="json"),
        )
        self.session.add(row)
        self.session.flush()
        return snapshot, True

    def history(self, ticker: str, reporting_identity: ReportingIdentity,
                measurement_key: str) -> list[ExpectationSnapshot]:
        periods = [row for row in reporting_identity.periods
                   if row.ticker == ticker.upper() and row.fiscal_period != "FY"]
        if len(periods) != 1:
            return []
        period = periods[0]
        rows = self.session.scalars(select(PersistedExpectationSnapshot).where(
            PersistedExpectationSnapshot.ticker == ticker.upper(),
            PersistedExpectationSnapshot.fiscal_year == period.fiscal_year,
            PersistedExpectationSnapshot.fiscal_period == period.fiscal_period,
            PersistedExpectationSnapshot.metric_key == measurement_key,
        ).order_by(PersistedExpectationSnapshot.captured_at,
                   PersistedExpectationSnapshot.snapshot_id)).all()
        return [self._snapshot(row) for row in rows]

    def newest(self, ticker: str, reporting_identity: ReportingIdentity,
               measurement_key: str) -> ExpectationSnapshot | None:
        rows = self.history(ticker, reporting_identity, measurement_key)
        return rows[-1] if rows else None

    def newest_pre_release(self, ticker: str, reporting_identity: ReportingIdentity,
                           measurement_key: str, release_at) -> ExpectationSnapshot | None:
        """Newest capture strictly before release; compatibility remains engine-owned."""
        rows = [row for row in self.history(ticker, reporting_identity, measurement_key)
                if row.captured_at and row.captured_at < release_at
                and (row.provider_as_of_at is None or row.provider_as_of_at < release_at)
                and (row.provenance.published_at is None or row.provenance.published_at < release_at)]
        return rows[-1] if rows else None

    @staticmethod
    def _snapshot(row: PersistedExpectationSnapshot) -> ExpectationSnapshot:
        low = EventValue(amount=row.low_amount, unit=row.unit) if row.low_amount is not None else None
        high = EventValue(amount=row.high_amount, unit=row.unit) if row.high_amount is not None else None
        return ExpectationSnapshot(
            snapshot_id=row.snapshot_id, event_id=row.event_id, basis="structured_consensus",
            metric="actual_value", measurement_key=row.metric_key, ticker=row.ticker,
            reporting_identity=row.reporting_identity, metric_identity=row.metric_identity,
            reference_period=f"FY{row.fiscal_year} {row.fiscal_period}",
            expected_value=EventValue(amount=row.expected_amount, unit=row.unit),
            low_estimate=low, high_estimate=high, currency=row.currency,
            analyst_count=row.analyst_count, captured_at=row.captured_at,
            provider_as_of_at=row.provider_as_of_at, expires_at=row.expires_at,
            provider=row.provider, temporal_status=row.temporal_status, origin=row.origin,
            provenance=EventSource.model_validate(row.provenance),
        )


class RepositoryExpectationProvider:
    """Provider-neutral read adapter; acquisition and persistence stay separate."""
    def __init__(self, repository: ExpectationRepository):
        self.repository = repository

    def observations(self, ticker: str, reporting_identity: ReportingIdentity | None,
                     measurement_key: str) -> list[ExpectationSnapshot]:
        if reporting_identity is None:
            return []
        return self.repository.history(ticker, reporting_identity, measurement_key)
