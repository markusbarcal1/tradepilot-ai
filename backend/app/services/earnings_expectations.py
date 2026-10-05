"""Provider-neutral selection and deterministic earnings surprise calculation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from app.models.outlook_event import (EarningsMetricIdentity, EventMeasurement, EventSurprise, ExpectationDiagnostics,
    EventValue, ExpectationSnapshot, ExternalEvent)

ET = ZoneInfo("America/New_York")
REVENUE_RELATIVE_TOLERANCE = 0.005
EPS_RELATIVE_TOLERANCE = 0.005
EPS_ABSOLUTE_TOLERANCE = 0.01
UNIT_SCALE = {"USD": 1.0, "USD_thousand": 1e3, "USD_million": 1e6, "USD_billion": 1e9}


class ExpectationProvider(Protocol):
    """Acquisition boundary: normalized observations only, no interpretation."""
    def observations(self, ticker: str, reporting_identity, measurement_key: str) -> list[ExpectationSnapshot]: ...


@dataclass(frozen=True)
class SnapshotSelection:
    selected: ExpectationSnapshot | None
    expected_value: EventValue | None
    candidate_count: int
    compatible_count: int
    temporal_count: int
    rejection_reason: str | None
    release_at: datetime | None


def release_boundary(event: ExternalEvent) -> datetime | None:
    if event.announced_at:
        return event.announced_at.astimezone(timezone.utc)
    if not event.scheduled_date:
        return None
    if event.market_session == "before_market":
        local = datetime.combine(event.scheduled_date, time.min, ET)
    elif event.market_session == "after_market":
        local = datetime.combine(event.scheduled_date, time(16), ET)
    else:
        return None
    return local.astimezone(timezone.utc)


def _period(identity, ticker):
    if not identity or identity.status != "authoritative":
        return None
    rows = [row for row in identity.periods if row.ticker == ticker and row.fiscal_period != "FY"]
    return rows[0] if len(rows) == 1 else None


def _same_period(snapshot, event):
    left = _period(snapshot.reporting_identity, event.ticker)
    right = _period(event.reporting_identity, event.ticker)
    if not left or not right or (left.fiscal_year, left.fiscal_period) != (right.fiscal_year, right.fiscal_period):
        return False
    return not (left.period_end and right.period_end and left.period_end != right.period_end)


def _metric_compatible(actual: EarningsMetricIdentity | None,
                       expected: EarningsMetricIdentity | None) -> tuple[bool, str | None]:
    if not actual or not expected or actual.metric != expected.metric:
        return False, "metric_identity_mismatch"
    if actual.metric == "eps" and (actual.accounting_basis in ("unknown", "provider_defined")
            or expected.accounting_basis in ("unknown", "provider_defined")):
        return False, "accounting_basis_mismatch"
    if actual.accounting_basis != expected.accounting_basis:
        return False, "accounting_basis_mismatch"
    if actual.share_basis != expected.share_basis:
        return False, "share_basis_mismatch"
    if actual.scope == "unknown" or expected.scope == "unknown" or actual.scope != expected.scope:
        return False, "scope_mismatch"
    if actual.constant_currency != expected.constant_currency:
        return False, "scope_mismatch"
    return True, None


def _compatible_value(actual: EventValue, snapshot: ExpectationSnapshot) -> tuple[EventValue | None, str | None]:
    expected = snapshot.expected_value
    if not expected or actual.amount is None or expected.amount is None:
        return None, "value_unavailable"
    if snapshot.metric_identity and snapshot.metric_identity.metric == "revenue" and not snapshot.currency:
        return None, "currency_mismatch"
    if actual.unit == expected.unit:
        return expected, None
    if actual.unit in UNIT_SCALE and expected.unit in UNIT_SCALE and snapshot.currency == "USD":
        amount = expected.amount * UNIT_SCALE[expected.unit] / UNIT_SCALE[actual.unit]
        return EventValue(amount=amount, unit=actual.unit), None
    return None, "unit_mismatch"


def select_snapshot(event: ExternalEvent, measurement: EventMeasurement,
                    snapshots: list[ExpectationSnapshot]) -> SnapshotSelection:
    candidates = sorted(snapshots, key=lambda row: (
        row.captured_at or datetime.min.replace(tzinfo=timezone.utc), row.snapshot_id))
    if not candidates:
        return SnapshotSelection(None, None, 0, 0, 0, "no_expectation_snapshots", release_boundary(event))
    if not event.ticker or not _period(event.reporting_identity, event.ticker):
        return SnapshotSelection(None, None, len(candidates), 0, 0, "reporting_period_unresolved", release_boundary(event))
    period_rows = [row for row in candidates if row.ticker == event.ticker and _same_period(row, event)]
    if not period_rows:
        return SnapshotSelection(None, None, len(candidates), 0, 0, "reporting_period_mismatch", release_boundary(event))
    compatible = []
    last_reason = "metric_identity_mismatch"
    for row in period_rows:
        match, reason = _metric_compatible(measurement.metric_identity, row.metric_identity)
        if not match:
            last_reason = reason
            continue
        if measurement.currency != row.currency:
            last_reason = "currency_mismatch"
            continue
        expected, reason = _compatible_value(measurement.actual_value, row) if measurement.actual_value else (None, "value_unavailable")
        if expected is None:
            last_reason = reason
            continue
        compatible.append((row, expected))
    if not compatible:
        return SnapshotSelection(None, None, len(candidates), 0, 0, last_reason, release_boundary(event))
    cutoff = release_boundary(event)
    if cutoff is None:
        return SnapshotSelection(None, None, len(candidates), len(compatible), 0, "timestamp_unknown", None)
    valid = []
    for row, expected in compatible:
        timestamps = (row.captured_at, row.provider_as_of_at, row.provenance.published_at,
                      row.provenance.retrieved_at)
        if row.captured_at is None:
            continue
        known = [value for value in timestamps if value is not None]
        if all(value < cutoff for value in known):
            valid.append((row, expected))
    if not valid:
        missing_capture = any(row.captured_at is None for row, _ in compatible)
        return SnapshotSelection(None, None, len(candidates), len(compatible), 0,
            "timestamp_unknown" if missing_capture else "post_release_only", cutoff)
    selected, expected = valid[-1]
    return SnapshotSelection(selected, expected, len(candidates), len(compatible), len(valid), None, cutoff)


def calculate_surprise(actual: EventValue, expected: EventValue,
                       identity: EarningsMetricIdentity, snapshot_id: str) -> EventSurprise:
    if actual.amount is None or expected.amount is None or actual.unit != expected.unit:
        return EventSurprise(rejection_reason="value_unavailable")
    difference = round(actual.amount - expected.amount, 8)
    crosses_zero = (actual.amount < 0 < expected.amount) or (expected.amount < 0 < actual.amount)
    percent = None if abs(expected.amount) < 0.000001 or crosses_zero else round(
        difference / abs(expected.amount) * 100, 8)
    tolerance = (max(EPS_ABSOLUTE_TOLERANCE, abs(expected.amount) * EPS_RELATIVE_TOLERANCE)
                 if identity.metric == "eps" else abs(expected.amount) * REVENUE_RELATIVE_TOLERANCE)
    result = "approximately_in_line" if abs(difference) <= tolerance else "beat" if difference > 0 else "miss"
    status = "as_expected" if result == "approximately_in_line" else (
        "higher_than_expected" if result == "beat" else "lower_than_expected")
    return EventSurprise(status=status, difference=EventValue(amount=difference, unit=actual.unit),
        percent_difference=percent, expectation_snapshot_id=snapshot_id, comparison_result=result,
        origin="tradepilot_calculated", actual_value=actual, expected_value=expected,
        crosses_zero=crosses_zero)


def compare_measurement(event: ExternalEvent, measurement: EventMeasurement,
                        snapshots: list[ExpectationSnapshot]) -> tuple[EventMeasurement, SnapshotSelection]:
    selection = select_snapshot(event, measurement, snapshots)
    diagnostics = ExpectationDiagnostics(candidate_count=selection.candidate_count,
        compatible_count=selection.compatible_count, temporal_count=selection.temporal_count,
        selected_snapshot_id=selection.selected.snapshot_id if selection.selected else None,
        captured_at=selection.selected.captured_at if selection.selected else None,
        release_at=selection.release_at,
        compatibility_result="compatible" if selection.compatible_count else
            "unavailable" if selection.rejection_reason in ("no_expectation_snapshots", "timestamp_unknown") else "incompatible",
        rejection_reason=selection.rejection_reason,
        surprise_origin="tradepilot_calculated" if selection.selected else None)
    if not selection.selected or not selection.expected_value or not measurement.actual_value:
        return measurement.model_copy(update={"expectation_status": "unavailable",
            "surprise": EventSurprise(rejection_reason=selection.rejection_reason),
            "expectation_diagnostics": diagnostics}), selection
    surprise = calculate_surprise(measurement.actual_value, selection.expected_value,
                                   measurement.metric_identity, selection.selected.snapshot_id)
    snapshot = selection.selected.model_copy(update={"temporal_status": "pre_release_verified",
        "expected_value": selection.expected_value})
    return measurement.model_copy(update={"expectation": snapshot,
        "expectation_status": "available", "surprise": surprise,
        "expectation_diagnostics": diagnostics}), selection


def current_upcoming_snapshot(event: ExternalEvent, measurement: EventMeasurement,
                              snapshots: list[ExpectationSnapshot]) -> ExpectationSnapshot | None:
    """Newest compatible current benchmark; it carries no direction."""
    if event.status != "upcoming" or not event.ticker:
        return None
    compatible = []
    for row in snapshots:
        match, _ = _metric_compatible(measurement.metric_identity, row.metric_identity)
        if (row.ticker == event.ticker and _same_period(row, event) and match
                and row.currency == measurement.currency
                and row.captured_at and row.expected_value):
            compatible.append(row)
    return max(compatible, key=lambda row: (row.captured_at, row.snapshot_id), default=None)
