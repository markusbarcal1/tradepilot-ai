"""Offline tests for the v2 bounded DEI DocumentPeriodEndDate transform."""
from datetime import date, timedelta
import json

import pytest

from app.models.outlook_inline_revenue import SelectedFilingDocument
from app.services.outlook_structured.inline_revenue_document_certification import QUALIFIER_VERSION
from app.services.outlook_structured.inline_revenue_operand import (
    APPROVED_DEI_DATE_TRANSFORM, POLICY_VERSION, qualify_inline_revenue_operand,
)


IXT = "http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
FORMAT = 'format="ixt:date-monthname-day-year-en"'


def selected(*, end="2025-03-31"):
    return SelectedFilingDocument(ticker="TEST", issuer="Test Issuer", cik="0001045810",
        target_fiscal_year=2025, expected_role="Q1", accession="0001045810-25-000001",
        form="10-Q", filing_date=date(2025, 4, 1), report_period_end=date.fromisoformat(end),
        primary_document="report.htm",
        source_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581025000001/report.htm",
        selector_policy="date-transform-fixture-1")


def anchor(name, value, *, attrs="", prefix="dei", context_ref="ctx"):
    return f'<ix:nonNumeric name="{prefix}:{name}" contextRef="{context_ref}" {attrs}>{value}</ix:nonNumeric>'


def payload(*, lexical="March 31, 2025", date_attrs=FORMAT, extras="", revenue_attrs='decimals="INF"',
        revenue_value="1000", extra_namespaces="", fiscal_year=2025,
        context_start="2025-01-01", context_end="2025-03-31"):
    anchors = "".join((anchor("DocumentFiscalYearFocus", str(fiscal_year)),
        anchor("DocumentFiscalPeriodFocus", "Q1"),
        anchor("DocumentPeriodEndDate", lexical, attrs=date_attrs),
        anchor("DocumentType", "10-Q")))
    return f'''<html xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:dei="http://xbrl.sec.gov/dei/2025"
      xmlns:us-gaap="http://fasb.org/us-gaap/2025"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:ixt="{IXT}" {extra_namespaces}>
      <body>{anchors}{extras}
      <xbrli:context id="ctx"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0001045810</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>{context_start}</xbrli:startDate><xbrli:endDate>{context_end}</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
      <ix:nonFraction name="us-gaap:Revenues" contextRef="ctx" unitRef="usd" {revenue_attrs}>{revenue_value}</ix:nonFraction>
      </body></html>'''.encode()


def qualify(**changes):
    document = changes.pop("document", selected())
    changes.setdefault("fiscal_year", document.target_fiscal_year)
    changes.setdefault("context_end", document.report_period_end.isoformat())
    return qualify_inline_revenue_operand(document, payload(**changes))


def date_diagnostic(result):
    return next(row for row in result.fiscal_anchor_diagnostic.anchors
        if row.required_local_name == "DocumentPeriodEndDate")


@pytest.mark.parametrize("lexical,canonical", [
    ("September 27, 2025", "2025-09-27"),
    ("December 28, 2024", "2024-12-28"),
    ("March 29, 2025", "2025-03-29"),
    ("June 28, 2025", "2025-06-28"),
    ("January 25, 2026", "2026-01-25"),
    ("April 27, 2025", "2025-04-27"),
    ("July 27, 2025", "2025-07-27"),
    ("October 26, 2025", "2025-10-26"),
])
def test_exact_live_evidence_shapes_transform(lexical, canonical):
    start = (date.fromisoformat(canonical) - timedelta(days=89)).isoformat()
    result = qualify(document=selected(end=canonical), lexical=lexical, context_start=start)
    observation = date_diagnostic(result).observations[0]
    assert result.state == "qualified" and result.dei_anchor.period_end.isoformat() == canonical
    assert observation.transform_categories == (APPROVED_DEI_DATE_TRANSFORM,)
    assert observation.transform_application_state == "applied"
    assert observation.transformed_canonical_value == canonical
    assert observation.semantic_outcome == "parsed"
    assert date_diagnostic(result).qualification_branch == "anchor_valid"


@pytest.mark.parametrize("lexical", ["March\u00a031, 2025", "March 31,\u00a02025",
    "March\u00a0\u00a031,\u00a0 2025"])
def test_ascii_space_and_nbsp_are_the_only_bounded_whitespace(lexical):
    assert qualify(lexical=lexical).state == "qualified"


@pytest.mark.parametrize("lexical", ["March\t31, 2025", "March\n31, 2025",
    "March\u200331, 2025"])
def test_other_whitespace_is_not_accepted_by_transform_grammar(lexical):
    result = qualify(lexical=lexical)
    row = date_diagnostic(result)
    assert result.state == "conflict"
    assert row.qualification_branch == "period_end_transform_invalid_lexical"


def test_existing_capture_boundary_stripping_remains_in_force():
    assert qualify(lexical="  March 31, 2025  ").state == "qualified"


def test_no_transform_preserves_existing_iso_behavior():
    result = qualify(lexical="2025-03-31", date_attrs="")
    observation = date_diagnostic(result).observations[0]
    assert result.state == "qualified"
    assert observation.transform_application_state == "not_applicable"
    assert observation.transformed_canonical_value is None


def test_transformed_manifest_mismatch_still_fails():
    result = qualify(document=selected(end="2025-03-30"))
    row = date_diagnostic(result)
    assert result.state == "conflict" and row.comparison == "mismatch"
    assert row.qualification_branch == "period_end_mismatch"


@pytest.mark.parametrize("date_attrs,extra_namespaces,branch,state", [
    ('format="wrong:date-monthname-day-year-en"',
        'xmlns:wrong="http://www.xbrl.org/inlineXBRL/transformation/2022-02-16"',
        "period_end_transform_unsupported", "unsupported"),
    ('format="ixt:date-month-day-year-en"', "", "period_end_transform_unsupported", "unsupported"),
    ('format="missing:date-monthname-day-year-en"', "", "period_end_transform_unresolved", "unresolved"),
    ('format="date-monthname-day-year-en"', "", "period_end_transform_unresolved", "unresolved"),
    ('format=":bad"', "", "period_end_transform_unresolved", "unresolved"),
])
def test_transform_identity_failures_are_typed(date_attrs, extra_namespaces, branch, state):
    result = qualify(date_attrs=date_attrs, extra_namespaces=extra_namespaces)
    row = date_diagnostic(result)
    assert result.state == "conflict" and row.qualification_branch == branch
    assert row.observations[0].transform_application_state == state


@pytest.mark.parametrize("lexical", ["Smarch 31, 2025", "March 0, 2025",
    "March 32, 2025", "February 29, 2025", "March 31 2025", "31 March, 2025",
    "March 31, 2025 extra", "march 31, 2025", "March 031, 2025",
    "March 31, 02025", "M" * 65])
def test_malformed_or_ambiguous_transform_lexical_values_fail_closed(lexical):
    result = qualify(lexical=lexical)
    row = date_diagnostic(result)
    assert result.state == "conflict"
    assert row.qualification_branch == "period_end_transform_invalid_lexical"
    assert row.observations[0].transform_application_state == "invalid_lexical"


def test_conflicting_raw_values_do_not_select_the_manifest_matching_value():
    extra = anchor("DocumentPeriodEndDate", "March 30, 2025", attrs=FORMAT)
    first = qualify(extras=extra)
    second = qualify(document=selected(end="2025-03-30"), extras=extra)
    for result in (first, second):
        row = date_diagnostic(result)
        assert result.state == "conflict" and row.qualification_branch == "duplicate_distinct"
        assert row.distinct_stripped_raw_value_count == 2


def test_identical_duplicates_collapse_only_with_the_same_transform_identity():
    same = qualify(extras=anchor("DocumentPeriodEndDate", "March 31, 2025", attrs=FORMAT))
    mixed = qualify(extras=anchor("DocumentPeriodEndDate", "March 31, 2025"))
    assert same.state == "qualified"
    row = date_diagnostic(mixed)
    assert mixed.state == "conflict"
    assert row.qualification_branch == "period_end_transform_unsupported"


def test_context_and_visibility_do_not_create_manifest_directed_selection():
    extra = ('<ix:hidden>' + anchor("DocumentPeriodEndDate", "March 30, 2025",
        attrs=FORMAT, context_ref="other")
        + '</ix:hidden>')
    result = qualify(extras=extra)
    assert result.state == "conflict"
    assert date_diagnostic(result).qualification_branch == "duplicate_distinct"


def test_multiple_transform_identities_fail_closed_even_for_identical_raw_text():
    attrs = 'format="other:date-monthname-day-year-en"'
    extra = anchor("DocumentPeriodEndDate", "March 31, 2025", attrs=attrs)
    result = qualify(extras=extra,
        extra_namespaces='xmlns:other="http://www.xbrl.org/inlineXBRL/transformation/2022-02-16"')
    assert result.state == "conflict"
    assert date_diagnostic(result).qualification_branch == "period_end_transform_unsupported"


def test_approved_format_attribute_on_instance_fact_is_not_treated_as_inline():
    instance = ('<dei:DocumentPeriodEndDate contextRef="ctx" '
        'format="ixt:date-monthname-day-year-en">March 31, 2025</dei:DocumentPeriodEndDate>')
    result = qualify(extras=instance, lexical="March 31, 2025", date_attrs=FORMAT)
    row = date_diagnostic(result)
    assert result.state == "conflict"
    assert row.qualification_branch == "period_end_transform_unsupported"


def test_continuation_is_not_followed_for_transform_qualification():
    result = qualify(lexical="March 31, ",
        date_attrs=FORMAT + ' continuedAt="rest"',
        extras='<ix:continuation id="rest">2025</ix:continuation>')
    row = date_diagnostic(result)
    assert result.state == "conflict"
    assert row.qualification_branch == "period_end_transform_invalid_lexical"
    assert row.observations[0].continuation_target_categories == ("target_present",)
    assert "2025</ix:continuation" not in result.model_dump_json()


def test_other_anchors_and_revenue_numeric_transform_remain_unchanged():
    result = qualify(revenue_value="1,000.25",
        revenue_attrs='decimals="2" format="ixt:num-dot-decimal"')
    rows = {row.required_local_name: row for row in result.fiscal_anchor_diagnostic.anchors}
    assert result.state == "qualified" and str(result.operand.numeric.normalized_value) == "1000.25"
    assert all(rows[name].qualification_branch == "anchor_valid" for name in (
        "DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus", "DocumentType"))


def test_v2_policy_and_future_runner_binding_do_not_mutate_v1_artifact():
    artifact_path = "../docs/diagnostics/phase6b5c2a5w5-inline-revenue-anchor-diagnostic-rerun-20261001.json"
    historical = json.loads(open(artifact_path, encoding="utf-8").read())
    assert historical["qualifier"] == "sec-inline-xbrl-revenue-operand-1"
    assert historical["roles"][0]["fiscal_anchor_diagnostic"]["schema_version"] == "1"
    assert POLICY_VERSION == QUALIFIER_VERSION == "sec-inline-xbrl-revenue-operand-2"
    assert qualify().policy_version == "sec-inline-xbrl-revenue-operand-2"
