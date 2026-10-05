"""One-shot, pre-dispatch-bounded live Q4 revenue certification."""
from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.parse import urlsplit

from app.config import settings
from app.services import revenue_history_runtime
from app.services.outlook_structured import transport
from app.services.outlook_structured.revenue_history_series import adapt_historical_revenue


TICKERS = ("AAPL", "NVDA")
GLOBAL_LIMIT, TICKER_LIMIT = 14, 7
REFERENCES = {"AAPL": "102466000000", "NVDA": "68127000000"}


def _historical_resource(url):
    if url == "https://www.sec.gov/files/company_tickers.json": return "ticker_cik_mapping"
    if url.startswith("https://data.sec.gov/api/xbrl/companyfacts/CIK") and url.endswith(".json"):
        return "company_facts"
    if url.startswith("https://data.sec.gov/submissions/CIK") and url.endswith(".json"):
        return "submissions_recent"
    raise RuntimeError("unauthorized_historical_resource")


def _selection(value):
    return {"policy": value.policy_version, "state": value.state, "reason": value.reason,
        "target_fiscal_year": value.target_fiscal_year,
        "documents": [{"role": row.role, "accession": row.document.accession,
            "form": row.document.form, "filing_date": str(row.document.filing_date),
            "report_date": str(row.document.report_period_end),
            "primary_document": row.document.primary_document,
            "canonical_url": row.document.source_url} for row in value.selected_filings]}


def _acquisition(value):
    history = value.snapshot
    revenue = [row for row in history.observations if row.metric == "revenue"]
    return {"ticker": history.ticker, "issuer": history.issuer, "cik": history.cik,
        "policy": value.acquisition_policy, "fingerprint": value.evidence_fingerprint,
        "cache_state": value.cache_state, "logical_requests": value.logical_requests,
        "http_attempts": value.http_attempts, "accepted_revenue_observations": len(revenue),
        "accepted_fiscal_identities": [f"FY{row.fiscal_year}:{row.fiscal_quarter}" for row in revenue],
        "missing_periods": [row.model_dump(mode="json") for row in history.missing_periods
            if row.metric == "revenue"], "rejected_fact_count": history.diagnostics.rejected_fact_count,
        "submissions_typed_rows": 0 if value.submissions is None else len(value.submissions.rows)}


def _retrieval(value):
    return {"policy": value.policy_version, "state": value.state, "reason": value.reason,
        "accounting": value.request_accounting.model_dump(mode="json"),
        "documents": [{"role": row.role, "accession": row.selected_document.accession,
            "form": row.selected_document.form, "report_date": str(row.selected_document.report_period_end),
            "primary_document": row.selected_document.primary_document,
            "canonical_url": row.canonical_url, "http_status": 200,
            "byte_length": row.byte_length, "sha256": row.fingerprint,
            "media_type": row.content_type, "cache_state": row.cache_state}
            for row in value.documents]}


def _runtime(value):
    operands = []
    for evidence in value.operand_evidence:
        operand = evidence.qualified_operand
        operands.append({"role": evidence.role, "qualifier_state": "qualified",
            "qualifier_policy": evidence.qualifier_policy,
            "qname": operand.expanded_qname.model_dump(mode="json"),
            "exact_decimal": str(operand.numeric.normalized_value),
            "unit": operand.unit.model_dump(mode="json"),
            "entity_scheme": operand.context.entity_scheme, "entity_value": operand.context.entity_value,
            "period_start": str(operand.context.period_start), "period_end": str(operand.context.period_end),
            "duration_days": (operand.context.period_end - operand.context.period_start).days + 1,
            "dimension_count": len(operand.context.explicit_dimensions) + operand.context.typed_dimension_count,
            "accounting_basis": operand.accounting_basis, "reporting_scope": operand.reporting_scope,
            "fiscal_identity": f"FY{operand.target_fiscal_year}:{operand.role}",
            "accession": operand.accession, "primary_document": operand.primary_document,
            "document_sha256": evidence.document_sha256})
    partition = value.partition
    return {"policy": value.builder_policy, "state": value.state, "reason": value.reason,
        "failed_role": value.failed_role,
        "qualification_outcomes": [row.model_dump(mode="json") for row in value.qualification_outcomes],
        "operands": operands, "evidence_fingerprint": value.evidence_fingerprint,
        "partition": None if partition is None else {
            "policy": partition.partition_policy_version, "state": partition.state,
            "reasons": list(partition.reasons),
            "concept_identity": None if partition.concept_identity is None
                else partition.concept_identity.model_dump(mode="json"),
            "residual_start": str(partition.residual_period_start),
            "residual_end": str(partition.residual_period_end),
            "residual_duration_days": partition.residual_duration_days}}


def _snapshot(value):
    derivation, reconciliation, series, projection = (value.derivation, value.reconciliation,
        value.series, value.projection)
    derived = None if derivation is None or derivation.observation is None else derivation.observation
    derivation_input = None if value.runtime_input is None else value.runtime_input.derivation_input
    operands = [] if derivation_input is None else [derivation_input.annual, derivation_input.q1,
        derivation_input.q2, derivation_input.q3]
    return {"state": value.state, "reasons": list(value.reasons),
        "q4_considered": value.q4_considered, "q4_attempted": value.q4_attempted,
        "target_fiscal_year": value.target_fiscal_year, "evidence_fingerprint": value.evidence_fingerprint,
        "request_accounting": value.request_accounting.model_dump(mode="json"),
        "selection": None if value.selection is None else _selection(value.selection),
        "retrieval": None if value.retrieval is None else _retrieval(value.retrieval),
        "runtime": None if value.runtime_input is None else _runtime(value.runtime_input),
        "derivation": None if derivation is None else {"policy": derivation.derivation_policy,
            "state": derivation.state, "reasons": list(derivation.reasons),
            "operands": [{"role": row.role, "exact_decimal": str(row.exact_decimal_value)}
                for row in operands if row is not None],
            "derived_q4_exact_decimal": None if derived is None else str(derived.exact_decimal_value),
            "residual_start": None if derived is None else str(derived.period_start),
            "residual_end": None if derived is None else str(derived.period_end),
            "source_label": None if derived is None else "DERIVED — NOT DIRECTLY REPORTED",
            "reference_exact_decimal": REFERENCES.get(value.ticker),
            "reference_exact_match": derived is not None and str(derived.exact_decimal_value) == REFERENCES.get(value.ticker)},
        "reconciliation": None if reconciliation is None else {
            "policy": reconciliation.reconciliation_policy, "state": reconciliation.state,
            "authoritative_source": reconciliation.authoritative_source_kind,
            "exact_value": None if reconciliation.authoritative_observation is None
                else str(reconciliation.authoritative_observation.exact_decimal_value)},
        "series": None if series is None else {"state": series.state,
            "research_eligible": series.research_eligible, "count": series.observation_count,
            "points": [{"identity": f"FY{row.fiscal_year}:{row.fiscal_period}",
                "exact_decimal": str(row.exact_decimal_value), "source_kind": row.source_kind,
                "source_policy": row.source_policy} for row in series.observations]},
        "projection": None if projection is None else {"state": projection.state,
            "point_count": len(projection.points),
            "qoq_count": 0 if projection.summary is None else projection.summary.available_qoq_comparisons,
            "yoy_count": 0 if projection.summary is None else projection.summary.available_yoy_comparisons,
            "latest_exact_revenue": None if projection.summary is None else str(projection.summary.latest_exact_revenue),
            "latest_qoq": None if projection.summary is None else str(projection.summary.latest_qoq_growth_pct),
            "latest_yoy": None if projection.summary is None else str(projection.summary.latest_yoy_growth_pct)}}


def main():
    original_values = (settings.outlook_historical_revenue_enabled,
        settings.outlook_historical_revenue_q4_derivation_enabled, settings.outlook_http_attempts)
    original_urlopen = transport.urlopen
    requests, active, acquisitions, checkpoints = [], [None], {}, {}

    def authorize(resource, identity):
        ticker = active[0]
        if ticker not in TICKERS or len(requests) >= GLOBAL_LIMIT:
            raise RuntimeError("authorization_budget_exceeded_before_request")
        ticker_rows = [row for row in requests if row["ticker"] == ticker]
        if len(ticker_rows) >= TICKER_LIMIT or any(row["identity"] == identity for row in requests):
            raise RuntimeError("ticker_budget_or_retry_rejected_before_request")
        row = {"ordinal": len(requests) + 1, "ticker": ticker, "resource_type": resource,
            "identity": identity, "attempt": 1, "status": None}
        requests.append(row); return row

    def observed_urlopen(request, *args, **kwargs):
        resource = _historical_resource(request.full_url)
        row = authorize(resource, request.full_url)
        try:
            response = original_urlopen(request, *args, **kwargs)
            row["status"] = getattr(response, "status", None); return response
        except HTTPError as exc:
            row["status"] = exc.code; raise

    output = {"authorization": {"global": GLOBAL_LIMIT, "per_ticker": TICKER_LIMIT},
        "requests": requests, "tickers": {}}
    try:
        settings.outlook_historical_revenue_enabled = True
        settings.outlook_historical_revenue_q4_derivation_enabled = True
        settings.outlook_http_attempts = 1
        revenue_history_runtime.get_revenue_history_snapshot_service.cache_clear()
        service = revenue_history_runtime.get_revenue_history_snapshot_service()
        provider = service.acquire_history.__self__
        retriever = service.retrieve_documents.__self__
        output["cache_before"] = {"ticker_mapping_warm": bool(provider.mapping_cache.entries),
            "AAPL_acquisition_warm": "AAPL" in provider.history_cache.entries,
            "NVDA_acquisition_warm": "NVDA" in provider.history_cache.entries,
            "filing_document_cache_entry_count": len(retriever.cache.entries),
            "selected_identity_cache_state": "not_determinable_before_live_selection"}
        original_acquire, original_select, original_retrieve = (service.acquire_history,
            service.select_filings, service.retrieve_documents)
        original_document_transport = retriever.transport
        allowed_documents = {}

        def capture_acquire(ticker):
            value = original_acquire(ticker)
            acquisitions.setdefault(str(ticker).upper(), value)
            return value

        def capture_select(request, submissions):
            value = original_select(request, submissions)
            checkpoints.setdefault(str(request.ticker).upper(), {})["target"] = {
                "fiscal_year": request.target_fiscal_year,
                "anchors": [{"role": row.role, "report_period_end": str(row.report_period_end)}
                    for row in request.quarter_anchors]}
            checkpoints[str(request.ticker).upper()]["selection"] = _selection(value)
            if value.state == "selected":
                allowed_documents[str(request.ticker).upper()] = {row.document.source_url for row in value.selected_filings}
            return value

        def capture_retrieve(selection):
            ticker = selection.selected_filings[0].document.ticker
            acquisition = acquisitions[ticker]
            adapted = tuple(filter(None, (adapt_historical_revenue(row)
                for row in acquisition.snapshot.observations)))
            direct_series = service.assemble_series(adapted)
            direct_projection = service.project_research(direct_series)
            checkpoints[ticker]["pre_document"] = {"acquisition": _acquisition(acquisition),
                "direct_series_state": direct_series.state,
                "direct_projection_state": direct_projection.state,
                "global_remaining": GLOBAL_LIMIT - len(requests),
                "ticker_remaining": TICKER_LIMIT - sum(row["ticker"] == ticker for row in requests)}
            return original_retrieve(selection)

        class ObservedDocumentTransport:
            def request(self, url, **kwargs):
                ticker = active[0]
                parts = urlsplit(url)
                if (parts.scheme != "https" or parts.hostname != "www.sec.gov"
                        or url not in allowed_documents.get(ticker, set())):
                    raise RuntimeError("unauthorized_filing_document")
                row = authorize("selected_primary_filing_document", url)
                try:
                    response = original_document_transport.request(url, **kwargs)
                    row["status"] = response.status; return response
                except Exception as exc:
                    row["status"] = getattr(exc, "status", None); raise

        service.acquire_history = capture_acquire
        service.select_filings = capture_select
        service.retrieve_documents = capture_retrieve
        retriever.transport = ObservedDocumentTransport()
        transport.urlopen = observed_urlopen
        for ticker in TICKERS:
            active[0] = ticker; before = len(requests)
            row = {"global_remaining_before": GLOBAL_LIMIT - before,
                "ticker_remaining_before": TICKER_LIMIT}
            try:
                first = service.get_snapshot(ticker); after_first = len(requests)
                repeat = service.get_snapshot(ticker); after_repeat = len(requests)
                row.update({"acquisition": _acquisition(acquisitions[ticker]),
                    "checkpoint": checkpoints.get(ticker), "snapshot": _snapshot(first),
                    "warm_repeat": {"additional_http_attempts": after_repeat - after_first,
                        "same_evidence_fingerprint": repeat.evidence_fingerprint == first.evidence_fingerprint,
                        "same_state": repeat.state == first.state,
                        "accounting": repeat.request_accounting.model_dump(mode="json")},
                    "unexpected_exception": None})
            except Exception as exc:
                row["unexpected_exception"] = type(exc).__name__
                row["checkpoint"] = checkpoints.get(ticker)
            row["observed_http_attempts"] = len(requests) - before
            output["tickers"][ticker] = row
        output["global_http_attempts"] = len(requests)
        output["limits_respected"] = len(requests) <= GLOBAL_LIMIT and all(
            sum(row["ticker"] == ticker for row in requests) <= TICKER_LIMIT for ticker in TICKERS)
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
    finally:
        transport.urlopen = original_urlopen
        settings.outlook_historical_revenue_enabled = original_values[0]
        settings.outlook_historical_revenue_q4_derivation_enabled = original_values[1]
        settings.outlook_http_attempts = original_values[2]
        revenue_history_runtime.get_revenue_history_snapshot_service.cache_clear()


if __name__ == "__main__": main()
