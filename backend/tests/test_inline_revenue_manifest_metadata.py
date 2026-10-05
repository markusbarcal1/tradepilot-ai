"""Offline tests for the two-attempt inline-revenue metadata runner."""
from copy import deepcopy
from datetime import datetime, timezone
import inspect
import json

import pytest

from app.cli.certify_inline_revenue_operands import main as cli_main
from app.services.outlook_structured.inline_revenue_manifest_metadata import (
    ACKNOWLEDGMENT, ANNUAL_TARGETS, ENDPOINTS, MetadataManifestCompletionRunner,
    QUARTERLY_IDENTITIES, RUNNER_VERSION, TARGET_SET, _complete, validate_live_gate,
)
from app.services.outlook_structured.q4_certification import FixtureTransport
from app.services.outlook_structured.transport import ProviderUnavailable


FIXED_NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


def recent(target, **changes):
    row = {"accessionNumber": target.accession, "form": "10-K",
        "reportDate": target.report_period_end.isoformat(), "filingDate":
        "2025-10-31" if target.ticker == "AAPL" else "2026-02-25",
        "primaryDocument": target.primary_document,
        "acceptanceDateTime": "2025-10-31T10:00:00Z" if target.ticker == "AAPL"
            else "2026-02-25T21:00:00Z"}
    row.update(changes)
    return {name: [value] for name, value in row.items()}


def payload(**per_ticker):
    responses = {}
    for target in ANNUAL_TARGETS:
        row = per_ticker.get(target.ticker, recent(target))
        responses[ENDPOINTS[target.ticker]] = {"json": {"filings": {"recent": row}}}
    return {"responses": responses}


def run(data=None, **changes):
    transport = FixtureTransport((data or payload())["responses"])
    runner = MetadataManifestCompletionRunner(transport,
        user_agent="TradePilot operator@example.com", clock=lambda: FIXED_NOW, **changes)
    return runner.run(), transport, runner


def test_exact_aapl_and_nvda_matches_complete_eight_role_manifest():
    result, transport, _ = run()
    assert result["runner"] == RUNNER_VERSION and result["target_set"] == TARGET_SET
    assert result["manifest_ready"] is True and len(result["manifest"]["roles"]) == 8
    assert [row["state"] for row in result["annual_results"]] == ["completed", "completed"]
    assert transport.calls == [ENDPOINTS["AAPL"], ENDPOINTS["NVDA"]]
    assert [row["expected_role"] for row in result["manifest"]["roles"]] == [
        "FY", "Q1", "Q2", "Q3", "FY", "Q1", "Q2", "Q3"]


@pytest.mark.parametrize("ticker", ["AAPL", "NVDA"])
def test_missing_issuer_row_keeps_manifest_incomplete(ticker):
    data = payload(); data["responses"][ENDPOINTS[ticker]]["json"]["filings"]["recent"] = {
        name: [] for name in ("accessionNumber", "form", "reportDate", "filingDate", "primaryDocument")}
    result, _, _ = run(data)
    row = next(item for item in result["annual_results"] if item["ticker"] == ticker)
    assert row["state"] == "missing_identity" and row["failure_reason"] == "accession_mismatch"
    assert result["manifest"] is None and result["failure_reasons"] == ["manifest_incomplete"]


def test_duplicate_exact_matches_are_ambiguous():
    data = payload(); target = ANNUAL_TARGETS[0]
    data["responses"][ENDPOINTS["AAPL"]]["json"]["filings"]["recent"] = {
        name: values * 2 for name, values in recent(target).items()}
    result, _, _ = run(data)
    assert result["annual_results"][0]["state"] == "ambiguous_identity"
    assert result["annual_results"][0]["exact_match_count"] == 2


@pytest.mark.parametrize("field,replacement,reason", [
    ("accessionNumber", "0000320193-25-000080", "accession_mismatch"),
    ("form", "10-K/A", "form_mismatch"),
    ("reportDate", "2025-09-28", "report_period_mismatch"),
    ("primaryDocument", "other.htm", "primary_document_mismatch"),
    ("filingDate", "", "filing_date_missing"),
])
def test_identity_mismatches_fail_closed(field, replacement, reason):
    target = ANNUAL_TARGETS[0]
    selected, state, actual, _ = _complete(target, {"filings": {"recent": recent(
        target, **{field: replacement})}})
    assert selected is None and actual == reason and state != "completed"


@pytest.mark.parametrize("body,reason", [
    (b"{bad", "invalid_json"),
    (json.dumps({"filings": {"recent": {}}}).encode(), "metadata_schema_invalid"),
])
def test_malformed_json_and_schema_are_sanitized(body, reason):
    data = payload(); data["responses"][ENDPOINTS["AAPL"]] = {"body": body}
    result, _, _ = run(data)
    assert result["annual_results"][0]["failure_reason"] == reason
    assert body.decode(errors="ignore") not in json.dumps(result)


def test_forbidden_endpoint_dispatches_nothing_and_charges_nothing():
    result, transport, runner = run()
    assert result["budget"]["attempts_charged"] == 2
    fresh = MetadataManifestCompletionRunner(FixtureTransport({}), user_agent="test@example.com")
    with pytest.raises(ProviderUnavailable, match="endpoint_not_allowed"):
        fresh._get("AAPL", "https://www.sec.gov/Archives/file.htm")
    assert fresh.attempts == {"AAPL": 0, "NVDA": 0} and fresh.transport.calls == []


@pytest.mark.parametrize("failure", ["redirect_rejected", "timeout", "transport_failure"])
def test_transport_failures_charge_once_without_retry(failure):
    data = payload(); data["responses"][ENDPOINTS["AAPL"]] = {"raise": failure}
    result, transport, _ = run(data)
    assert transport.calls.count(ENDPOINTS["AAPL"]) == 1 and len(transport.calls) == 2
    assert result["budget"] == {"maximum": 2, "attempts_charged": 2,
        "per_issuer_maximum": 1, "per_issuer": {"AAPL": 1, "NVDA": 1}}
    assert result["requests"][0]["transport_outcome"] == failure


def test_http_and_response_size_failures_are_bounded():
    data = payload(); data["responses"][ENDPOINTS["AAPL"]] = {"status": 503, "body": "bounded"}
    result, _, _ = run(data)
    assert result["requests"][0]["transport_outcome"] == "http_error"
    data = payload(); data["responses"][ENDPOINTS["AAPL"]] = {"body": "x" * 101}
    result, transport, _ = run(data, max_bytes=100)
    assert result["requests"][0]["transport_outcome"] == "response_size_rejected"
    assert transport.calls.count(ENDPOINTS["AAPL"]) == 1


def test_budget_is_nontransferable_and_maximum_two():
    _, _, runner = run()
    with pytest.raises(ProviderUnavailable, match="attempt_budget_exhausted"):
        runner._get("AAPL", ENDPOINTS["AAPL"])
    assert runner.attempts == {"AAPL": 1, "NVDA": 1}


def test_quarterly_identities_are_frozen_and_annual_changes_are_only_metadata():
    before = tuple(row.model_dump_json() for row in QUARTERLY_IDENTITIES)
    result, _, _ = run()
    after = tuple(json.dumps(row, sort_keys=True, separators=(",", ":"))
        for row in result["manifest"]["roles"] if row["expected_role"] != "FY")
    expected = tuple(json.dumps(row.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        for row in QUARTERLY_IDENTITIES)
    assert after == expected and before == tuple(row.model_dump_json() for row in QUARTERLY_IDENTITIES)
    for annual, target in zip((row for row in result["manifest"]["roles"] if row["expected_role"] == "FY"), ANNUAL_TARGETS):
        assert (annual["accession"], annual["primary_document"], annual["source_url"]) == (
            target.accession, target.primary_document, target.source_url)


def test_manifest_serialization_and_content_fingerprint_are_deterministic():
    first = run()[0]; second = run()[0]
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert len(first["manifest"]["fingerprint"]) == 64
    assert first["manifest"]["created_at"] == "2026-10-01T12:00:00Z"


def test_artifact_is_sanitized_and_dispatches_no_document_urls():
    data = payload(); recent_payload = data["responses"][ENDPOINTS["AAPL"]]["json"]["filings"]["recent"]
    recent_payload["unrelatedSecret"] = ["DO_NOT_SERIALIZE"]
    result, transport, _ = run(data)
    serialized = json.dumps(result)
    assert "DO_NOT_SERIALIZE" not in serialized and "response_body" not in serialized
    assert all(url.startswith("https://data.sec.gov/submissions/CIK") for url in transport.calls)


def test_exact_acknowledgment_and_user_agent_are_required():
    with pytest.raises(ProviderUnavailable, match="not_authorized"):
        validate_live_gate(live=False, acknowledgment=ACKNOWLEDGMENT, user_agent="x@y.com")
    with pytest.raises(ProviderUnavailable, match="not_authorized"):
        validate_live_gate(live=True, acknowledgment="2", user_agent="x@y.com")
    with pytest.raises(ProviderUnavailable, match="user_agent"):
        validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT, user_agent="invalid")
    validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT,
        user_agent="TradePilot operator@example.com")


def test_offline_cli_fixture_writes_sanitized_artifact(tmp_path, monkeypatch, capsys):
    fixture = tmp_path / "fixture.json"; fixture.write_text(json.dumps(payload()), encoding="utf-8")
    repository = tmp_path / "repository"; output = repository / "docs" / "diagnostics" / "result.json"
    import app.cli.certify_inline_revenue_operands as cli
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", repository)
    assert cli_main(["metadata", "--fixture", str(fixture), "--ack-max-attempts", "2",
        "--targets", "AAPL-FY2025,NVDA-FY2026", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["manifest_ready"] is True
    assert capsys.readouterr().out.strip() == str(output)


def test_runner_has_no_qualifier_q4_eps_provider_database_research_or_ai_dependency():
    import app.services.outlook_structured.inline_revenue_manifest_metadata as module
    source = inspect.getsource(module).lower()
    for forbidden in ("qualify_inline_revenue", "qualify_direct_q4", "earningspershare",
            "configured_providers", "database", "outlook_research", "openai"):
        assert forbidden not in source
