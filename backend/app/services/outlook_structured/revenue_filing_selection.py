"""Pure, offline selection of FY/Q1/Q2/Q3 SEC filing identities."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import re

from app.models.outlook_inline_revenue import SelectedFilingDocument
from app.models.outlook_revenue_filing_selection import (
    FilingMetadataProvenance, RevenueFilingSelectionRequest,
    RevenueFilingSelectionResult, SecSubmissionFilingRow,
    SecSubmissionsSelectionInput, SelectedRevenueFiling,
)


POLICY_VERSION = "revenue-operand-filing-selection-1"
MIN_QUARTER_DAYS = 70
MAX_QUARTER_DAYS = 105
_ACCESSION = re.compile(r"^(\d{10})-\d{2}-\d{6}$")
_DOCUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_ROLE_ORDER = {"FY": 0, "Q1": 1, "Q2": 2, "Q3": 3}


def _result(request, state, reason=None, selected=()):
    return RevenueFilingSelectionResult(policy_version=POLICY_VERSION,
        issuer=request.issuer, cik=request.cik, target_fiscal_year=request.target_fiscal_year,
        state=state, reason=reason, selected_filings=tuple(selected))


def _safe_url(cik: str, accession: str, document: str) -> str:
    return ("https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession.replace('-', '')}/{document}")


def _same_identity(row: SecSubmissionFilingRow):
    return (row.accession, row.form, row.filing_date, row.report_period_end,
        row.primary_document)


def select_revenue_operand_filings(
    request: RevenueFilingSelectionRequest,
    submissions: SecSubmissionsSelectionInput,
) -> RevenueFilingSelectionResult:
    """Select four identities using explicit fiscal anchors and submissions rows only."""
    if not request.issuer.strip() or not request.cik.strip():
        return _result(request, "unavailable", "issuer_identity_missing")
    if submissions.issuer is None or submissions.cik is None:
        return _result(request, "unavailable", "issuer_identity_missing")
    if submissions.issuer != request.issuer or submissions.cik != request.cik:
        return _result(request, "conflict", "issuer_mismatch")
    if not re.fullmatch(r"\d{10}", request.cik):
        return _result(request, "conflict", "issuer_mismatch")

    anchors = {anchor.role: anchor.report_period_end for anchor in request.quarter_anchors}
    if set(anchors) != {"Q1", "Q2", "Q3"}:
        return _result(request, "conflict", "quarter_order_invalid")
    ends = [anchors[role] for role in ("Q1", "Q2", "Q3")]
    if ends != sorted(ends) or any(not MIN_QUARTER_DAYS <= (b - a).days <= MAX_QUARTER_DAYS
            for a, b in zip(ends, ends[1:])):
        return _result(request, "conflict", "quarter_order_invalid")

    # A row without its period cannot be safely excluded from any requested role.
    supported = [row for row in submissions.rows if row.form in
        {"10-Q", "10-Q/A", "10-K", "10-K/A"}]
    if any(row.report_period_end is None for row in supported):
        return _result(request, "unavailable", "report_period_missing")

    deduped = {}
    ordinals = defaultdict(list)
    for row in supported:
        identity = _same_identity(row)
        deduped.setdefault(identity, row)
        ordinals[identity].append(row.source_ordinal)
    rows = tuple(deduped.values())

    role_rows = {role: [row for row in rows if row.report_period_end == period]
        for role, period in anchors.items()}
    annual_rows = [row for row in rows if row.form in {"10-K", "10-K/A"}
        and row.report_period_end is not None
        and MIN_QUARTER_DAYS <= (row.report_period_end - ends[-1]).days <= MAX_QUARTER_DAYS]
    role_rows["FY"] = annual_rows

    chosen = {}
    for role in ("Q1", "Q2", "Q3", "FY"):
        candidates = role_rows[role]
        allowed = {"10-K", "10-K/A"} if role == "FY" else {"10-Q", "10-Q/A"}
        candidates = [row for row in candidates if row.form in allowed]
        if any(row.form and row.form.endswith("/A") for row in candidates):
            return _result(request, "ambiguous", "amendment_ambiguous")
        originals = [row for row in candidates if row.form in {"10-Q", "10-K"}]
        if not originals:
            return _result(request, "unavailable",
                "annual_filing_missing" if role == "FY" else "quarter_filing_missing")
        if len(originals) > 1:
            return _result(request, "ambiguous",
                "multiple_annual_candidates" if role == "FY" else "multiple_quarter_candidates")
        chosen[role] = originals[0]

    if not (ends[0] < ends[1] < ends[2] < chosen["FY"].report_period_end):
        return _result(request, "conflict", "fiscal_geometry_invalid")

    selected = []
    for role in ("FY", "Q1", "Q2", "Q3"):
        row = chosen[role]
        if row.filing_date is None:
            return _result(request, "unavailable", "filing_date_missing")
        if not row.primary_document:
            return _result(request, "unavailable", "primary_document_missing")
        if not _DOCUMENT.fullmatch(row.primary_document):
            return _result(request, "conflict", "primary_document_invalid")
        match = _ACCESSION.fullmatch(row.accession or "")
        if not match or match.group(1) != request.cik:
            return _result(request, "conflict", "accession_invalid")
        identity = _same_identity(row)
        document = SelectedFilingDocument(ticker=request.ticker, issuer=request.issuer,
            cik=request.cik, target_fiscal_year=request.target_fiscal_year,
            expected_role=role, accession=row.accession, form=row.form,
            filing_date=row.filing_date, acceptance_time=row.acceptance_time,
            report_period_end=row.report_period_end, primary_document=row.primary_document,
            source_url=_safe_url(request.cik, row.accession, row.primary_document),
            source_kind="inline_primary", selector_policy=POLICY_VERSION)
        selected.append(SelectedRevenueFiling(role=role, document=document,
            metadata_provenance=FilingMetadataProvenance(
                source_identity=submissions.source_identity,
                source_ordinals=tuple(sorted(ordinals[identity])))))
    return _result(request, "selected", selected=selected)
