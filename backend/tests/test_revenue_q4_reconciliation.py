"""Offline direct/derived revenue-Q4 reconciliation tests."""
from datetime import date
from decimal import Decimal
import inspect
import json
from pathlib import Path

import pytest

from app.models.outlook_q4 import DirectQ4Observation
from app.services.outlook_structured.revenue_q4_derivation import (
    derivation_input_from_certified_artifact, derive_revenue_q4,
)
from app.services.outlook_structured.revenue_q4_reconciliation import (
    adapt_direct_revenue_q4, reconcile_revenue_q4,
)


ARTIFACT = Path(__file__).parents[2] / "docs/diagnostics/phase6b5c2a5w10a-schema2-live-revenue-partition-certification-20261002.json"


@pytest.fixture(scope="module")
def derived_by_ticker():
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    return {ticker: derive_revenue_q4(derivation_input_from_certified_artifact(
        artifact, ticker=ticker, fiscal_year=year)).observation
        for ticker, year in (("AAPL", 2025), ("NVDA", 2026))}


def direct_for(derived, **changes):
    accession = derived.operand_provenance[0].accession
    ticker = "AAPL" if accession.startswith("0000320193") else "NVDA"
    data = dict(observation_id="synthetic-direct-q4", ticker=ticker,
        issuer=f"{ticker} synthetic issuer", cik=accession[:10], metric="revenue",
        fiscal_year=derived.fiscal_year, period_start=derived.period_start,
        period_end=derived.period_end, duration_days=derived.duration_days,
        original_value=derived.exact_decimal_value,
        normalized_value=derived.exact_decimal_value,
        original_concept="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        original_unit="USD", scale=0, currency="USD", share_basis="not_applicable",
        source_family="filing_xbrl", accession=accession, form="10-K",
        document_url="https://www.sec.gov/Archives/synthetic.htm",
        document_id="synthetic.htm", filing_date=derived.period_end,
        locator="xbrl-context:synthetic:fact:0", version_status="current",
        comparison_eligible=True)
    data.update(changes)
    return adapt_direct_revenue_q4(DirectQ4Observation(**data))


@pytest.mark.parametrize("ticker,expected", [("AAPL", Decimal("102466000000")),
    ("NVDA", Decimal("68127000000"))])
def test_certified_artifact_is_derived_only_without_claiming_direct_absence(
        derived_by_ticker, ticker, expected):
    derived = derived_by_ticker[ticker]
    result = reconcile_revenue_q4(direct=None, derived=derived)
    assert result.state == "available"
    assert result.authoritative_source_kind == "derived"
    assert result.authoritative_observation is derived
    assert result.authoritative_observation.exact_decimal_value == expected
    assert result.direct_observation is None


def test_neither_is_unavailable(derived_by_ticker):
    result = reconcile_revenue_q4()
    assert result.state == "unavailable"
    assert result.reasons == ("q4_evidence_unavailable",)


def test_direct_only_is_authoritative_and_preserves_provenance(derived_by_ticker):
    direct = direct_for(derived_by_ticker["AAPL"])
    result = reconcile_revenue_q4(direct=direct)
    assert result.state == "available" and result.authoritative_source_kind == "directly_reported"
    assert result.authoritative_observation is direct
    assert result.direct_observation.observation.accession == "0000320193-25-000079"
    assert result.direct_observation.qualification_policy == "direct-q4-1"


def test_exact_agreement_prefers_direct_and_retains_both_paths(derived_by_ticker):
    derived = derived_by_ticker["AAPL"]; direct = direct_for(derived)
    result = reconcile_revenue_q4(direct=direct, derived=derived)
    assert result.state == "available"
    assert result.authoritative_source_kind == "directly_reported"
    assert result.authoritative_observation is direct
    assert result.corroboration_state == "derived_exact_agreement"
    assert result.comparison_diagnostics.exact_value_agreement is True
    assert len(result.derived_observation.operand_provenance) == 4
    assert result.direct_observation.observation.document_id == "synthetic.htm"


def test_exact_disagreement_is_conflict_not_direct_precedence(derived_by_ticker):
    derived = derived_by_ticker["AAPL"]
    direct = direct_for(derived, normalized_value=derived.exact_decimal_value + 1,
        original_value=derived.exact_decimal_value + 1)
    result = reconcile_revenue_q4(direct=direct, derived=derived)
    assert result.state == "conflict" and result.authoritative_observation is None
    assert result.reasons == ("direct_derived_value_mismatch",)
    assert result.comparison_diagnostics.value_compared is True
    assert result.direct_observation is direct and result.derived_observation is derived


@pytest.mark.parametrize("changes,reason", [
    ({"period_start": date(2025, 6, 28), "duration_days": 92}, "period_mismatch"),
    ({"fiscal_year": 2024}, "fiscal_year_mismatch"),
    ({"canonical_unit": "USD-thousands"}, "unit_mismatch"),
    ({"currency": "EUR"}, "currency_mismatch"),
    ({"accounting_basis": "other"}, "accounting_basis_mismatch"),
    ({"reporting_scope": "other"}, "scope_mismatch"),
    ({"cik": "0000000000"}, "issuer_identity_mismatch"),
])
def test_compatibility_mismatch_prevents_value_comparison(derived_by_ticker, changes, reason):
    derived = derived_by_ticker["AAPL"]
    direct = direct_for(derived)
    direct_fields = type(direct).model_fields
    observation_fields = type(direct.observation).model_fields
    direct = direct.model_copy(update={key: value for key, value in changes.items()
        if key in direct_fields}) if any(key in direct_fields for key in changes) else direct
    observation_changes = {key: value for key, value in changes.items()
        if key in observation_fields}
    if observation_changes:
        direct = direct.model_copy(update={"observation": direct.observation.model_copy(
            update=observation_changes)})
    result = reconcile_revenue_q4(direct=direct, derived=derived)
    assert result.state == "conflict" and reason in result.reasons
    assert result.comparison_diagnostics.value_compared is False


def test_invalid_inputs_fail_closed(derived_by_ticker):
    derived = derived_by_ticker["AAPL"]; direct = direct_for(derived)
    invalid_direct = direct.model_copy(update={"qualification_state": "invalid"})
    assert reconcile_revenue_q4(direct=invalid_direct, derived=derived).reasons == ("direct_input_invalid",)
    invalid_derived = derived.model_copy(update={"derivation_state": "conflict"})
    assert reconcile_revenue_q4(direct=direct, derived=invalid_derived).reasons == ("derived_input_invalid",)


def test_rounded_direct_is_not_tolerance_matched(derived_by_ticker):
    derived = derived_by_ticker["AAPL"]
    rounded = direct_for(derived).model_copy(update={"precision_state": "rounded",
        "exact_decimal_value": Decimal("102466000000")})
    result = reconcile_revenue_q4(direct=rounded, derived=derived)
    assert result.state == "conflict"
    assert result.reasons == ("rounded_direct_value_unsupported",)
    assert result.comparison_diagnostics.value_compared is False


def test_source_kinds_survive(derived_by_ticker):
    derived = derived_by_ticker["AAPL"]; direct = direct_for(derived)
    assert reconcile_revenue_q4(derived=derived).authoritative_observation.source_kind == "derived"
    assert reconcile_revenue_q4(direct=direct).authoritative_observation.source_kind == "directly_reported"


def test_adapter_rejects_noncurrent_or_nonrevenue_direct(derived_by_ticker):
    derived = derived_by_ticker["AAPL"]
    observation = direct_for(derived).observation
    assert adapt_direct_revenue_q4(observation.model_copy(update={
        "version_status": "conflict", "comparison_eligible": False})) is None
    assert adapt_direct_revenue_q4(observation.model_copy(update={"metric": "diluted_eps",
        "share_basis": "diluted"})) is None


def test_reconciler_has_no_derivation_float_network_eps_or_direct_policy_path():
    import app.services.outlook_structured.revenue_q4_reconciliation as module
    source = inspect.getsource(module).lower()
    for forbidden in ("fy -", "q1", "q2", "q3", "float(", "requests", "httpx",
            "transport", "earningspershare", "diluted_eps", "qualify_direct_q4"):
        assert forbidden not in source
