"""Offline qualification tests for sec-inline-xbrl-revenue-operand-2."""
from datetime import date, datetime, timezone
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from app.models.outlook_inline_revenue import ExpandedQName, SelectedFilingDocument
from app.services.outlook_structured.inline_revenue_operand import (
    CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES, EQUIVALENCE_POLICY_VERSION,
    PARTITION_IDENTITY_POLICY_VERSION, POLICY_VERSION,
    STRICT_PARTITION_IDENTITY_POLICY_VERSION, STRICT_REVENUE_CONCEPT_EQUIVALENCES,
    qualify_inline_revenue_operand, revenue_concepts_equivalent,
    validate_revenue_operand_partition,
)


US_GAAP = "http://fasb.org/us-gaap/2025"
DEI = "http://xbrl.sec.gov/dei/2025"
NS = f'''xmlns:xbrli="http://www.xbrl.org/2003/instance"
xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
xmlns:dei="{DEI}" xmlns:us-gaap="{US_GAAP}"
xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"'''


def selected(role="Q1", *, form=None, end=None, state="selected", document="report.htm"):
    end = end or ("2025-12-31" if role == "FY" else {"Q1": "2025-03-31",
        "Q2": "2025-06-30", "Q3": "2025-09-30"}[role])
    form = form or ("10-K" if role == "FY" else "10-Q")
    return SelectedFilingDocument(ticker="TEST", issuer="Synthetic Issuer",
        cik="0001045810", target_fiscal_year=2025, expected_role=role,
        accession="0001045810-25-000001", form=form, filing_date=date(2025, 5, 1),
        acceptance_time=datetime(2025, 5, 1, 20, tzinfo=timezone.utc),
        report_period_end=date.fromisoformat(end), primary_document=document,
        source_url=f"https://www.sec.gov/Archives/edgar/data/1045810/000104581025000001/{document}",
        source_kind="inline_primary", selector_policy="synthetic-selector-1",
        selection_state=state)


def context(*, identifier="0001045810", scheme="http://www.sec.gov/CIK",
            start="2025-01-01", end="2025-03-31", context_id="ctx", inner="",
            instant=None, segment=False, scenario=False):
    period = f"<xbrli:instant>{instant}</xbrli:instant>" if instant else (
        f"<xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate>")
    scoped = (f"<xbrli:segment>{inner}</xbrli:segment>" if segment else inner) + (
        "<xbrli:scenario> </xbrli:scenario>" if scenario else "")
    return (f'<xbrli:context id="{context_id}"><xbrli:entity>'
        f'<xbrli:identifier scheme="{scheme}">{identifier}</xbrli:identifier>{scoped}'
        f'</xbrli:entity><xbrli:period>{period}</xbrli:period></xbrli:context>')


def unit(unit_id="usd", body="<xbrli:measure>iso4217:USD</xbrli:measure>"):
    return f'<xbrli:unit id="{unit_id}">{body}</xbrli:unit>'


def fact(*, concept="us-gaap:Revenues", context_ref="ctx", unit_ref="usd",
         value="1000", attrs='decimals="INF"'):
    return (f'<ix:nonFraction name="{concept}" contextRef="{context_ref}" '
        f'unitRef="{unit_ref}" {attrs}>{value}</ix:nonFraction>')


def anchors(role="Q1", *, year=2025, end=None, form=None, duplicate=""):
    end = end or ("2025-12-31" if role == "FY" else {"Q1": "2025-03-31",
        "Q2": "2025-06-30", "Q3": "2025-09-30"}[role])
    form = form or ("10-K" if role == "FY" else "10-Q")
    values = (("DocumentFiscalYearFocus", year), ("DocumentFiscalPeriodFocus", role),
        ("DocumentPeriodEndDate", end), ("DocumentType", form))
    rendered = "".join(f'<ix:nonNumeric name="dei:{name}" contextRef="ctx">{value}</ix:nonNumeric>'
        for name, value in values)
    return rendered + duplicate


def source(*, role="Q1", contexts=None, units=None, facts=None, anchor_text=None,
           namespaces=NS, extra=""):
    default_end = "2025-12-31" if role == "FY" else {"Q1": "2025-03-31",
        "Q2": "2025-06-30", "Q3": "2025-09-30"}[role]
    default_start = "2025-01-01" if role in {"FY", "Q1"} else (
        "2025-04-01" if role == "Q2" else "2025-07-01")
    contexts = context(start=default_start, end=default_end) if contexts is None else contexts
    units = unit() if units is None else units
    facts = fact() if facts is None else facts
    anchor_text = anchors(role) if anchor_text is None else anchor_text
    return f"<html {namespaces}><body>{anchor_text}{contexts}{units}{facts}{extra}</body></html>".encode()


def qualify(role="Q1", **changes):
    document = changes.pop("document", selected(role))
    return qualify_inline_revenue_operand(document, source(role=role, **changes))


def test_identity_and_valid_nondimensional_operand_are_frozen_and_provenanced():
    result = qualify()
    assert result.state == "qualified" and result.policy_version == POLICY_VERSION
    operand = result.operand
    assert operand.numeric.normalized_value == 1000
    assert operand.expanded_qname.namespace_uri == US_GAAP
    assert operand.context.entity_value == "0001045810"
    assert operand.unit.currency == "USD" and operand.reporting_scope == "consolidated_entity"
    assert operand.fact_ordinal == 4 and operand.dei_anchor.fact_ordinals == (0, 1, 2, 3)
    with pytest.raises(ValidationError):
        type(operand).model_validate({**operand.model_dump(), "metric": "diluted_eps"})


@pytest.mark.parametrize("concept", [
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    "us-gaap:Revenues", "us-gaap:SalesRevenueNet",
])
def test_each_supported_revenue_concept(concept):
    assert qualify(facts=fact(concept=concept)).state == "qualified"


def test_expanded_qname_accepts_alternate_prefix_and_rejects_spoofed_prefix():
    alternate = NS + f' xmlns:foo="{US_GAAP}"'
    assert qualify(namespaces=alternate, facts=fact(concept="foo:Revenues")).state == "qualified"
    spoofed = NS.replace(f'xmlns:us-gaap="{US_GAAP}"', 'xmlns:us-gaap="https://evil.invalid/us-gaap/2025"')
    result = qualify(namespaces=spoofed)
    assert result.state == "unavailable" and result.failure_reasons == ("concept_unavailable",)


def test_explicitly_supplied_xbrl_instance_bytes_are_supported_offline():
    instance = (f'<xbrli:xbrl {NS}>{context()}{unit()}'
        '<dei:DocumentFiscalYearFocus contextRef="ctx">2025</dei:DocumentFiscalYearFocus>'
        '<dei:DocumentFiscalPeriodFocus contextRef="ctx">Q1</dei:DocumentFiscalPeriodFocus>'
        '<dei:DocumentPeriodEndDate contextRef="ctx">2025-03-31</dei:DocumentPeriodEndDate>'
        '<dei:DocumentType contextRef="ctx">10-Q</dei:DocumentType>'
        '<us-gaap:Revenues contextRef="ctx" unitRef="usd" decimals="INF">1000</us-gaap:Revenues>'
        '</xbrli:xbrl>').encode()
    result = qualify_inline_revenue_operand(
        selected().model_copy(update={"source_kind": "xbrl_instance"}), instance)
    assert result.state == "qualified" and result.operand.source_kind == "xbrl_instance"


def test_unsupported_custom_and_eps_concepts_never_qualify():
    custom_ns = NS + ' xmlns:custom="https://example.invalid/custom"'
    assert qualify(namespaces=custom_ns, facts=fact(concept="custom:Revenue")).state == "unavailable"
    eps = fact(concept="us-gaap:EarningsPerShareDiluted")
    assert qualify(facts=eps).state == "unavailable"


def test_multiple_supported_concepts_are_ambiguous():
    facts = fact() + fact(concept="us-gaap:SalesRevenueNet", value="1000")
    result = qualify(facts=facts)
    assert result.state == "ambiguous" and "ambiguous_concept" in result.failure_reasons


def test_empty_scope_is_allowed_but_dimensions_fail_closed():
    empty = context(inner=" ", segment=True, scenario=True)
    assert qualify(contexts=empty).state == "qualified"
    explicit = '<xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">us-gaap:ProductMember</xbrldi:explicitMember>'
    result = qualify(contexts=context(inner=explicit, segment=True))
    assert result.state == "unavailable" and "dimensional_context_unsupported" in result.failure_reasons
    typed = '<xbrldi:typedMember dimension="us-gaap:CustomAxis"><foo xmlns="urn:test">secret</foo></xbrldi:typedMember>'
    result = qualify(contexts=context(inner=typed, segment=True))
    assert "typed_dimension_unsupported" in result.failure_reasons
    assert "secret" not in result.model_dump_json()


def test_conflicting_duplicate_dimension_is_conflict():
    members = "".join((
        '<xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">us-gaap:ProductMember</xbrldi:explicitMember>',
        '<xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">us-gaap:OtherMember</xbrldi:explicitMember>'))
    result = qualify(contexts=context(inner=members, segment=True))
    assert result.state == "conflict" and "duplicate_conflict" in result.failure_reasons


@pytest.mark.parametrize("identifier,scheme", [
    ("999999", "http://www.sec.gov/CIK"),
    ("0001045810", "https://example.invalid/entity"),
])
def test_wrong_or_unprovable_entity_rejects(identifier, scheme):
    result = qualify(contexts=context(identifier=identifier, scheme=scheme))
    assert "entity_mismatch" in result.failure_reasons


def test_missing_conflicting_and_instant_contexts_fail_closed():
    assert "context_missing" in qualify(facts=fact(context_ref="missing")).failure_reasons
    duplicate = context() + context(start="2025-01-02")
    result = qualify(contexts=duplicate)
    assert result.state == "conflict" and "context_ambiguous" in result.failure_reasons
    result = qualify(contexts=context(instant="2025-03-31"))
    assert "period_unavailable" in result.failure_reasons


def test_valid_equivalent_usd_unit_ids_and_invalid_units():
    units = unit("usd-a") + unit("usd-b")
    facts = fact(unit_ref="usd-a") + fact(unit_ref="usd-b")
    result = qualify(units=units, facts=facts)
    assert result.state == "qualified" and result.operand.duplicate_count == 1
    eur = unit(body="<xbrli:measure>iso4217:EUR</xbrli:measure>")
    assert "unsupported_currency" in qualify(units=eur).failure_reasons
    shares = unit(body="<xbrli:measure>xbrli:shares</xbrli:measure>")
    assert qualify(units=shares).state == "unavailable"
    divided = unit(body="<xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unitNumerator><xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide>")
    assert "unit_mismatch" in qualify(units=divided).failure_reasons
    multiple = unit(body="<xbrli:measure>iso4217:USD</xbrli:measure><xbrli:measure>xbrli:shares</xbrli:measure>")
    assert "unit_mismatch" in qualify(units=multiple).failure_reasons
    assert "unit_unavailable" in qualify(facts=fact(unit_ref="missing")).failure_reasons


def test_conflicting_duplicate_unit_id_is_conflict():
    units = unit() + unit(body="<xbrli:measure>iso4217:EUR</xbrli:measure>")
    result = qualify(units=units)
    assert result.state == "conflict" and "duplicate_conflict" in result.failure_reasons


@pytest.mark.parametrize("value,attrs,expected", [
    ("1000", 'decimals="INF"', "1000"),
    ("1000.25", 'decimals="2"', "1000.25"),
    ("1,000.25", 'decimals="2"', "1000.25"),
    ("(1000)", 'decimals="INF"', "-1000"),
    ("12", 'decimals="INF" scale="3"', "12000"),
    ("12000", 'decimals="INF" scale="-3"', "12.000"),
    ("1000", 'decimals="INF" sign="-"', "-1000"),
    ("1,000.25", 'decimals="2" format="ixt:num-dot-decimal"', "1000.25"),
])
def test_numeric_normalization(value, attrs, expected):
    result = qualify(facts=fact(value=value, attrs=attrs))
    assert result.state == "qualified"
    assert result.operand.numeric.normalized_value == Decimal(expected)


@pytest.mark.parametrize("value,attrs,reason", [
    ("", 'decimals="INF"', "malformed_numeric_value"),
    ("12,34", 'decimals="INF"', "malformed_numeric_value"),
    ("NaN", 'decimals="INF"', "malformed_numeric_value"),
    ("1e3", 'decimals="INF"', "malformed_numeric_value"),
    ("(100)", 'decimals="INF" sign="-"', "malformed_numeric_value"),
    ("100", 'decimals="bad"', "precision_unproven"),
    ("100", 'decimals="INF" format="ixt:unknown"', "unsupported_numeric_transform"),
])
def test_invalid_numeric_forms(value, attrs, reason):
    assert reason in qualify(facts=fact(value=value, attrs=attrs)).failure_reasons


def test_nil_and_missing_precision_fail_closed_with_namespace_aware_nil():
    nil = fact(value="", attrs='decimals="INF" xsi:nil="true"')
    assert "nil_fact" in qualify(facts=nil).failure_reasons
    assert "precision_unproven" in qualify(facts=fact(attrs="")).failure_reasons


def test_exact_duplicates_collapse_and_differing_values_conflict():
    result = qualify(facts=fact() + fact())
    assert result.state == "qualified" and result.operand.duplicate_count == 1
    assert result.operand.occurrence_ordinals == (4, 5)
    result = qualify(facts=fact() + fact(value="1001"))
    assert result.state == "conflict" and "duplicate_conflict" in result.failure_reasons


def test_different_compatible_contexts_are_ambiguous_not_order_ranked():
    contexts = context(context_id="a") + context(context_id="b", start="2025-01-02")
    facts = fact(context_ref="a") + fact(context_ref="b")
    result = qualify(contexts=contexts, facts=facts)
    assert result.state == "ambiguous" and result.failure_reasons == ("operand_ambiguous",)


@pytest.mark.parametrize("role,start,end,form", [
    ("Q1", "2025-01-01", "2025-03-31", "10-Q"),
    ("Q2", "2025-04-01", "2025-06-30", "10-Q"),
    ("Q3", "2025-07-01", "2025-09-30", "10-Q"),
    ("FY", "2025-01-01", "2025-12-31", "10-K"),
])
def test_each_period_role(role, start, end, form):
    result = qualify(role, document=selected(role, form=form, end=end),
        contexts=context(start=start, end=end), anchor_text=anchors(role, end=end, form=form))
    assert result.state == "qualified" and result.operand.role == role


def test_ytd_wrong_year_period_form_and_report_end_fail_closed():
    q2_ytd = qualify("Q2", contexts=context(start="2025-01-01", end="2025-06-30"))
    assert "period_role_mismatch" in q2_ytd.failure_reasons
    q3_ytd = qualify("Q3", contexts=context(start="2025-01-01", end="2025-09-30"))
    assert "period_role_mismatch" in q3_ytd.failure_reasons
    wrong_year = qualify(anchor_text=anchors("Q1", year=2024))
    assert wrong_year.state == "conflict" and "fiscal_anchor_conflict" in wrong_year.failure_reasons
    wrong_period = qualify(anchor_text=anchors("Q2", end="2025-03-31"))
    assert "fiscal_anchor_conflict" in wrong_period.failure_reasons
    wrong_form = qualify(document=selected("Q1", form="10-K"), anchor_text=anchors("Q1", form="10-K"))
    assert "period_role_mismatch" in wrong_form.failure_reasons
    mismatch = qualify(contexts=context(end="2025-03-30"))
    assert "period_role_mismatch" in mismatch.failure_reasons


def test_missing_and_conflicting_dei_anchors():
    assert "fiscal_anchor_unavailable" in qualify(anchor_text="").failure_reasons
    duplicate = '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2024</ix:nonNumeric>'
    result = qualify(anchor_text=anchors("Q1", duplicate=duplicate))
    assert result.state == "conflict" and "fiscal_anchor_conflict" in result.failure_reasons


def test_selection_state_amendment_identity_and_model_safety():
    for state, expected in (("unavailable", "unavailable"), ("ambiguous", "ambiguous"), ("conflict", "conflict")):
        result = qualify_inline_revenue_operand(selected(state=state), b"ignored")
        assert result.state == expected
    amended = selected("Q1", form="10-Q/A")
    result = qualify(document=amended, anchor_text=anchors("Q1", form="10-Q/A"))
    assert result.state == "qualified" and result.operand.form == "10-Q/A"
    with pytest.raises(ValidationError): selected(document="../unsafe.htm")


def _operand(role, start, end, *, annual_end=None):
    document = selected(role, end=annual_end or end)
    return qualify(role, document=document, contexts=context(start=start, end=end),
        anchor_text=anchors(role, end=annual_end or end)).operand


def test_partition_validator_valid_52_week_and_53_week_geometry_without_arithmetic():
    annual = _operand("FY", "2025-01-01", "2025-12-31")
    q1 = _operand("Q1", "2025-01-01", "2025-03-31")
    q2 = _operand("Q2", "2025-04-01", "2025-06-30")
    q3 = _operand("Q3", "2025-07-01", "2025-09-30")
    valid = validate_revenue_operand_partition(annual=annual, q1=q1, q2=q2, q3=q3)
    assert valid.state == "valid" and valid.residual_duration_days == 92
    assert "value" not in valid.model_dump_json()
    annual_53 = _operand("FY", "2025-01-01", "2026-01-07")
    valid_53 = validate_revenue_operand_partition(annual=annual_53, q1=q1, q2=q2, q3=q3)
    assert valid_53.state == "valid" and valid_53.residual_duration_days == 99


@pytest.mark.parametrize("change,reason", [
    (("q2", "2025-04-02", "2025-06-30"), "q1_q2_gap_or_overlap"),
    (("q2", "2025-03-31", "2025-06-30"), "q1_q2_gap_or_overlap"),
    (("q2", "2025-04-01", "2025-09-30"), "quarter_duration_invalid"),
    (("annual", "2024-12-31", "2025-12-31"), "annual_q1_start_mismatch"),
    (("annual", "2025-01-01", "2025-11-30"), "residual_duration_invalid"),
    (("annual", "2025-01-01", "2026-02-15"), "residual_duration_invalid"),
    (("q3", "2025-06-30", "2025-09-30"), "q2_q3_gap_or_overlap"),
])
def test_partition_validator_rejects_gap_overlap_ytd_start_and_residual(change, reason):
    operands = {"annual": _operand("FY", "2025-01-01", "2025-12-31"),
        "q1": _operand("Q1", "2025-01-01", "2025-03-31"),
        "q2": _operand("Q2", "2025-04-01", "2025-06-30"),
        "q3": _operand("Q3", "2025-07-01", "2025-09-30")}
    name, start, end = change
    original = operands[name]
    operands[name] = original.model_copy(update={
        "context": original.context.model_copy(update={
            "period_start": date.fromisoformat(start),
            "period_end": date.fromisoformat(end),
        })
    })
    result = validate_revenue_operand_partition(**operands)
    assert result.state == "conflict" and reason in result.reasons


def _partition_identity_operands():
    return {"annual": _operand("FY", "2025-01-01", "2025-12-31"),
        "q1": _operand("Q1", "2025-01-01", "2025-03-31"),
        "q2": _operand("Q2", "2025-04-01", "2025-06-30"),
        "q3": _operand("Q3", "2025-07-01", "2025-09-30")}


@pytest.mark.parametrize("mutation", [
    lambda row: row.model_copy(update={"expanded_qname": row.expanded_qname.model_copy(
        update={"namespace_uri": "http://fasb.org/us-gaap/2023"})}),
    lambda row: row.model_copy(update={"expanded_qname": row.expanded_qname.model_copy(
        update={"local_name": "SalesRevenueNet"})}),
    lambda row: row.model_copy(update={"context": row.context.model_copy(
        update={"entity_scheme": "https://www.sec.gov/CIK"})}),
    lambda row: row.model_copy(update={"context": row.context.model_copy(
        update={"entity_value": "0000320193"})}),
    lambda row: row.model_copy(update={"unit": row.unit.model_copy(update={"currency": "EUR"})}),
    lambda row: row.model_copy(update={"unit": row.unit.model_copy(
        update={"numerator_measures": (ExpandedQName(
            namespace_uri="http://www.xbrl.org/2003/instance", local_name="shares"),)})}),
    lambda row: row.model_copy(update={"context": row.context.model_copy(
        update={"explicit_dimensions": ((ExpandedQName(namespace_uri="urn:test", local_name="Axis"),
            ExpandedQName(namespace_uri="urn:test", local_name="Member")),)})}),
    lambda row: row.model_copy(update={"context": row.context.model_copy(
        update={"typed_dimension_count": 1})}),
    lambda row: row.model_copy(update={"accounting_basis": "other"}),
    lambda row: row.model_copy(update={"target_fiscal_year": 2024}),
])
def test_partition_identity_each_compared_field_triggers_mismatch(mutation):
    operands = _partition_identity_operands()
    operands["q1"] = mutation(operands["q1"])
    result = validate_revenue_operand_partition(**operands)
    assert result.state == "conflict" and "operand_identity_mismatch" in result.reasons


def test_partition_identity_ignores_source_ids_and_reporting_scope():
    operands = _partition_identity_operands()
    q1 = operands["q1"]
    operands["q1"] = q1.model_copy(update={"reporting_scope": "other",
        "context": q1.context.model_copy(update={"context_id": "different-context-id"}),
        "unit": q1.unit.model_copy(update={"unit_id": "different-unit-id"})})
    result = validate_revenue_operand_partition(**operands)
    assert result.state == "valid"


def _qname(year, local="RevenueFromContractWithCustomerExcludingAssessedTax"):
    return ExpandedQName(namespace_uri=f"http://fasb.org/us-gaap/{year}", local_name=local)


def test_equivalence_policy_is_exactly_the_two_fingerprint_bound_records():
    assert len(CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES) == 2
    assert {row.local_name for row in CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES} == {
        "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"}
    assert {row.policy_version for row in CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES} == {
        EQUIVALENCE_POLICY_VERSION}
    assert {row.source_package_sha256 for row in CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES} == {
        "DECDD417D86FF7BFB5CA166C0CA1001017AEA873673544A8D7F91C34BF5D82DF"}
    assert {row.target_package_sha256 for row in CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES} == {
        "A3B835925AD74030EB5BE865A26D7DFE44013081C4AB7204B6122316A685FFF4"}
    with pytest.raises(ValidationError):
        CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES[0].local_name = "Other"


@pytest.mark.parametrize("a,b,expected", [
    (_qname(2025), _qname(2025), True),
    (_qname(2024), _qname(2025), True),
    (_qname(2025), _qname(2024), True),
    (_qname(2024, "Revenues"), _qname(2025, "Revenues"), True),
    (_qname(2023), _qname(2024), False),
    (_qname(2025), _qname(2026), False),
    (_qname(2024), _qname(2026), False),
    (_qname(2024), _qname(2025, "Revenues"), False),
    (_qname(2024, "SalesRevenueNet"), _qname(2025, "SalesRevenueNet"), False),
    (ExpandedQName(namespace_uri="http://example.invalid/us-gaap/2024",
        local_name="Revenues"), _qname(2025, "Revenues"), False),
    (ExpandedQName(namespace_uri="http://fasb.org/us-gaap/2024-extra",
        local_name="Revenues"), _qname(2025, "Revenues"), False),
    (_qname(2024, "Revenue"), _qname(2025, "Revenues"), False),
    (ExpandedQName(namespace_uri="", local_name="Revenues"),
        ExpandedQName(namespace_uri="", local_name="Revenues"), False),
    (None, _qname(2025), False),
])
def test_revenue_concept_equivalence_matrix(a, b, expected):
    assert revenue_concepts_equivalent(a, b) is expected


def _with_qnames(operands, annual_qname, quarterly_qname):
    updated = dict(operands)
    updated["annual"] = updated["annual"].model_copy(
        update={"expanded_qname": annual_qname})
    for role in ("q1", "q2", "q3"):
        updated[role] = updated[role].model_copy(
            update={"expanded_qname": quarterly_qname})
    return updated


@pytest.mark.parametrize("local", [
    "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"])
def test_partition_accepts_only_certified_cross_version_concepts_with_diagnostics(local):
    operands = _with_qnames(_partition_identity_operands(), _qname(2025, local), _qname(2024, local))
    before = tuple(row.expanded_qname for row in operands.values())
    result = validate_revenue_operand_partition(**operands)
    assert result.state == "valid"
    assert result.partition_policy_version == PARTITION_IDENTITY_POLICY_VERSION
    assert result.concept_identity.state == "certified_cross_version_equivalence"
    assert result.concept_identity.original_qnames == before
    assert len(result.concept_identity.certified_records) == 1
    assert tuple(row.expanded_qname for row in operands.values()) == before


def test_exact_qname_diagnostic_and_numeric_values_do_not_influence_identity():
    operands = _partition_identity_operands()
    operands["q1"] = operands["q1"].model_copy(update={"numeric":
        operands["q1"].numeric.model_copy(update={"normalized_value": Decimal("999999")})})
    result = validate_revenue_operand_partition(**operands)
    assert result.state == "valid" and result.concept_identity.state == "exact_qname"


def test_historical_strict_partition_policy_remains_explicitly_characterizable():
    operands = _with_qnames(_partition_identity_operands(), _qname(2025), _qname(2024))
    result = validate_revenue_operand_partition(**operands,
        concept_equivalence_policy=STRICT_REVENUE_CONCEPT_EQUIVALENCES,
        partition_policy_version=STRICT_PARTITION_IDENTITY_POLICY_VERSION,
        equivalence_policy_version="none-strict-expanded-qname")
    assert result.state == "conflict" and result.partition_policy_version == (
        STRICT_PARTITION_IDENTITY_POLICY_VERSION)
    assert result.concept_identity.state == "mismatch"
    assert "operand_identity_mismatch" in result.reasons


@pytest.mark.parametrize("ticker,fy,periods,namespace_years,expected", [
    ("AAPL", 2025, (("2024-09-29", "2025-09-27"), ("2024-09-29", "2024-12-28"),
        ("2024-12-29", "2025-03-29"), ("2025-03-30", "2025-06-28")),
        (2025, 2024, 2024, 2024), (date(2025, 6, 29), date(2025, 9, 27), 91)),
    ("NVDA", 2026, (("2025-01-27", "2026-01-25"), ("2025-01-27", "2025-04-27"),
        ("2025-04-28", "2025-07-27"), ("2025-07-28", "2025-10-26")),
        (2025, 2024, 2025, 2025), (date(2025, 10, 27), date(2026, 1, 25), 91)),
])
def test_certified_synthetic_saved_evidence_geometry(
        ticker, fy, periods, namespace_years, expected):
    roles = ("annual", "q1", "q2", "q3")
    operands = _partition_identity_operands()
    for role, (start, end), namespace_year in zip(roles, periods, namespace_years):
        row = operands[role]
        operands[role] = row.model_copy(update={"ticker": ticker, "target_fiscal_year": fy,
            "expanded_qname": _qname(namespace_year),
            "context": row.context.model_copy(update={"period_start": date.fromisoformat(start),
                "period_end": date.fromisoformat(end)})})
    result = validate_revenue_operand_partition(**operands)
    assert (result.residual_period_start, result.residual_period_end,
        result.residual_duration_days) == expected


def test_bounds_fail_closed_and_never_create_uniqueness(monkeypatch):
    import app.services.outlook_structured.inline_revenue_operand as module
    monkeypatch.setattr(module, "MAX_SOURCE_BYTES", 32)
    result = qualify_inline_revenue_operand(selected(), source())
    assert result.state == "unavailable" and "source_too_large" in result.failure_reasons
    monkeypatch.setattr(module, "MAX_SOURCE_BYTES", 4 * 1024 * 1024)
    monkeypatch.setattr(module, "MAX_COMPETING_FACTS", 1)
    contexts = context(context_id="a") + context(context_id="b", start="2025-01-02")
    facts = fact(context_ref="a") + fact(context_ref="b")
    result = qualify(contexts=contexts, facts=facts)
    assert result.state == "unavailable" and "parser_cap_exceeded" in result.failure_reasons


@pytest.mark.parametrize("constant,value,extra", [
    ("MAX_ELEMENTS", 5, "<div><span>x</span></div>"),
    ("MAX_CONTEXTS", 0, ""),
    ("MAX_UNITS", 0, ""),
    ("MAX_FACTS", 3, ""),
    ("MAX_REVENUE_FACTS", 0, ""),
    ("MAX_IDENTITY_CHARS", 5, ""),
    ("MAX_NUMERIC_CHARS", 2, ""),
])
def test_individual_parser_caps(constant, value, extra, monkeypatch):
    import app.services.outlook_structured.inline_revenue_operand as module
    monkeypatch.setattr(module, constant, value)
    result = qualify(extra=extra)
    assert result.state == "unavailable" and "parser_cap_exceeded" in result.failure_reasons


def test_dimension_and_typed_dimension_caps(monkeypatch):
    import app.services.outlook_structured.inline_revenue_operand as module
    monkeypatch.setattr(module, "MAX_DIMENSIONS", 0)
    member = '<xbrldi:explicitMember dimension="us-gaap:Axis">us-gaap:Member</xbrldi:explicitMember>'
    assert "parser_cap_exceeded" in qualify(contexts=context(inner=member, segment=True)).failure_reasons
    monkeypatch.setattr(module, "MAX_DIMENSIONS", 16)
    monkeypatch.setattr(module, "MAX_TYPED_DIMENSIONS", 0)
    typed = '<xbrldi:typedMember dimension="us-gaap:Axis"><x>hidden</x></xbrldi:typedMember>'
    assert "parser_cap_exceeded" in qualify(contexts=context(inner=typed, segment=True)).failure_reasons


def test_deterministic_serialization_no_raw_source_or_external_behavior():
    payload = source(extra="<script>TOP_SECRET_SOURCE</script><p>arbitrary prose</p>")
    first = qualify_inline_revenue_operand(selected(), payload)
    second = qualify_inline_revenue_operand(selected(), payload)
    assert first.model_dump_json() == second.model_dump_json()
    serialized = first.model_dump_json()
    assert "TOP_SECRET_SOURCE" not in serialized and "arbitrary prose" not in serialized
    assert not hasattr(first, "client") and not hasattr(first, "cache")
