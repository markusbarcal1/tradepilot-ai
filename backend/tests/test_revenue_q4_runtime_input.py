from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from app.models.outlook_inline_revenue import SelectedFilingDocument
from app.models.outlook_revenue_filing_document import (
    RetrievedRevenueFilingDocument, RevenueFilingDocumentBatchResult,
    RevenueFilingDocumentRequestAccounting,
)
from app.models.outlook_revenue_filing_selection import (
    RevenueFilingQuarterAnchor, RevenueFilingSelectionRequest, SecSubmissionFilingRow,
    SecSubmissionsSelectionInput, FilingMetadataProvenance, SelectedRevenueFiling,
    RevenueFilingSelectionResult,
)
from app.services.outlook_structured.inline_revenue_operand import qualify_inline_revenue_operand
from app.services.outlook_structured.revenue_filing_selection import select_revenue_operand_filings
from app.services.outlook_structured.revenue_q4_runtime_input import build_revenue_q4_runtime_input


CIK = "0001045810"
PERIODS = {"FY": ("2025-01-01", "2025-12-31"), "Q1": ("2025-01-01", "2025-03-31"),
    "Q2": ("2025-04-01", "2025-06-30"), "Q3": ("2025-07-01", "2025-09-30")}
VALUES = {"FY": "1000", "Q1": "200", "Q2": "220", "Q3": "240"}


def html(role, *, concept="Revenues", taxonomy=2025, value=None, cik=CIK,
        start=None, end=None, currency="USD", entity=None, fiscal_year=2025):
    start = start or PERIODS[role][0]; end = end or PERIODS[role][1]
    form = "10-K" if role == "FY" else "10-Q"; entity = entity or cik
    return f'''<html xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:dei="http://xbrl.sec.gov/dei/2025"
 xmlns:us-gaap="http://fasb.org/us-gaap/{taxonomy}" xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
 <body><ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">{fiscal_year}</ix:nonNumeric>
 <ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">{role}</ix:nonNumeric>
 <ix:nonNumeric name="dei:DocumentPeriodEndDate" contextRef="ctx">{end}</ix:nonNumeric>
 <ix:nonNumeric name="dei:DocumentType" contextRef="ctx">{form}</ix:nonNumeric>
 <xbrli:context id="ctx"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{entity}</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:unit id="usd"><xbrli:measure>iso4217:{currency}</xbrli:measure></xbrli:unit>
 <ix:nonFraction name="us-gaap:{concept}" contextRef="ctx" unitRef="usd" decimals="INF">{value or VALUES[role]}</ix:nonFraction>
 </body></html>'''.encode()


def inputs(*, concepts=None, taxonomies=None, bodies=None):
    ends = {role: date.fromisoformat(PERIODS[role][1]) for role in PERIODS}
    request = RevenueFilingSelectionRequest(ticker="TEST", issuer="Synthetic Issuer", cik=CIK,
        target_fiscal_year=2025, quarter_anchors=tuple(RevenueFilingQuarterAnchor(role=role,
            report_period_end=ends[role]) for role in ("Q1", "Q2", "Q3")))
    rows = tuple(SecSubmissionFilingRow(accession=f"{CIK}-25-{index + 1:06d}",
        form="10-K" if role == "FY" else "10-Q", filing_date=ends[role] + timedelta(days=30),
        report_period_end=ends[role], primary_document=f"test-{role.lower()}.htm",
        source_ordinal=index) for index, role in enumerate(("Q1", "Q2", "Q3", "FY")))
    selection = select_revenue_operand_filings(request, SecSubmissionsSelectionInput(
        issuer="Synthetic Issuer", cik=CIK, source_identity="fixture", rows=rows))
    documents = []
    for item in selection.selected_filings:
        role = item.role
        body = ((bodies or {})[role] if bodies is not None and role in bodies else html(role,
            concept=(concepts or {}).get(role, "Revenues"), taxonomy=(taxonomies or {}).get(role, 2025)))
        documents.append(RetrievedRevenueFilingDocument(role=role, selected_document=item.document,
            selection_provenance=item.metadata_provenance, canonical_url=item.document.source_url,
            body=body, byte_length=len(body), fingerprint=hashlib.sha256(body).hexdigest(),
            content_type="text/html", retrieval_policy="revenue-filing-document-retrieval-1",
            cache_state="miss"))
    retrieval = RevenueFilingDocumentBatchResult(policy_version="revenue-filing-document-retrieval-1",
        state="available", issuer=selection.issuer, cik=selection.cik,
        target_fiscal_year=selection.target_fiscal_year, documents=tuple(documents),
        request_accounting=RevenueFilingDocumentRequestAccounting(logical_documents_requested=4,
            http_attempts_charged=4, successes=4, bytes_accepted=sum(len(row.body) for row in documents),
            cache_success_hits=0, cache_failure_hits=0, failures=0))
    return selection, retrieval


def test_a_exact_qname_builds_ready_without_deriving_q4():
    result = build_revenue_q4_runtime_input(*inputs())
    assert result.state == "ready" and result.derivation_input is not None
    assert [row.role for row in result.operand_evidence] == ["FY", "Q1", "Q2", "Q3"]
    assert result.partition.residual_period_start == date(2025, 10, 1)
    assert not hasattr(result.derivation_input, "observation")


@pytest.mark.parametrize("concept", ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"])
def test_b_c_certified_cross_version_equivalence_builds_ready(concept):
    result = build_revenue_q4_runtime_input(*inputs(concepts={role: concept for role in PERIODS},
        taxonomies={"FY": 2024}))
    assert result.state == "ready"
    assert result.partition.concept_identity.state == "certified_cross_version_equivalence"
    assert result.partition.concept_identity.certified_records


def test_d_unsupported_cross_version_local_name_conflicts():
    result = build_revenue_q4_runtime_input(*inputs(
        concepts={role: "SalesRevenueNet" for role in PERIODS}, taxonomies={"FY": 2024}))
    assert (result.state, result.reason, result.partition.state) == (
        "conflict", "partition_conflict", "conflict")


def test_e_selection_not_selected_is_unavailable():
    selection, retrieval = inputs()
    selection = selection.model_copy(update={"state": "unavailable", "reason": "quarter_filing_missing",
        "selected_filings": ()})
    assert build_revenue_q4_runtime_input(selection, retrieval).reason == "selection_unavailable"


def test_f_retrieval_unavailable_is_unavailable():
    selection, retrieval = inputs()
    retrieval = retrieval.model_copy(update={"state": "unavailable", "reason": "http_404", "documents": ()})
    assert build_revenue_q4_runtime_input(selection, retrieval).reason == "retrieval_unavailable"


@pytest.mark.parametrize(("mutation", "reason"), [
    ("role", "role_set_invalid"), ("accession", "identity_mismatch"),
    ("document", "identity_mismatch"), ("issuer", "identity_mismatch"),
    ("year", "identity_mismatch"), ("length", "document_integrity_conflict"),
    ("sha", "document_integrity_conflict"), ("retrieval_policy", "retrieval_policy_unsupported"),
    ("selection_policy", "selection_policy_unsupported"),
])
def test_g_o_upstream_identity_integrity_and_policy_conflicts(mutation, reason):
    selection, retrieval = inputs()
    if mutation == "role":
        retrieval = retrieval.model_copy(update={"documents": retrieval.documents[:3]})
    elif mutation == "retrieval_policy":
        retrieval = retrieval.model_copy(update={"policy_version": "unsupported"})
    elif mutation == "selection_policy":
        selection = selection.model_copy(update={"policy_version": "unsupported"})
    else:
        first = retrieval.documents[0]
        if mutation == "length": first = first.model_copy(update={"byte_length": first.byte_length + 1})
        elif mutation == "sha": first = first.model_copy(update={"fingerprint": "0" * 64})
        else:
            changes = {"accession": "0001045810-25-999999"} if mutation == "accession" else (
                {"primary_document": "other.htm"} if mutation == "document" else (
                {"issuer": "Other"} if mutation == "issuer" else {"target_fiscal_year": 2026}))
            first = first.model_copy(update={"selected_document": first.selected_document.model_copy(update=changes)})
        retrieval = retrieval.model_copy(update={"documents": (first, *retrieval.documents[1:])})
    result = build_revenue_q4_runtime_input(selection, retrieval)
    assert (result.state, result.reason) == ("conflict", reason)


@pytest.mark.parametrize(("role", "body", "state"), [
    ("FY", b"not xbrl", "unavailable"), ("Q1", b"not xbrl", "unavailable"),
    ("Q2", html("Q2").replace(b"220", b"220</ix:nonFraction><ix:nonFraction name=\"us-gaap:Revenues\" contextRef=\"ctx\" unitRef=\"usd\" decimals=\"INF\">221"), "conflict"),
    ("Q3", b"<html>", "unavailable"),
])
def test_p_t_qualification_failure_is_role_specific_and_fail_closed(role, body, state):
    selection, retrieval = inputs(bodies={role: body})
    result = build_revenue_q4_runtime_input(selection, retrieval)
    assert result.failed_role == role and result.derivation_input is None
    assert result.state == state


@pytest.mark.parametrize(("kind", "expected_reason"), [
    ("concept", "partition_conflict"), ("unit", "partition_conflict"),
    ("entity", "partition_conflict"), ("dimensions", "partition_conflict"),
    ("basis", "partition_conflict"), ("year", "partition_conflict"),
    ("geometry", "partition_conflict"),
])
def test_u_aa_partition_conflicts_are_preserved(kind, expected_reason):
    selection, retrieval = inputs()
    from app.models.outlook_inline_revenue import RevenueOperandPartitionResult
    def partition_validator(**operands):
        return RevenueOperandPartitionResult(
            partition_policy_version="revenue-operand-partition-identity-2",
            state="conflict", reasons=(f"{kind}_mismatch",))
    result = build_revenue_q4_runtime_input(selection, retrieval,
        partition_validator=partition_validator)
    assert result.state == "conflict" and result.reason == expected_reason
    assert result.partition.state == "conflict" and len(result.operand_evidence) == 4


def test_ab_ae_ready_preserves_residual_fingerprints_policies_and_partition_provenance():
    selection, retrieval = inputs(taxonomies={"FY": 2024})
    result = build_revenue_q4_runtime_input(selection, retrieval)
    assert result.partition.residual_period_start == date(2025, 10, 1)
    assert [row.document_sha256 for row in result.operand_evidence] == [row.fingerprint for row in retrieval.documents]
    assert all(row.qualifier_policy == "sec-inline-xbrl-revenue-operand-2" for row in result.operand_evidence)
    assert result.partition.partition_policy_version == "revenue-operand-partition-identity-2"
    assert result.partition.concept_identity.certified_records


def test_evidence_fingerprint_is_deterministic_and_semantic():
    first = build_revenue_q4_runtime_input(*inputs())
    second = build_revenue_q4_runtime_input(*inputs())
    changed = build_revenue_q4_runtime_input(*inputs(bodies={"Q3": html("Q3", value="241")}))
    assert first.evidence_fingerprint == second.evidence_fingerprint
    assert first.evidence_fingerprint != changed.evidence_fingerprint


def retained_fixture_inputs(ticker, year):
    root = Path(__file__).parents[2] / "docs" / "diagnostics"
    manifest = json.loads((root / "phase6b5c2a5w2-inline-revenue-metadata-20261001.json").read_text())
    certified = json.loads((root / "phase6b5c2a5w10a-schema2-live-revenue-partition-certification-20261002.json").read_text())
    manifest_rows = [row for row in manifest["manifest"]["roles"] if row["ticker"] == ticker]
    evidence_rows = [row for row in certified["roles"] if row["ticker"] == ticker]
    evidence_by_role = {row["role"]: row for row in evidence_rows}
    selected = tuple(SelectedRevenueFiling(role=row["expected_role"],
        document=SelectedFilingDocument.model_validate(row),
        metadata_provenance=FilingMetadataProvenance(source_identity="retained-5y3",
            source_ordinals=(index,))) for index, row in enumerate(manifest_rows))
    selection = RevenueFilingSelectionResult(policy_version="revenue-operand-filing-selection-1",
        issuer=selected[0].document.issuer, cik=selected[0].document.cik,
        target_fiscal_year=year, state="selected", selected_filings=selected)
    documents = []
    for item in selected:
        retained = evidence_by_role[item.role]
        replay = retained["partition_replay_evidence"]
        namespace = replay["expanded_qname"]["namespace_uri"]
        concept = replay["expanded_qname"]["local_name"]
        context = replay["context"]
        body = html(item.role, concept=concept, taxonomy=int(namespace.rsplit("/", 1)[1]),
            value=retained["qualified_operand"]["exact_decimal_value"], cik=item.document.cik,
            entity=context["entity_value"], start=context["period_start"], end=context["period_end"],
            fiscal_year=year)
        documents.append(RetrievedRevenueFilingDocument(role=item.role,
            selected_document=item.document, selection_provenance=item.metadata_provenance,
            canonical_url=item.document.source_url, body=body, byte_length=len(body),
            fingerprint=hashlib.sha256(body).hexdigest(), content_type="text/html",
            retrieval_policy="revenue-filing-document-retrieval-1", cache_state="miss"))
    retrieval = RevenueFilingDocumentBatchResult(policy_version="revenue-filing-document-retrieval-1",
        state="available", issuer=selection.issuer, cik=selection.cik,
        target_fiscal_year=year, documents=tuple(documents),
        request_accounting=RevenueFilingDocumentRequestAccounting(logical_documents_requested=4,
            cache_success_hits=0, cache_failure_hits=0, http_attempts_charged=0,
            successes=4, failures=0, bytes_accepted=sum(len(row.body) for row in documents)))
    partition = next(row for row in certified["partitions"] if row["ticker"] == ticker)
    return selection, retrieval, evidence_by_role, partition


@pytest.mark.parametrize(("ticker", "year"), [("AAPL", 2025), ("NVDA", 2026)])
def test_aapl_nvda_fixture_based_runtime_certification_matches_reviewed_partition(ticker, year):
    selection, retrieval, reviewed, reviewed_partition = retained_fixture_inputs(ticker, year)
    result = build_revenue_q4_runtime_input(selection, retrieval)
    assert result.state == "ready"
    assert [row.role for row in result.operand_evidence] == ["FY", "Q1", "Q2", "Q3"]
    for row in result.operand_evidence:
        expected = reviewed[row.role]
        operand = row.qualified_operand
        assert str(operand.numeric.normalized_value) == expected["qualified_operand"]["exact_decimal_value"]
        assert operand.expanded_qname.model_dump(mode="json") == expected["partition_replay_evidence"]["expanded_qname"]
        assert operand.context.entity_value == expected["partition_replay_evidence"]["context"]["entity_value"]
        assert operand.unit.currency == expected["partition_replay_evidence"]["canonical_unit"]["currency"]
        assert operand.accounting_basis == "gaap" and not operand.context.explicit_dimensions
    assert result.partition.residual_period_start.isoformat() == reviewed_partition["residual_period_start"]
    assert result.partition.residual_period_end.isoformat() == reviewed_partition["residual_period_end"]
    assert result.partition.concept_identity.model_dump(mode="json") == reviewed_partition["concept_identity"]


def test_af_ak_source_has_no_replay_arithmetic_network_or_wiring_dependency():
    source = (Path(__file__).parents[1] / "app/services/outlook_structured/revenue_q4_runtime_input.py").read_text()
    for forbidden in ("certified_artifact", "replay_certification", "AAPL", "NVDA",
            "derive_revenue_q4", "FY -", "urlopen", "requests.", "configured_providers",
            "AIAnalysis", "POST /outlook"):
        assert forbidden not in source
