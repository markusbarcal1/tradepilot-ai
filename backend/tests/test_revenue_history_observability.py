import json
import logging
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.outlook_revenue_filing_document import RevenueFilingDocumentRequestAccounting
from app.models.outlook_revenue_history_snapshot import (
    RevenueHistorySnapshotResult,
    RevenueSnapshotRequestAccounting,
)
from app.models.outlook_revenue_research import RevenueResearchProjectionResult
from app.services.revenue_history_observability import observe_revenue_snapshot


def settings(*, master=False, q4=False):
    return SimpleNamespace(outlook_historical_revenue_enabled=master,
        outlook_historical_revenue_q4_derivation_enabled=q4)


def available_projection():
    path = Path(__file__).with_name("test_revenue_history_research_dto.py")
    spec = importlib.util.spec_from_file_location("observability_projection_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.projection("AAPL", 2025)


def snapshot(*, state="unavailable", reasons=("feature_disabled",), projection=None,
        cache=None, historical_logical=0, historical_attempts=0, documents=None,
        total_attempts=0, considered=False, attempted=False, target=None):
    return RevenueHistorySnapshotResult(snapshot_policy="revenue-history-snapshot-1",
        ticker="AAPL", state=state, reasons=reasons, projection=projection,
        q4_considered=considered, q4_attempted=attempted, target_fiscal_year=target,
        evidence_fingerprint="0" * 64 if state == "available" else None,
        request_accounting=RevenueSnapshotRequestAccounting(
            acquisition_cache_state=cache,
            historical_logical_requests=historical_logical,
            historical_http_attempts=historical_attempts,
            document_accounting=documents, total_sec_http_attempts=total_attempts))


class Service:
    def __init__(self, value=None, error=None): self.value, self.error = value, error
    def get_snapshot(self, ticker):
        if self.error: raise self.error
        return self.value


@pytest.fixture
def emitted(monkeypatch):
    import app.services.revenue_history_observability as module
    calls = []
    monkeypatch.setattr(module.LOGGER, "log",
        lambda level, message, **kwargs: calls.append((level, message, kwargs)))
    return calls


def event(emitted):
    assert len(emitted) == 1
    level, message, kwargs = emitted[0]
    fields = kwargs["extra"]["revenue_history_event"]
    assert json.loads(message) == fields
    return level, message, fields


def test_a_b_feature_disabled_emits_one_zero_accounting_completion(emitted):
    result = snapshot()
    assert observe_revenue_snapshot(Service(result), "aapl", settings()) is result
    level, _, fields = event(emitted)
    assert level == logging.INFO
    assert fields == {
        "event":"revenue_history_snapshot", "ticker":"AAPL",
        "master_enabled":False, "q4_enabled":False,
        "snapshot_state":"unavailable", "reason_code":"feature_disabled",
        "q4_considered":False, "q4_attempted":False, "target_fy":None,
        "acquisition_cache_state":None, "document_cache_hits":None,
        "document_misses_or_attempted":None, "document_failures":None,
        "historical_logical_requests":0, "historical_http_attempts":0,
        "document_logical_requests":None, "document_http_attempts":None,
        "total_logical_requests":0, "total_http_attempts":0,
        "projection_state":None, "elapsed_ms":fields["elapsed_ms"]}


def test_c_d_direct_available_reports_cache_and_no_documents(emitted):
    projection = available_projection()
    value = snapshot(state="available", reasons=(), projection=projection, cache="miss",
        historical_logical=3, historical_attempts=3, total_attempts=3)
    observe_revenue_snapshot(Service(value), "AAPL", settings(master=True))
    _, _, fields = event(emitted)
    assert fields["snapshot_state"] == fields["projection_state"] == "available"
    assert fields["reason_code"] == "available"
    assert fields["acquisition_cache_state"] == "miss"
    assert fields["historical_logical_requests"] == fields["historical_http_attempts"] == 3
    assert fields["document_http_attempts"] is None


def test_e_f_direct_insufficient_is_expected_and_q4_not_attempted(emitted):
    projection = RevenueResearchProjectionResult(state="unavailable", reasons=("research_eligible_series_required",))
    value = snapshot(state="insufficient_data", reasons=("q4_derivation_disabled",),
        projection=projection, cache="miss", historical_logical=3,
        historical_attempts=3, total_attempts=3)
    observe_revenue_snapshot(Service(value), "AAPL", settings(master=True))
    level, _, fields = event(emitted)
    assert level == logging.INFO
    assert fields["snapshot_state"] == "insufficient_data"
    assert fields["reason_code"] == "q4_derivation_disabled"
    assert fields["q4_attempted"] is False and fields["document_http_attempts"] is None


def test_g_i_q4_success_exposes_bounded_document_accounting_without_values(emitted):
    documents = RevenueFilingDocumentRequestAccounting(logical_documents_requested=4,
        cache_success_hits=1, cache_failure_hits=0, http_attempts_charged=3,
        successes=4, failures=0, bytes_accepted=1234)
    projection = available_projection()
    value = snapshot(state="available", reasons=(), projection=projection, cache="miss",
        historical_logical=3, historical_attempts=3, documents=documents,
        total_attempts=6, considered=True, attempted=True, target=2025)
    observe_revenue_snapshot(Service(value), "AAPL", settings(master=True, q4=True))
    _, _, fields = event(emitted)
    assert fields["q4_considered"] is fields["q4_attempted"] is True
    assert fields["target_fy"] == 2025 and fields["document_cache_hits"] == 1
    assert fields["document_misses_or_attempted"] == fields["document_http_attempts"] == 3
    assert fields["total_logical_requests"] == 7 and fields["total_http_attempts"] == 6
    assert fields["projection_state"] == "available"
    assert "revenue" not in fields and "bytes_accepted" not in fields


def test_j_expected_q4_failure_is_one_info_completion(emitted):
    documents = RevenueFilingDocumentRequestAccounting(logical_documents_requested=2,
        cache_success_hits=1, cache_failure_hits=0, http_attempts_charged=1,
        successes=1, failures=1, bytes_accepted=100, failure_position=2,
        failure_role="Q1", failure_reason="timeout")
    projection = RevenueResearchProjectionResult(state="unavailable", reasons=("research_eligible_series_required",))
    value = snapshot(state="insufficient_data", reasons=("document_retrieval_failed",),
        projection=projection, cache="miss", historical_logical=3,
        historical_attempts=3, documents=documents, total_attempts=4,
        considered=True, attempted=True, target=2025)
    observe_revenue_snapshot(Service(value), "AAPL", settings(master=True, q4=True))
    level, _, fields = event(emitted)
    assert level == logging.INFO and fields["reason_code"] == "document_retrieval_failed"
    assert "outcome" not in fields and fields["document_failures"] == 1


def test_k_warm_cache_is_distinguishable(emitted):
    projection = available_projection()
    documents = RevenueFilingDocumentRequestAccounting(logical_documents_requested=4,
        cache_success_hits=4, cache_failure_hits=0, http_attempts_charged=0,
        successes=4, failures=0, bytes_accepted=400)
    value = snapshot(state="available", reasons=(), projection=projection, cache="success_hit",
        historical_logical=0, historical_attempts=0, documents=documents,
        total_attempts=0, considered=True, attempted=True, target=2025)
    observe_revenue_snapshot(Service(value), "AAPL", settings(master=True, q4=True))
    _, _, fields = event(emitted)
    assert fields["acquisition_cache_state"] == "success_hit"
    assert fields["document_cache_hits"] == 4
    assert fields["historical_http_attempts"] == fields["document_http_attempts"] == fields["total_http_attempts"] == 0


def test_l_n_unexpected_exception_logs_type_only_and_propagates(emitted):
    secret = "token-secret-value https://example.invalid/private?token=x"
    with pytest.raises(RuntimeError, match="token-secret-value"):
        observe_revenue_snapshot(Service(error=RuntimeError(secret)), "aapl",
            settings(master=True, q4=True))
    level, message, fields = event(emitted)
    assert level == logging.ERROR
    assert fields["outcome"] == "unexpected_exception"
    assert fields["exception_type"] == "RuntimeError"
    assert secret not in message and "https://" not in message


def test_o_p_completion_schema_excludes_sensitive_and_financial_fields(emitted):
    observe_revenue_snapshot(Service(snapshot()), "AAPL", settings())
    _, _, fields = event(emitted)
    forbidden = {"revenue", "operands", "qoq", "yoy", "url", "token", "user_id",
        "email", "user_agent", "authorization", "exception_message", "bytes_accepted"}
    assert forbidden.isdisjoint(fields)


def test_logging_failure_does_not_change_valid_result(monkeypatch):
    import app.services.revenue_history_observability as module
    monkeypatch.setattr(module.LOGGER, "log", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("logging failed")))
    value = snapshot()
    assert observe_revenue_snapshot(Service(value), "AAPL", settings()) is value
