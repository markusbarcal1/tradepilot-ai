from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from threading import Barrier, Event, Lock

import pytest

from app.models.outlook_revenue_filing_selection import (
    FilingMetadataProvenance, RevenueFilingSelectionRequest, SecSubmissionFilingRow,
    SecSubmissionsSelectionInput, SelectedRevenueFiling,
)
from app.services.outlook_structured.revenue_filing_document import (
    DocumentTransportError, DocumentTransportResponse, MAX_RESPONSE_BYTES,
    RevenueFilingDocumentCache, RevenueFilingDocumentRetriever,
)
from app.services.outlook_structured.revenue_filing_selection import select_revenue_operand_filings


CIK = "0000001234"


def selection():
    ends = (date(2025, 3, 31), date(2025, 6, 30), date(2025, 9, 29), date(2025, 12, 29))
    request = RevenueFilingSelectionRequest(ticker="TEST", issuer="Issuer", cik=CIK,
        target_fiscal_year=2025, quarter_anchors=tuple({"role": role, "report_period_end": end}
        for role, end in zip(("Q1", "Q2", "Q3"), ends)))
    rows = tuple(SecSubmissionFilingRow(accession=f"{CIK}-25-{index + 1:06d}",
        form="10-K" if role == "FY" else "10-Q", filing_date=end + timedelta(days=30),
        report_period_end=end, primary_document=f"issuer-{role.lower()}.htm", source_ordinal=index)
        for index, (role, end) in enumerate(zip(("Q1", "Q2", "Q3", "FY"), ends)))
    source = SecSubmissionsSelectionInput(issuer="Issuer", cik=CIK,
        source_identity="fixture", rows=rows)
    return select_revenue_operand_filings(request, source)


class Gate:
    def __init__(self): self.calls = 0
    def wait(self, interval): self.calls += 1


class FakeTransport:
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}; self.calls = []; self.lock = Lock()

    def request(self, url, **kwargs):
        with self.lock: self.calls.append((url, kwargs))
        outcome = self.outcomes.get(url, b"<html>ok</html>")
        if isinstance(outcome, BaseException): raise outcome
        if isinstance(outcome, DocumentTransportResponse): return outcome
        return DocumentTransportResponse(200, url, outcome, "text/html", len(outcome))


def retriever(fake=None, **kwargs):
    fake = fake or FakeTransport(); gate = kwargs.pop("rate_gate", Gate())
    return RevenueFilingDocumentRetriever(fake, rate_gate=gate, request_interval=0,
        user_agent="TradePilotAI test@example.com", **kwargs), fake, gate


def urls(selected): return [row.document.source_url for row in selected.selected_filings]


def test_a_g_selected_batch_has_four_ordered_cold_attempts():
    selected = selection(); service, fake, gate = retriever()
    result = service.retrieve(selected)
    assert result.state == "available"
    assert [row.role for row in result.documents] == ["FY", "Q1", "Q2", "Q3"]
    assert [call[0] for call in fake.calls] == urls(selected)
    assert result.request_accounting.http_attempts_charged == 4
    assert gate.calls == 4


def test_b_non_selected_rejected_before_transport():
    selected = selection().model_copy(update={"state": "unavailable", "reason": "quarter_filing_missing",
        "selected_filings": ()})
    service, fake, _ = retriever()
    result = service.retrieve(selected)
    assert (result.state, result.reason, len(fake.calls)) == ("conflict", "input_not_selected", 0)


def test_c_wrong_role_count_rejected_before_transport():
    selected = selection().model_copy(update={"selected_filings": selection().selected_filings[:3]})
    service, fake, _ = retriever()
    assert service.retrieve(selected).reason == "role_set_invalid"
    assert fake.calls == []


@pytest.mark.parametrize("source_url", [
    "https://evil.example/a.htm", "https://sec.gov/Archives/edgar/data/a.htm",
    "https://www.sec.gov/Archives/edgar/data/1234/wrong/a.htm?x=1",
    "https://user@www.sec.gov/Archives/edgar/data/a.htm",
    "https://www.sec.gov/Archives/edgar/data/1234/%2e%2e/a.htm",
])
def test_d_e_f_url_policy_rejects_untrusted_or_noncanonical_urls(source_url):
    selected = selection(); first = selected.selected_filings[0]
    changed = first.model_copy(update={"document": first.document.model_copy(update={"source_url": source_url})})
    selected = selected.model_copy(update={"selected_filings": (changed, *selected.selected_filings[1:])})
    service, fake, _ = retriever()
    result = service.retrieve(selected)
    assert (result.state, result.reason, fake.calls) == ("conflict", "url_policy_rejected", [])


def test_h_fully_warm_batch_uses_zero_attempts_and_preserves_fingerprints():
    service, fake, gate = retriever(); selected = selection()
    cold = service.retrieve(selected); warm = service.retrieve(selected)
    assert warm.request_accounting.http_attempts_charged == 0
    assert warm.request_accounting.cache_success_hits == 4
    assert [row.fingerprint for row in warm.documents] == [row.fingerprint for row in cold.documents]
    assert len(fake.calls) == gate.calls == 4


def test_i_one_warm_three_cold_is_three_attempts():
    selected = selection(); shared = RevenueFilingDocumentCache()
    service, fake, _ = retriever(cache=shared, failure_ttl=0)
    fake.outcomes[urls(selected)[1]] = DocumentTransportError("http_404")
    service.retrieve(selected)
    del fake.outcomes[urls(selected)[1]]
    result = service.retrieve(selected)
    assert result.request_accounting.cache_success_hits == 1
    assert result.request_accounting.http_attempts_charged == 3


@pytest.mark.parametrize(("position", "reason", "expected"), [(1, "http_404", 1), (2, "http_403", 2)])
def test_j_k_fail_fast_exact_position(position, reason, expected):
    selected = selection(); fake = FakeTransport({urls(selected)[position - 1]: DocumentTransportError(reason)})
    service, _, _ = retriever(fake)
    result = service.retrieve(selected)
    assert result.state == "unavailable" and result.documents == ()
    assert result.request_accounting.http_attempts_charged == expected
    assert result.request_accounting.failure_position == position


@pytest.mark.parametrize(("outcome", "reason"), [
    (DocumentTransportResponse(403, "", b"", "text/html"), "http_403"),
    (DocumentTransportResponse(429, "", b"", "text/html"), "http_429"),
    (DocumentTransportResponse(500, "", b"", "text/html"), "http_5xx"),
    (TimeoutError(), "timeout"), (OSError(), "connection_failure"),
])
def test_l_p_http_and_transport_failures_have_no_retry(outcome, reason):
    selected = selection(); url = urls(selected)[0]
    if isinstance(outcome, DocumentTransportResponse): outcome = outcome.__class__(outcome.status, url, outcome.body, outcome.content_type)
    service, fake, _ = retriever(FakeTransport({url: outcome}))
    result = service.retrieve(selected)
    assert result.reason == reason and len(fake.calls) == 1


@pytest.mark.parametrize(("response", "reason"), [
    (lambda url: DocumentTransportResponse(200, url + "?redirected=1", b"x", "text/html"), "redirect_rejected"),
    (lambda url: DocumentTransportResponse(200, url, b"x", "text/html", MAX_RESPONSE_BYTES + 1), "response_size_rejected"),
    (lambda url: DocumentTransportResponse(200, url, b"x" * (MAX_RESPONSE_BYTES + 1), "text/html"), "response_size_rejected"),
    (lambda url: DocumentTransportResponse(200, url, b"", "text/html"), "empty_response"),
    (lambda url: DocumentTransportResponse(200, url, b"GIF89a", "image/gif"), "content_type_rejected"),
])
def test_q_u_response_validation(response, reason):
    selected = selection(); url = urls(selected)[0]
    service, fake, _ = retriever(FakeTransport({url: response(url)}))
    assert service.retrieve(selected).reason == reason
    assert len(fake.calls) == 1


def test_v_w_sha256_is_exact_and_byte_sensitive():
    selected = selection(); first_url = urls(selected)[0]
    body = b"<html>exact bytes</html>"
    service, _, _ = retriever(FakeTransport({first_url: body}))
    cold = service.retrieve(selected); warm = service.retrieve(selected)
    assert cold.documents[0].fingerprint == hashlib.sha256(body).hexdigest()
    assert cold.documents[0].fingerprint == warm.documents[0].fingerprint
    assert hashlib.sha256(body + b"!").hexdigest() != cold.documents[0].fingerprint


def test_x_y_failure_cache_and_expiry():
    now = [100.0]; selected = selection(); url = urls(selected)[0]
    fake = FakeTransport({url: DocumentTransportError("http_429")})
    service, _, gate = retriever(fake, clock=lambda: now[0], failure_ttl=60)
    assert service.retrieve(selected).request_accounting.http_attempts_charged == 1
    assert service.retrieve(selected).request_accounting.cache_failure_hits == 1
    now[0] += 61
    assert service.retrieve(selected).request_accounting.http_attempts_charged == 1
    assert len(fake.calls) == gate.calls == 2


def test_z_success_ttl_expiry_permits_one_attempt():
    now = [100.0]; selected = selection()
    service, fake, _ = retriever(clock=lambda: now[0], success_ttl=60)
    service.retrieve(selected); assert service.retrieve(selected).request_accounting.http_attempts_charged == 0
    now[0] += 61
    assert service.retrieve(selected).request_accounting.http_attempts_charged == 4
    assert len(fake.calls) == 8


def test_aa_same_key_concurrent_callers_share_one_attempt_per_document():
    selected = selection(); fake = FakeTransport(); service, _, _ = retriever(fake)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.retrieve(selected), range(2)))
    assert all(result.state == "available" for result in results)
    assert len(fake.calls) == 4


def test_ab_different_cache_keys_are_not_globally_locked():
    cache = RevenueFilingDocumentCache(); key1 = ("p", "1"),; key2 = ("p", "2"),
    mode1, _, _ = cache.acquire(key1)
    mode2, _, _ = cache.acquire(key2)
    assert (mode1, mode2) == ("leader", "leader")


def test_ac_ad_gate_only_receives_real_attempts():
    service, _, gate = retriever(); selected = selection()
    service.retrieve(selected); service.retrieve(selected)
    assert gate.calls == 4


class AssertChargedTransport(FakeTransport):
    def __init__(self): super().__init__(); self.service = None
    def request(self, url, **kwargs):
        assert self.service is not None
        raise OSError()


def test_ae_attempt_is_accounted_for_transport_failure():
    fake = AssertChargedTransport(); service, _, _ = retriever(fake); fake.service = service
    result = service.retrieve(selection())
    assert result.request_accounting.http_attempts_charged == 1


def retained_selection(ticker, year):
    root = Path(__file__).parents[2]
    payload = json.loads((root / "docs/diagnostics/phase6b5c2a5w2-inline-revenue-metadata-20261001.json").read_text())
    roles = [row for row in payload["manifest"]["roles"] if row["ticker"] == ticker]
    selected = []
    for row in roles:
        from app.models.outlook_inline_revenue import SelectedFilingDocument
        selected.append(SelectedRevenueFiling(role=row["expected_role"],
            document=SelectedFilingDocument.model_validate(row),
            metadata_provenance=FilingMetadataProvenance(source_identity="retained-5y3",
                source_ordinals=(len(selected),))))
    from app.models.outlook_revenue_filing_selection import RevenueFilingSelectionResult
    return RevenueFilingSelectionResult(policy_version="revenue-operand-filing-selection-1",
        issuer=roles[0]["issuer"], cik=roles[0]["cik"], target_fiscal_year=year,
        state="selected", selected_filings=tuple(selected))


@pytest.mark.parametrize(("ticker", "year"), [("AAPL", 2025), ("NVDA", 2026)])
def test_af_ag_retained_real_identities_fake_transport_certification(ticker, year):
    selected = retained_selection(ticker, year); service, fake, _ = retriever()
    cold = service.retrieve(selected); warm = service.retrieve(selected)
    assert cold.state == warm.state == "available"
    assert cold.request_accounting.http_attempts_charged == 4
    assert warm.request_accounting.http_attempts_charged == 0
    assert len({row.fingerprint for row in cold.documents}) == 1  # same fixture bytes
    assert [row.selection_provenance for row in cold.documents] == [
        row.metadata_provenance for row in selected.selected_filings]
    assert len(fake.calls) == 4


def test_ah_ak_module_has_no_downstream_or_wiring_dependencies():
    source = (Path(__file__).parents[1] / "app/services/outlook_structured/revenue_filing_document.py").read_text()
    for forbidden in ("qualify_inline_revenue_operand", "derive_revenue_q4",
            "reconcile_revenue_q4", "configured_providers", "AIAnalysis", "Decimal("):
        assert forbidden not in source
