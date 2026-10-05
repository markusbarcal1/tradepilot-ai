"""Audit-only synthetic characterization of frozen DEI anchor semantics."""
from datetime import date

import pytest

from app.models.outlook_inline_revenue import SelectedFilingDocument
from app.services.outlook_structured.inline_revenue_operand import qualify_inline_revenue_operand


DEI_2025 = "http://xbrl.sec.gov/dei/2025"
DEI_2024 = "http://xbrl.sec.gov/dei/2024"


def selected():
    return SelectedFilingDocument(ticker="TEST", issuer="Test Issuer", cik="0001045810",
        target_fiscal_year=2025, expected_role="Q1", accession="0001045810-25-000001",
        form="10-Q", filing_date=date(2025, 4, 1), report_period_end=date(2025, 3, 31),
        primary_document="report.htm",
        source_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581025000001/report.htm",
        selector_policy="anchor-audit-fixture-1")


VALUES = {"DocumentFiscalYearFocus": "2025", "DocumentFiscalPeriodFocus": "Q1",
    "DocumentPeriodEndDate": "2025-03-31", "DocumentType": "10-Q"}


def anchor(name, value, *, prefix="dei", context=' contextRef="ctx"', wrapper="", attrs=""):
    fact = f'<ix:nonNumeric name="{prefix}:{name}"{context}{attrs}>{value}</ix:nonNumeric>'
    return f"<{wrapper}>{fact}</{wrapper}>" if wrapper else fact


def source(*, replacements=None, extras="", namespaces=""):
    replacements = replacements or {}
    anchors = "".join(replacements.get(name, anchor(name, value)) for name, value in VALUES.items())
    return f'''<html xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:dei="{DEI_2025}"
      xmlns:olddei="{DEI_2024}" xmlns:us-gaap="http://fasb.org/us-gaap/2025"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217" {namespaces}><body>{anchors}{extras}
      <xbrli:context id="ctx"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0001045810</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:context id="other"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0001045810</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
      <ix:nonFraction name="us-gaap:Revenues" contextRef="ctx" unitRef="usd" decimals="INF">1000</ix:nonFraction>
      </body></html>'''.encode()


def qualify(**kwargs):
    return qualify_inline_revenue_operand(selected(), source(**kwargs))


@pytest.mark.parametrize("name", tuple(VALUES))
def test_duplicate_identical_each_anchor_collapses(name):
    result = qualify(extras=anchor(name, VALUES[name]))
    assert result.state == "qualified"
    assert len(result.dei_anchor.fact_ordinals) == 5


@pytest.mark.parametrize("name,different", [
    ("DocumentFiscalYearFocus", "2024"), ("DocumentFiscalPeriodFocus", "Q2"),
    ("DocumentPeriodEndDate", "2025-03-30"), ("DocumentType", "10-K"),
])
def test_duplicate_differing_each_anchor_conflicts(name, different):
    result = qualify(extras=anchor(name, different))
    assert result.state == "conflict" and result.failure_reasons == ("fiscal_anchor_conflict",)


@pytest.mark.parametrize("extra", [
    anchor("DocumentFiscalYearFocus", "2025", context=' contextRef="other"'),
    anchor("DocumentFiscalYearFocus", "2025", context=""),
    anchor("DocumentFiscalYearFocus", "2025", wrapper="ix:hidden"),
    anchor("DocumentFiscalYearFocus", "2025", prefix="olddei"),
])
def test_context_visibility_and_accepted_namespace_version_do_not_affect_equal_value(extra):
    assert qualify(extras=extra).state == "qualified"


def test_prefix_different_same_namespace_collapses():
    extra = anchor("DocumentFiscalYearFocus", "2025", prefix="alias")
    assert qualify(extras=extra, namespaces=f'xmlns:alias="{DEI_2025}"').state == "qualified"


def test_multiple_contexts_with_different_values_conflict_but_context_itself_is_not_identity():
    same = qualify(extras=anchor("DocumentFiscalPeriodFocus", "Q1", context=' contextRef="other"'))
    different = qualify(extras=anchor("DocumentFiscalPeriodFocus", "Q2", context=' contextRef="other"'))
    assert same.state == "qualified"
    assert different.state == "conflict" and different.failure_reasons == ("fiscal_anchor_conflict",)


def test_whitespace_is_stripped_but_duplicate_case_variation_conflicts_before_normalization():
    whitespace = qualify(extras=anchor("DocumentFiscalPeriodFocus", "  Q1  "))
    case = qualify(extras=anchor("DocumentFiscalPeriodFocus", "q1"))
    assert whitespace.state == "qualified"
    assert case.state == "conflict" and case.failure_reasons == ("fiscal_anchor_conflict",)


@pytest.mark.parametrize("name,value", [
    ("DocumentFiscalYearFocus", "not-a-year"),
    ("DocumentFiscalPeriodFocus", "H1"),
    ("DocumentPeriodEndDate", "March 31, 2025"),
    ("DocumentType", "FORM 10-Q"),
])
def test_single_unparseable_or_unsupported_value_conflicts(name, value):
    result = qualify(replacements={name: anchor(name, value)})
    assert result.state == "conflict" and result.failure_reasons == ("fiscal_anchor_conflict",)


def test_single_case_variations_normalize_for_period_and_document_type():
    result = qualify(replacements={
        "DocumentFiscalPeriodFocus": anchor("DocumentFiscalPeriodFocus", "q1"),
        "DocumentType": anchor("DocumentType", "10-q")})
    assert result.state == "qualified"


def test_inline_transform_on_dei_date_is_retained_as_raw_text_not_applied():
    formatted = anchor("DocumentPeriodEndDate", "March 31, 2025",
        attrs=' format="ixt:date-month-day-year"')
    result = qualify(replacements={"DocumentPeriodEndDate": formatted},
        namespaces='xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"')
    assert result.state == "conflict" and result.failure_reasons == ("fiscal_anchor_conflict",)


def test_amendment_like_repeated_complete_anchor_set_collapses_when_values_are_identical():
    extras = "".join(anchor(name, value, context=' contextRef="other"') for name, value in VALUES.items())
    result = qualify(extras=extras)
    assert result.state == "qualified" and len(result.dei_anchor.fact_ordinals) == 8
