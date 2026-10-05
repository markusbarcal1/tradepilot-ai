"""Offline characterization of bounded fiscal-anchor diagnostic metadata."""
from datetime import date
import json

import pytest

from app.models.outlook_inline_revenue import SelectedFilingDocument
from app.services.outlook_structured import inline_revenue_operand as module


DEI = "http://xbrl.sec.gov/dei/2025"
VALUES = {"DocumentFiscalYearFocus": "2025", "DocumentFiscalPeriodFocus": "Q1",
    "DocumentPeriodEndDate": "2025-03-31", "DocumentType": "10-Q"}


def document(**changes):
    values = dict(ticker="TEST", issuer="Test Issuer", cik="0001045810",
        target_fiscal_year=2025, expected_role="Q1", accession="0001045810-25-000001",
        form="10-Q", filing_date=date(2025, 4, 1), report_period_end=date(2025, 3, 31),
        primary_document="report.htm",
        source_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581025000001/report.htm",
        selector_policy="diagnostic-fixture-1")
    values.update(changes); return SelectedFilingDocument(**values)


def fact(name, value, *, prefix="dei", attrs="", wrapper=""):
    value = f'<ix:nonNumeric name="{prefix}:{name}" {attrs}>{value}</ix:nonNumeric>'
    return f"<{wrapper}>{value}</{wrapper}>" if wrapper else value


def payload(*, replacements=None, extras="", unrelated=""):
    replacements = replacements or {}
    anchors = "".join(replacements.get(name, fact(name, value, attrs='contextRef="ctx"'))
        for name, value in VALUES.items())
    return f'''<html xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:dei="{DEI}"
      xmlns:old="http://xbrl.sec.gov/dei/2024"
      xmlns:us-gaap="http://fasb.org/us-gaap/2025"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
      xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"><body>
      BEFORE SURROUNDING PROSE {anchors}{extras}{unrelated} AFTER SURROUNDING PROSE
      <xbrli:context id="ctx"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0001045810</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
      <ix:nonFraction name="us-gaap:Revenues" contextRef="ctx" unitRef="usd" decimals="INF">1000</ix:nonFraction>
      </body></html>'''.encode()


def qualify(*, selected=None, **changes):
    return module.qualify_inline_revenue_operand(selected or document(), payload(**changes))


def anchors(result):
    return {row.required_local_name: row for row in result.fiscal_anchor_diagnostic.anchors}


def test_valid_set_reports_four_anchor_valid_entries_and_safe_observations():
    result = qualify(); diagnostic = result.fiscal_anchor_diagnostic
    assert result.state == "qualified" and diagnostic.diagnostic_identity == "inline-revenue-fiscal-anchor-diagnostic-2"
    assert diagnostic.schema_version == "2" and len(diagnostic.anchors) == 4
    assert all(row.qualification_branch == "anchor_valid" and row.comparison == "match"
        for row in diagnostic.anchors)


@pytest.mark.parametrize("name,different", [
    ("DocumentFiscalYearFocus", "2024"), ("DocumentFiscalPeriodFocus", "q1"),
    ("DocumentPeriodEndDate", "03/31/2025"), ("DocumentType", "10-q"),
])
def test_raw_duplicate_conflict_has_exact_diagnostic_branch_without_changing_public_reason(name, different):
    result = qualify(extras=fact(name, different))
    row = anchors(result)[name]
    assert result.state == "conflict" and result.failure_reasons == ("fiscal_anchor_conflict",)
    assert row.qualification_branch == "duplicate_distinct" and row.comparison == "not_comparable"
    assert row.distinct_stripped_raw_value_count == 2


@pytest.mark.parametrize("name,value,branch", [
    ("DocumentFiscalYearFocus", "bad", "fiscal_year_parse_invalid"),
    ("DocumentFiscalPeriodFocus", "H1", "fiscal_period_parse_invalid"),
    ("DocumentPeriodEndDate", "March 31, 2025", "period_end_parse_invalid"),
    ("DocumentType", "FORM 10-Q", "document_type_parse_invalid"),
])
def test_parse_invalid_branches(name, value, branch):
    result = qualify(replacements={name: fact(name, value)})
    row = anchors(result)[name]
    assert result.failure_reasons == ("fiscal_anchor_conflict",)
    assert row.qualification_branch == branch and row.comparison == "not_comparable"
    assert row.observations[0].semantic_outcome == "parse_invalid"


@pytest.mark.parametrize("name,selected,branch", [
    ("DocumentFiscalYearFocus", document(target_fiscal_year=2024), "year_mismatch"),
    ("DocumentFiscalPeriodFocus", document(expected_role="Q2", report_period_end=date(2025, 3, 31)), "role_mismatch"),
    ("DocumentPeriodEndDate", document(report_period_end=date(2025, 3, 30)), "period_end_mismatch"),
    ("DocumentType", document(form="10-K"), "form_mismatch"),
])
def test_frozen_identity_mismatch_branches(name, selected, branch):
    result = qualify(selected=selected); row = anchors(result)[name]
    assert result.failure_reasons == ("fiscal_anchor_conflict",)
    assert row.qualification_branch == branch and row.comparison == "mismatch"


def test_missing_anchor_is_diagnosed_without_changing_unavailable_reason():
    result = qualify(replacements={"DocumentType": ""})
    row = anchors(result)["DocumentType"]
    assert result.state == "unavailable" and result.failure_reasons == ("fiscal_anchor_unavailable",)
    assert row.qualification_branch == "anchor_unavailable" and row.observation_count == 0


def test_context_visibility_namespace_and_identical_duplicates_are_observed_but_collapse():
    extras = (fact("DocumentFiscalYearFocus", "2025", attrs='contextRef="ctx"', wrapper="ix:hidden")
        + fact("DocumentFiscalYearFocus", "2025", prefix="old"))
    result = qualify(extras=extras); row = anchors(result)["DocumentFiscalYearFocus"]
    observation = row.observations[0]
    assert result.state == "qualified" and row.observation_count == 3
    assert observation.context_ref_present_count == 2 and observation.context_ref_absent_count == 1
    assert observation.visibility_categories == ("hidden", "visible")
    assert len(observation.namespace_identities) == 2 and observation.occurrence_count == 3


@pytest.mark.parametrize("format_value,category", [
    (None, "absent"), ("ixt:date-month-day-year", "resolved:"),
    ("bad:unknown", "present_unresolved"),
])
def test_transform_identity_is_observed_but_never_applied(format_value, category):
    attrs = '' if format_value is None else f'format="{format_value}"'
    replacement = fact("DocumentPeriodEndDate", "March 31, 2025", attrs=attrs)
    result = qualify(replacements={"DocumentPeriodEndDate": replacement})
    observation = anchors(result)["DocumentPeriodEndDate"].observations[0]
    assert result.failure_reasons == ("fiscal_anchor_conflict",)
    assert any(value.startswith(category) for value in observation.transform_categories)
    assert observation.semantic_outcome == "parse_invalid"


@pytest.mark.parametrize("target,expected", [(None, "not_applicable"),
    ("later", "target_present"), ("missing", "target_absent")])
def test_continuation_is_observed_structurally_and_never_followed(target, expected):
    attrs = '' if target is None else f'continuedAt="{target}"'
    continuation = '<ix:continuation id="later">IGNORED CONTINUATION BODY</ix:continuation>'
    replacement = fact("DocumentFiscalYearFocus", "2025", attrs=attrs)
    result = qualify(replacements={"DocumentFiscalYearFocus": replacement}, extras=continuation)
    observation = anchors(result)["DocumentFiscalYearFocus"].observations[0]
    assert result.state == "qualified" and expected in observation.continuation_target_categories
    assert "IGNORED CONTINUATION BODY" not in result.model_dump_json()


def test_lexical_and_distinct_caps_are_diagnostic_only(monkeypatch):
    monkeypatch.setattr(module, "MAX_ANCHOR_DIAGNOSTIC_LEXICAL", 3)
    monkeypatch.setattr(module, "MAX_ANCHOR_DIAGNOSTIC_DISTINCT", 1)
    result = qualify(extras=fact("DocumentFiscalYearFocus", "2024"))
    row = anchors(result)["DocumentFiscalYearFocus"]
    assert result.state == "conflict" and result.failure_reasons == ("fiscal_anchor_conflict",)
    assert row.diagnostic_cap_exceeded and row.observations[0].raw_lexical_value is None
    assert row.observations[0].raw_lexical_category == "over_length"


def test_sanitization_and_deterministic_serialization_exclude_surrounding_and_unrelated_content():
    unrelated = '<ix:nonNumeric name="dei:EntityRegistrantName">UNRELATED SECRET</ix:nonNumeric>'
    first = qualify(unrelated=unrelated); second = qualify(unrelated=unrelated)
    serialized = first.fiscal_anchor_diagnostic.model_dump_json()
    assert serialized == second.fiscal_anchor_diagnostic.model_dump_json()
    for forbidden in ("SURROUNDING PROSE", "UNRELATED SECRET", "<html", "operator@example"):
        assert forbidden not in serialized
