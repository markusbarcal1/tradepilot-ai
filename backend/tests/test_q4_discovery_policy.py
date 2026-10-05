"""Synthetic-only tests for the offline Phase 6B.5C.2A.5G prototype."""
import json

from app.services.outlook_structured.q4_discovery_policy import (
    DISCOVERY_COUNT_LIMIT, DISCOVERY_POLICY_VERSION, discover_q4_earnings_8k_prototype,
)


TEN_K = "0000000001-25-000100"


def row(**changes):
    value = {"accession": "0000000001-25-000050", "form": "8-K",
        "filing_date": "2025-02-02", "report_date": "2025-02-01",
        "items": "2.02,9.01", "primary_document": "earnings.htm"}
    value.update(changes)
    return value


def discover(*rows):
    annual = row(accession=TEN_K, form="10-K", filing_date="2025-02-20",
        report_date="2025-01-25", items="", primary_document="annual.htm")
    return discover_q4_earnings_8k_prototype((annual, *rows),
        period_end="2025-01-25", approved_ten_k_accession=TEN_K)


def test_report_date_mismatch_does_not_block_one_bounded_item_202_candidate():
    result = discover(row(report_date="2025-02-01"))
    assert result.state == "resolved" and len(result.candidates) == 1
    assert result.diagnostics["policy_version"] == DISCOVERY_POLICY_VERSION


def test_multiple_non_earnings_eight_ks_leave_no_candidate():
    result = discover(row(items="1.01"), row(accession="0000000001-25-000051", items="5.02"))
    assert (result.state, result.reason) == ("unavailable", "no_plausible_candidate")


def test_multiple_item_202_filings_fail_closed():
    result = discover(row(), row(accession="0000000001-25-000051", filing_date="2025-02-03"))
    assert result.state == "ambiguous" and len(result.candidates) == 2


def test_original_and_amendment_fail_closed_as_distinct_candidates():
    result = discover(row(), row(accession="0000000001-25-000051", form="8-K/A",
        filing_date="2025-02-04"))
    assert result.state == "ambiguous"


def test_missing_report_date_is_allowed_because_it_does_not_assign_the_period():
    assert discover(row(report_date="")).state == "resolved"


def test_missing_item_202_fails_qualification():
    assert discover(row(items="")).state == "unavailable"


def test_missing_filing_date_fails_qualification():
    assert discover(row(filing_date="")).state == "unavailable"


def test_unsafe_primary_document_fails_qualification():
    assert discover(row(primary_document="../earnings.htm")).state == "unavailable"


def test_candidate_after_approved_ten_k_is_outside_window():
    result = discover(row(filing_date="2025-02-21"))
    assert result.state == "unavailable"
    assert result.diagnostics["rows_rejected_after_approved_10k_boundary"] == 1


def test_candidate_on_or_before_period_end_is_outside_window():
    result = discover(row(filing_date="2025-01-25"))
    assert result.state == "unavailable"
    assert result.diagnostics["rows_rejected_at_or_before_period_end"] == 1


def test_candidate_on_approved_ten_k_date_is_allowed():
    assert discover(row(filing_date="2025-02-20")).state == "resolved"


def test_exact_duplicate_metadata_rows_collapse():
    candidate = row()
    result = discover(candidate, dict(candidate))
    assert result.state == "resolved" and len(result.candidates) == 1
    assert result.diagnostics["exact_duplicate_rows_collapsed"] == 1


def test_different_accessions_never_collapse():
    result = discover(row(), row(accession="0000000001-25-000051"))
    assert result.state == "ambiguous"
    assert result.diagnostics["exact_duplicate_rows_collapsed"] == 0


def test_no_plausible_candidate_fails_closed():
    assert discover().reason == "no_plausible_candidate"


def test_two_equally_plausible_candidates_are_not_ranked_arbitrarily():
    result = discover(row(), row(accession="0000000001-25-000051"))
    assert (result.state, result.reason) == ("ambiguous", "multiple_plausible_candidates")


def test_approved_10k_filing_boundary_must_be_uniquely_verified():
    result = discover_q4_earnings_8k_prototype((row(),), period_end="2025-01-25",
        approved_ten_k_accession=TEN_K)
    assert result.reason == "approved_10k_filing_date_unresolved"


def test_multiple_distinct_approved_10k_dates_fail_closed():
    annual_one = row(accession=TEN_K, form="10-K", filing_date="2025-02-20")
    annual_two = row(accession=TEN_K, form="10-K/A", filing_date="2025-02-21")
    result = discover_q4_earnings_8k_prototype((annual_one, annual_two, row()),
        period_end="2025-01-25", approved_ten_k_accession=TEN_K)
    assert result.state == "unavailable"
    assert result.diagnostics["distinct_approved_10k_filing_dates"] == 2


def test_invalid_approved_10k_date_fails_closed():
    annual = row(accession=TEN_K, form="10-K", filing_date="not-a-date")
    result = discover_q4_earnings_8k_prototype((annual, row()),
        period_end="2025-01-25", approved_ten_k_accession=TEN_K)
    assert result.state == "unavailable"
    assert result.diagnostics["invalid_or_missing_10k_filing_dates"] == 1


def test_unsafe_accession_is_rejected_before_primary_document():
    result = discover(row(accession="unsafe", primary_document="../also-unsafe.htm"))
    counts = result.diagnostics
    assert counts["rows_rejected_by_unsafe_or_missing_accession"] == 1
    assert counts["rows_rejected_by_unsafe_or_missing_primary_document"] == 0


def test_sequential_diagnostics_reconcile_first_failure_gates():
    rows = (row(form="10-Q"), row(filing_date=""), row(filing_date="2025-01-25"),
        row(filing_date="2025-02-21"), row(items="9.01"), row(accession="unsafe"),
        row(primary_document="../unsafe.htm"), row())
    result = discover(*rows)
    counts = result.diagnostics
    assert counts["count_semantics"] == "sequential_first_failure"
    assert counts["eight_k_rows_examined"] == 7
    assert counts["rows_rejected_by_missing_or_invalid_filing_date"] == 1
    assert counts["rows_rejected_at_or_before_period_end"] == 1
    assert counts["rows_rejected_after_approved_10k_boundary"] == 1
    assert counts["rows_inside_valid_filing_window"] == 4
    assert counts["rows_rejected_by_item_202"] == 1
    assert counts["rows_rejected_by_unsafe_or_missing_accession"] == 1
    assert counts["rows_rejected_by_unsafe_or_missing_primary_document"] == 1
    assert counts["distinct_qualifying_candidates"] == 1


def test_diagnostic_counters_saturate_without_retaining_rows():
    annual = row(accession=TEN_K, form="10-K", filing_date="2025-02-20")
    unrelated = [row(form="10-Q", accession=f"secret-{index}")
        for index in range(DISCOVERY_COUNT_LIMIT + 1)]
    result = discover_q4_earnings_8k_prototype((annual, *unrelated),
        period_end="2025-01-25", approved_ten_k_accession=TEN_K)
    assert result.diagnostics["counts_capped"] is True
    assert result.diagnostics["metadata_rows_examined"] == DISCOVERY_COUNT_LIMIT
    assert "secret-" not in json.dumps(result.diagnostics)


def test_diagnostics_contain_no_candidate_identity_or_secret_fields():
    result = discover(row())
    serialized = json.dumps(result.diagnostics)
    for forbidden in ("0000000001-25-000050", "earnings.htm", "2025-02-02",
            "2.02,9.01", "user-agent", "headers", "response_body"):
        assert forbidden not in serialized.lower()
