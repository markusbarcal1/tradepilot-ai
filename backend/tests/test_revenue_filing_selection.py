from datetime import date, timedelta
import json
from pathlib import Path

import pytest

from app.models.outlook_revenue_filing_selection import (
    RevenueFilingQuarterAnchor, RevenueFilingSelectionRequest,
    SecSubmissionFilingRow, SecSubmissionsSelectionInput,
)
from app.services.outlook_structured.revenue_filing_selection import (
    POLICY_VERSION, select_revenue_operand_filings,
)


CIK = "0000001234"


def row(role, end, *, ordinal=0, form=None, accession=None, document=None, **changes):
    forms = {"FY": "10-K", "Q1": "10-Q", "Q2": "10-Q", "Q3": "10-Q"}
    values = dict(accession=accession or f"{CIK}-25-{ordinal + 1:06d}",
        form=form or forms[role], filing_date=end + timedelta(days=30),
        acceptance_time=None, report_period_end=end,
        primary_document=document or f"issuer-{role.lower()}.htm", source_ordinal=ordinal)
    values.update(changes)
    return SecSubmissionFilingRow(**values)


def fixture(*, q1=date(2025, 3, 31), step=91, annual_step=91, cik=CIK, issuer="Issuer"):
    ends = [q1, q1 + timedelta(days=step), q1 + timedelta(days=step * 2)]
    request = RevenueFilingSelectionRequest(ticker="TEST", issuer=issuer, cik=cik,
        target_fiscal_year=2025, quarter_anchors=tuple(
            RevenueFilingQuarterAnchor(role=role, report_period_end=end)
            for role, end in zip(("Q1", "Q2", "Q3"), ends)))
    rows = tuple(row(role, end, ordinal=index) for index, (role, end) in enumerate(
        zip(("Q1", "Q2", "Q3", "FY"), (*ends, ends[-1] + timedelta(days=annual_step)))))
    metadata = SecSubmissionsSelectionInput(issuer=issuer, cik=cik,
        source_identity="offline-submissions-fixture", rows=rows)
    return request, metadata


def replace_input(metadata, rows=None, **changes):
    values = metadata.model_dump()
    values.update(changes)
    if rows is not None:
        values["rows"] = rows
    return SecSubmissionsSelectionInput(**values)


def assert_reason(request, metadata, state, reason):
    result = select_revenue_operand_filings(request, metadata)
    assert (result.state, result.reason, result.selected_filings) == (state, reason, ())


@pytest.mark.parametrize(("label", "q1", "step", "annual_step"), [
    ("A calendar", date(2025, 3, 31), 91, 92),
    ("B non-calendar", date(2024, 12, 28), 91, 91),
    ("C 52-week", date(2025, 3, 29), 91, 91),
    ("D 53-week", date(2025, 4, 5), 91, 98),
])
def test_supported_fiscal_geometries(label, q1, step, annual_step):
    request, metadata = fixture(q1=q1, step=step, annual_step=annual_step)
    result = select_revenue_operand_filings(request, metadata)
    assert result.state == "selected", label
    assert result.reason is None
    assert [item.role for item in result.selected_filings] == ["FY", "Q1", "Q2", "Q3"]
    assert all(item.document.selector_policy == POLICY_VERSION for item in result.selected_filings)


def test_e_missing_q2():
    request, metadata = fixture()
    assert_reason(request, replace_input(metadata, metadata.rows[:1] + metadata.rows[2:]),
        "unavailable", "quarter_filing_missing")


def test_f_duplicate_q2_candidate():
    request, metadata = fixture()
    duplicate = metadata.rows[1].model_copy(update={"accession": f"{CIK}-25-000099"})
    assert_reason(request, replace_input(metadata, (*metadata.rows, duplicate)),
        "ambiguous", "multiple_quarter_candidates")


def test_g_missing_annual():
    request, metadata = fixture()
    assert_reason(request, replace_input(metadata, metadata.rows[:3]),
        "unavailable", "annual_filing_missing")


def test_h_multiple_annual_candidates():
    request, metadata = fixture()
    duplicate = metadata.rows[3].model_copy(update={"accession": f"{CIK}-25-000099"})
    assert_reason(request, replace_input(metadata, (*metadata.rows, duplicate)),
        "ambiguous", "multiple_annual_candidates")


@pytest.mark.parametrize(("role", "form"), [("Q2", "10-Q/A"), ("FY", "10-K/A")])
def test_i_j_original_plus_amendment_is_ambiguous(role, form):
    request, metadata = fixture()
    original = next(value for value in metadata.rows if value.primary_document == f"issuer-{role.lower()}.htm")
    amendment = original.model_copy(update={"accession": f"{CIK}-25-000099", "form": form,
        "primary_document": f"issuer-{role.lower()}a.htm", "source_ordinal": 9})
    assert_reason(request, replace_input(metadata, (*metadata.rows, amendment)),
        "ambiguous", "amendment_ambiguous")


def test_k_amendment_only_is_ambiguous():
    request, metadata = fixture()
    rows = tuple(value.model_copy(update={"form": "10-Q/A"}) if index == 1 else value
        for index, value in enumerate(metadata.rows))
    assert_reason(request, replace_input(metadata, rows), "ambiguous", "amendment_ambiguous")


def test_l_missing_report_date():
    request, metadata = fixture()
    rows = (metadata.rows[0].model_copy(update={"report_period_end": None}), *metadata.rows[1:])
    assert_reason(request, replace_input(metadata, rows), "unavailable", "report_period_missing")


@pytest.mark.parametrize(("document", "state", "reason"), [
    (None, "unavailable", "primary_document_missing"),
    ("bad document.htm", "conflict", "primary_document_invalid"),
    ("../escape.htm", "conflict", "primary_document_invalid"),
    ("https://evil.example/a.htm", "conflict", "primary_document_invalid"),
])
def test_m_n_primary_document_safety(document, state, reason):
    request, metadata = fixture()
    rows = (metadata.rows[0].model_copy(update={"primary_document": document}), *metadata.rows[1:])
    assert_reason(request, replace_input(metadata, rows), state, reason)


def test_o_wrong_form_for_role():
    request, metadata = fixture()
    rows = (metadata.rows[0].model_copy(update={"form": "8-K"}), *metadata.rows[1:])
    assert_reason(request, replace_input(metadata, rows), "unavailable", "quarter_filing_missing")


def test_p_quarter_outside_annual_boundary():
    request, metadata = fixture(annual_step=106)
    assert_reason(request, metadata, "unavailable", "annual_filing_missing")


def test_q_reversed_quarter_order():
    request, metadata = fixture()
    anchors = list(request.quarter_anchors)
    request = request.model_copy(update={"quarter_anchors": (anchors[1], anchors[0], anchors[2])})
    # Roles retain their dates; reverse the actual Q1/Q2 period identities.
    request = request.model_copy(update={"quarter_anchors": (
        anchors[0].model_copy(update={"report_period_end": anchors[1].report_period_end}),
        anchors[1].model_copy(update={"report_period_end": anchors[0].report_period_end}), anchors[2])})
    assert_reason(request, metadata, "conflict", "quarter_order_invalid")


def test_r_issuer_mismatch():
    request, metadata = fixture()
    assert_reason(request, replace_input(metadata, issuer="Different Issuer"),
        "conflict", "issuer_mismatch")


def test_s_exact_duplicate_collapses_and_preserves_provenance():
    request, metadata = fixture()
    duplicate = metadata.rows[1].model_copy(update={"source_ordinal": 99})
    result = select_revenue_operand_filings(request, replace_input(metadata, (*metadata.rows, duplicate)))
    assert result.state == "selected"
    q2 = next(item for item in result.selected_filings if item.role == "Q2")
    assert q2.metadata_provenance.source_ordinals == (1, 99)


def test_t_u_multiple_years_do_not_change_explicit_target_selection():
    request, metadata = fixture()
    older = tuple(value.model_copy(update={
        "accession": f"{CIK}-24-{index + 1:06d}",
        "filing_date": value.filing_date - timedelta(days=364),
        "report_period_end": value.report_period_end - timedelta(days=364),
        "source_ordinal": index + 10,
    }) for index, value in enumerate(metadata.rows))
    result = select_revenue_operand_filings(request, replace_input(metadata, (*metadata.rows, *older)))
    assert result.state == "selected"
    assert {item.document.accession for item in result.selected_filings} == {
        value.accession for value in metadata.rows}


def test_retained_aapl_nvda_metadata_reproduces_frozen_manifest():
    artifact_path = Path(__file__).parents[2] / "docs" / "diagnostics" / \
        "phase6b5c2a5w2-inline-revenue-metadata-20261001.json"
    roles = json.loads(artifact_path.read_text(encoding="utf-8"))["manifest"]["roles"]
    for ticker, target_year in (("AAPL", 2025), ("NVDA", 2026)):
        expected = [value for value in roles if value["ticker"] == ticker]
        by_role = {value["expected_role"]: value for value in expected}
        request = RevenueFilingSelectionRequest(ticker=ticker, issuer=expected[0]["issuer"],
            cik=expected[0]["cik"], target_fiscal_year=target_year,
            quarter_anchors=tuple(RevenueFilingQuarterAnchor(role=role,
                report_period_end=date.fromisoformat(by_role[role]["report_period_end"]))
                for role in ("Q1", "Q2", "Q3")))
        rows = tuple(SecSubmissionFilingRow(accession=value["accession"], form=value["form"],
            filing_date=date.fromisoformat(value["filing_date"]),
            acceptance_time=value["acceptance_time"],
            report_period_end=date.fromisoformat(value["report_period_end"]),
            primary_document=value["primary_document"], source_ordinal=index)
            for index, value in enumerate(expected))
        source = SecSubmissionsSelectionInput(issuer=expected[0]["issuer"], cik=expected[0]["cik"],
            source_identity=str(artifact_path.relative_to(Path(__file__).parents[2])), rows=rows)
        result = select_revenue_operand_filings(request, source)
        assert result.state == "selected"
        actual = {item.role: item.document for item in result.selected_filings}
        for role, frozen in by_role.items():
            assert (actual[role].accession, actual[role].form, actual[role].filing_date.isoformat(),
                actual[role].report_period_end.isoformat(), actual[role].primary_document) == (
                frozen["accession"], frozen["form"], frozen["filing_date"],
                frozen["report_period_end"], frozen["primary_document"])
