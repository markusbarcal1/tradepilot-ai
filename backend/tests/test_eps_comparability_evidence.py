"""Offline SEC filing-evidence retrieval and EPS comparability integration tests."""
from datetime import datetime, timezone

from app.config import Settings
from app.services.outlook_structured.eps_comparability_evidence import (
    EpsComparabilityEvidenceResult, EpsComparabilityEvidenceService,
    MAX_EXTRACTED_TEXT_CHARS, _certify_document,
)
from app.services.outlook_structured.revenue_filing_document import (
    DocumentTransportError, DocumentTransportResponse, RevenueFilingDocumentRetriever,
)
from app.services.outlook_structured.sec_history import SecHistoricalFinancialProvider, normalize_companyfacts
from tests.test_eps_history_certification import NOW, annual, payload


NVDA_HTML = b"""<html><body><p>In June 2024, we executed a ten-for-one stock split of our common stock.
All share, equity award, and per share amounts presented herein have been retroactively adjusted
to reflect the Stock Split.</p></body></html>"""


class Gate:
    def __init__(self): self.calls = 0
    def wait(self, interval): self.calls += 1


class Transport:
    def __init__(self, outcome=NVDA_HTML): self.outcome, self.calls = outcome, []
    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.outcome, BaseException): raise self.outcome
        body = self.outcome
        return DocumentTransportResponse(200, url, body, "text/html", len(body))


def split_inputs():
    original = annual(2024, "11.93", start="2023-01-30", end="2024-01-28",
        filed="2024-02-21", accn="0001045810-24-000029")
    current = annual(2025, "2.94", start="2024-01-29", end="2025-01-26",
        filed="2025-02-26", accn="0001045810-25-000023")
    comparative = annual(2025, "1.19", start=original["start"], end=original["end"],
        filed=current["filed"], accn=current["accn"])
    companyfacts, submissions = payload(diluted=[original, current, comparative])
    recent = submissions["filings"]["recent"]
    recent["reportDate"][recent["accessionNumber"].index(current["accn"])] = current["end"]
    return companyfacts, submissions


def preliminary():
    companyfacts, submissions = split_inputs()
    return normalize_companyfacts(companyfacts, submissions, "NVDA", NOW)


def service(outcome=NVDA_HTML, *, max_requests=2):
    transport, gate = Transport(outcome), Gate()
    retriever = RevenueFilingDocumentRetriever(transport, user_agent="TradePilot test@example.com",
        request_interval=0, rate_gate=gate)
    return EpsComparabilityEvidenceService(retriever.retrieve_bound,
        max_requests=max_requests), retriever, transport, gate


def test_nvda_filing_language_certifies_exact_bound_evidence_and_cache_reuse():
    evidence_service, _, transport, gate = service()
    cold = evidence_service.certify(preliminary())
    warm = evidence_service.certify(preliminary())
    assert len(cold.evidence) == 1
    assert cold.evidence[0].accession == "0001045810-25-000023"
    assert cold.evidence[0].action_identities == ("ten-for-one-stock-split",)
    assert cold.evidence[0].adjustment_direction == "split"
    assert cold.http_attempts == 1 and warm.http_attempts == 0 and warm.cache_hits == 1
    assert len(transport.calls) == gate.calls == 1


def test_missing_ambiguous_conflicting_and_truncated_text_fail_closed():
    row = next(item for item in preliminary().annual_eps_source_observations
        if item.disclosure_type == "later_comparative")
    for body, reason in [
        (b"<html><p>A ten-for-one stock split occurred.</p></html>",
            "retrospective_adjustment_statement_missing"),
        (b"<html><p>A ten-for-one stock split and a one-for-five reverse stock split occurred. "
            b"Per share amounts were retrospectively adjusted.</p><p>Per share amounts were "
            b"retrospectively adjusted for a two-for-one stock split.</p></html>",
            "retrospective_adjustment_statement_ambiguous"),
        (("<html><p>ten-for-one stock split; per share amounts were retrospectively adjusted.</p>"
          + "x" * MAX_EXTRACTED_TEXT_CHARS + "</html>").encode(), "document_text_limit_exceeded"),
    ]:
        certified, actual = _certify_document(row, body)
        assert certified is None and actual == reason

    for body, safe_reason in [
        (b"<html><p>A ten-for-one stock split occurred.</p></html>",
            "missing_adjustment_statement"),
        (b"<html><p>A ten-for-one stock split and a one-for-five reverse stock split occurred. "
            b"Per share amounts were retrospectively adjusted.</p><p>Per share amounts were "
            b"retrospectively adjusted for a two-for-one stock split.</p></html>",
            "ambiguous_adjustment_statement"),
    ]:
        evidence_service, _, _, _ = service(body)
        assert evidence_service.certify(preliminary()).reasons == (safe_reason,)


def test_reverse_split_and_multiple_actions_are_explicit_not_numeric_inferences():
    row = next(item for item in preliminary().annual_eps_source_observations
        if item.disclosure_type == "later_comparative")
    reverse, _ = _certify_document(row, b"<p>A one-for-ten reverse stock split was completed. "
        b"All per share amounts were retrospectively adjusted for the one-for-ten reverse stock split.</p>")
    assert reverse.adjustment_direction == "reverse_split"
    multiple, _ = _certify_document(row, b"<p>A two-for-one stock split and a one-for-five reverse stock split occurred. "
        b"All per share amounts were retrospectively adjusted for the two-for-one stock split and "
        b"one-for-five reverse stock split.</p>")
    assert multiple.adjustment_direction == "multiple_actions"


def test_wrong_url_transport_failure_and_budget_exhaustion_preserve_breaks():
    snapshot = preliminary()
    index = next(index for index, item in enumerate(snapshot.annual_eps_source_observations)
        if item.disclosure_type == "later_comparative")
    changed = snapshot.annual_eps_source_observations[index].model_copy(
        update={"source_url": "https://evil.example/report.htm"})
    rows = list(snapshot.annual_eps_source_observations); rows[index] = changed
    wrong = snapshot.model_copy(update={"annual_eps_source_observations": tuple(rows)})
    evidence_service, _, transport, _ = service()
    result = evidence_service.certify(wrong)
    assert result.evidence == () and result.failures == 1 and transport.calls == []
    assert result.reasons == ("invalid_document_binding",)

    failed_service, _, failed_transport, _ = service(DocumentTransportError("http_429"))
    failed = failed_service.certify(snapshot)
    assert failed.evidence == () and failed.http_attempts == 1 and len(failed_transport.calls) == 1

    over_budget, _, over_transport, _ = service(max_requests=0)
    exhausted = over_budget.certify(snapshot)
    assert exhausted.reasons == ("request_budget_exhausted",)
    assert over_transport.calls == []


def test_bound_retrieval_rejects_incorrect_accession_url_pair_before_transport():
    _, retriever, transport, _ = service()
    result = retriever.retrieve_bound(cik="0001045810", accession="0001045810-25-000999",
        primary_document="report.htm",
        source_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/report.htm")
    assert result.state == "conflict" and result.reason == "url_policy_rejected"
    assert transport.calls == []


class JsonClient:
    def __init__(self, companyfacts, submissions):
        self.companyfacts, self.submissions, self.calls = companyfacts, submissions, []
    def get(self, url, **kwargs):
        self.calls.append(url)
        if "company_tickers" in url:
            return {"0": {"ticker": "NVDA", "cik_str": 1045810}}
        return self.companyfacts if "companyfacts" in url else self.submissions


def test_provider_integration_selects_119_and_document_failure_is_eps_local():
    companyfacts, submissions = split_inputs()
    settings = Settings(_env_file=None, environment="test",
        outlook_sec_user_agent="TradePilot test@example.com")
    evidence_service, _, transport, _ = service()
    client = JsonClient(companyfacts, submissions)
    provider = SecHistoricalFinancialProvider(settings, client, lambda: NOW, enabled=True,
        eps_evidence_enabled=True, eps_evidence_loader=evidence_service.certify)
    acquisition = provider.get_acquisition("NVDA")
    assert [str(row.exact_eps) for row in acquisition.snapshot.annual_eps_observations] == ["1.19", "2.94"]
    assert acquisition.snapshot.annual_eps_observations[1].comparison_break_before is False
    assert acquisition.snapshot.diagnostics.eps_document_http_attempts == 1
    assert acquisition.snapshot.diagnostics.eps_document_evidence_state == "available"
    assert acquisition.snapshot.diagnostics.eps_document_failure_reasons == ()
    assert len(client.calls) == 3 and len(transport.calls) == 1
    assert provider.get_acquisition("NVDA").http_attempts == 0

    failed_service, _, _, _ = service(DocumentTransportError("http_500"))
    failed_provider = SecHistoricalFinancialProvider(settings, JsonClient(companyfacts, submissions),
        lambda: NOW, enabled=True, eps_evidence_enabled=True,
        eps_evidence_loader=failed_service.certify)
    failed = failed_provider.get_acquisition("NVDA").snapshot
    assert [str(row.exact_eps) for row in failed.annual_eps_observations] == ["11.93", "2.94"]
    assert failed.annual_eps_observations[1].comparison_break_before is True
    assert failed.annual_revenue_observations == ()
    assert failed.diagnostics.eps_document_evidence_state == "rejected"
    assert failed.diagnostics.eps_document_failures == 1
    assert failed.diagnostics.eps_document_failure_reasons == ("document_unavailable",)


def test_partial_rejection_preserves_certified_observations_and_safe_reason():
    companyfacts, submissions = split_inputs()
    settings = Settings(_env_file=None, environment="test",
        outlook_sec_user_agent="TradePilot test@example.com")
    proof = service()[0].certify(preliminary()).evidence[0]
    result = EpsComparabilityEvidenceResult(evidence=(proof,), logical_documents=2,
        http_attempts=2, failures=1, reasons=("ambiguous_adjustment_statement",))
    provider = SecHistoricalFinancialProvider(settings, JsonClient(companyfacts, submissions),
        lambda: NOW, enabled=True, eps_evidence_enabled=True, eps_evidence_loader=lambda _: result)
    snapshot = provider.get_acquisition("NVDA").snapshot
    assert [str(row.exact_eps) for row in snapshot.annual_eps_observations] == ["1.19", "2.94"]
    assert snapshot.diagnostics.eps_document_evidence_state == "partial"
    assert snapshot.diagnostics.eps_document_failures == 1
    assert snapshot.diagnostics.eps_document_failure_reasons == ("ambiguous_adjustment_statement",)


def test_budget_and_unexpected_loader_failures_are_explicit_and_fail_closed():
    companyfacts, submissions = split_inputs()
    settings = Settings(_env_file=None, environment="test",
        outlook_sec_user_agent="TradePilot test@example.com")
    cases = [
        (lambda _: EpsComparabilityEvidenceResult(logical_documents=3, failures=1,
            reasons=("request_budget_exhausted",)), "budget_exhausted", "request_budget_exhausted"),
        (lambda _: (_ for _ in ()).throw(RuntimeError("secret accession and EPS 11.93")),
            "loader_error", "loader_error"),
    ]
    for loader, state, reason in cases:
        provider = SecHistoricalFinancialProvider(settings, JsonClient(companyfacts, submissions),
            lambda: NOW, enabled=True, eps_evidence_enabled=True, eps_evidence_loader=loader)
        snapshot = provider.get_acquisition("NVDA").snapshot
        assert [str(row.exact_eps) for row in snapshot.annual_eps_observations] == ["11.93", "2.94"]
        assert snapshot.annual_eps_observations[1].comparison_break_before is True
        assert snapshot.diagnostics.eps_document_evidence_state == state
        assert snapshot.diagnostics.eps_document_failures == 1
        assert snapshot.diagnostics.eps_document_failure_reasons == (reason,)
        serialized = snapshot.diagnostics.model_dump_json()
        assert "secret accession" not in serialized and "11.93" not in serialized


def test_aapl_like_unchanged_comparative_needs_no_document_request():
    original = annual(2024, "6.08", start="2023-10-01", end="2024-09-28",
        filed="2024-11-01", accn="0001045810-24-000123")
    current = annual(2025, "7.46", start="2024-09-29", end="2025-09-27",
        filed="2025-10-31", accn="0001045810-25-000079")
    comparative = annual(2025, "6.08", start=original["start"], end=original["end"],
        filed=current["filed"], accn=current["accn"])
    companyfacts, submissions = payload(diluted=[original, current, comparative])
    recent = submissions["filings"]["recent"]
    recent["reportDate"][recent["accessionNumber"].index(current["accn"])] = current["end"]
    snapshot = normalize_companyfacts(companyfacts, submissions, "AAPL", NOW)
    evidence_service, _, transport, _ = service()
    result = evidence_service.certify(snapshot)
    assert result.logical_documents == 0 and result.evidence == () and transport.calls == []
