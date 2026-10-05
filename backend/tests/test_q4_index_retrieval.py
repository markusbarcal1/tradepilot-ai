"""Fixture-only tests for versioned SEC filing-index discovery."""
from copy import deepcopy
import inspect
import json

import pytest

from app.cli.certify_q4_index_retrieval import main as cli_main
from app.services.outlook_structured.q4_candidate_retrieval import CandidateRetrievalRunner
from app.services.outlook_structured.q4_certification import FixtureTransport
from app.services.outlook_structured.q4_filing_index import (
    discover_index_earnings_exhibits, normalize_exhibit_type,
)
from app.services.outlook_structured.q4_index_retrieval import (
    AGGREGATE_LIMIT, CLASS_LIMITS, INDEX_RETRIEVAL_ACKNOWLEDGMENT, PER_ISSUER_LIMIT,
    RUNNER_VERSION, IndexEnabledCandidateRetrievalRunner, IndexRetrievalBudget,
    _index_url, validate_index_retrieval_live_gate,
)
from app.services.outlook_structured.transport import ProviderUnavailable
from tests.test_q4_candidate_retrieval import fixture, release


def index_fixture(*, entries=(), primary_sufficient=False, primary_relationship=False,
        index_failure=None, exhibit_failure=None, basic=False, conflicting=False):
    payload = fixture(primary_sufficient=primary_sufficient,
        no_exhibit=not primary_relationship, basic=basic, conflicting=conflicting)
    if primary_sufficient or primary_relationship:
        return payload
    primary_urls = [url for url in payload["responses"] if "/eight-" in url]
    for primary_url in primary_urls:
        index_url = primary_url.rsplit("/", 1)[0] + "/index.json"
        payload["responses"][index_url] = index_failure or {
            "json": {"directory": {"item": [dict(item) for item in entries]}}}
        for item in entries:
            name = item.get("name")
            if isinstance(name, str) and "/" not in name and ".." not in name:
                exhibit_url = primary_url.rsplit("/", 1)[0] + "/" + name
                target = next(target for target in __import__(
                    "app.services.outlook_structured.q4_certification", fromlist=["MANIFEST"]
                    ).MANIFEST if f"eight-{target.fiscal_year}.htm" in primary_url)
                payload["responses"][exhibit_url] = exhibit_failure or {
                    "body": release(target, basic=basic, conflicting=conflicting)}
    return payload


def run(payload, **changes):
    transport = FixtureTransport(payload["responses"])
    runner = IndexEnabledCandidateRetrievalRunner(transport,
        user_agent="TradePilot offline operator@example.com", **changes)
    return runner.run(), transport


@pytest.mark.parametrize("raw,normalized", [("EX-99", "EX-99"), ("ex-99.1", "EX-99.1"),
    ("EX-99.01", "EX-99.1"), ("EX-99.001", "EX-99.1"), ("EX-10.1", None),
    ("EX-99.A", None)])
def test_ex99_normalization_is_narrow(raw, normalized):
    assert normalize_exhibit_type(raw) == normalized


def test_index_parser_uses_sequential_bounded_metadata_only():
    result = discover_index_earnings_exhibits({"directory": {"item": [
        {"name": "../unsafe.htm", "type": "EX-99.1", "description": "earnings release"},
        {"name": "safe.htm", "type": "EX-10.1", "description": "earnings release"},
        {"name": "other.htm", "type": "EX-99.2", "description": "credit agreement"},
        {"name": "results.htm", "type": "EX-99.01", "description": "Financial Results"},
    ]}})
    assert result.state == "resolved" and result.documents == ("results.htm",)
    assert result.diagnostics["entries_rejected_by_unsafe_identity"] == 1
    assert result.diagnostics["entries_rejected_by_exhibit_type"] == 1
    assert result.diagnostics["entries_rejected_by_description_semantics"] == 1


def test_primary_success_spends_no_index_or_exhibit():
    result, _ = run(index_fixture(primary_sufficient=True))
    assert result["budget"]["attempts"] == 6
    assert result["budget"]["class_attempts"] == {"current_submissions": 2,
        "selected_primary_document": 4, "filing_index": 0, "earnings_exhibit": 0}


def test_primary_relationship_spends_exhibit_without_index():
    result, _ = run(index_fixture(primary_relationship=True))
    assert result["budget"]["class_attempts"]["filing_index"] == 0
    assert result["budget"]["class_attempts"]["earnings_exhibit"] == 4


def test_no_primary_relationship_spends_exactly_one_index_per_target():
    result, _ = run(index_fixture(entries=[]))
    assert result["runner"] == RUNNER_VERSION
    assert result["budget"]["attempts"] == 10
    assert result["budget"]["class_attempts"]["filing_index"] == 4
    assert result["budget"]["class_attempts"]["earnings_exhibit"] == 0
    assert all(row["reason"] == "no_eligible_index_exhibit" for row in result["targets"])


def test_unrelated_ex99_is_unavailable():
    result, _ = run(index_fixture(entries=[{"name": "other.htm", "type": "EX-99.1",
        "description": "Material contract"}]))
    assert all(row["reason"] == "no_eligible_index_exhibit" for row in result["targets"])


def test_one_index_earnings_exhibit_is_retrieved_and_parsed():
    result, _ = run(index_fixture(entries=[{"name": "results.htm", "type": "EX-99.01",
        "description": "Quarterly Financial Results"}]))
    assert result["budget"]["attempts"] == AGGREGATE_LIMIT
    assert result["budget"]["class_attempts"] == CLASS_LIMITS
    assert all(row["reason"] == "exhibit_parser_qualified" for row in result["targets"])
    assert all(row["exhibit"]["parser"]["revenue_available"] for row in result["targets"])
    assert all(row["exhibit"]["parser"]["diluted_eps_available"] for row in result["targets"])


def test_two_index_earnings_exhibits_are_ambiguous_without_retrieval():
    result, _ = run(index_fixture(entries=[
        {"name": "a.htm", "type": "EX-99.1", "description": "Earnings Release"},
        {"name": "b.htm", "type": "EX-99.2", "description": "Financial Results"},
    ]))
    assert all(row["reason"] == "multiple_eligible_index_exhibits" for row in result["targets"])
    assert result["budget"]["class_attempts"]["earnings_exhibit"] == 0


@pytest.mark.parametrize("name", ["../escape.htm", "folder/results.htm",
    "https://evil.example/results.htm", "results.htm?x=1"])
def test_unsafe_external_or_cross_path_document_identity_is_rejected(name):
    result = discover_index_earnings_exhibits({"directory": {"item": [{"name": name,
        "type": "EX-99.1", "description": "Earnings Release"}]}})
    assert result.state == "unavailable"
    assert result.diagnostics["entries_rejected_by_unsafe_identity"] == 1


def test_index_path_is_bound_and_has_no_enumeration_or_search():
    url = _index_url("0000320193", "0000320193-24-000123")
    assert url.endswith("/320193/000032019324000123/index.json")
    assert "?" not in url and "search" not in url
    with pytest.raises(ProviderUnavailable):
        _index_url("0000320193", "../unsafe")


@pytest.mark.parametrize("failure,category", [({"raise": "timeout"}, "timeout"),
    ({"raise": "response_size_rejected", "received_bytes": 1048577}, "response_size_rejected"),
    ({"final_url": "https://evil.example/index.json"}, "redirect_rejected")])
def test_index_transport_failure_is_bounded_and_not_retried(failure, category):
    result, transport = run(index_fixture(entries=[], index_failure=failure))
    assert result["targets"][0]["index"]["transport_outcome"] == category
    first_index = next(url for url in transport.calls if url.endswith("index.json"))
    assert transport.calls.count(first_index) == 1


@pytest.mark.parametrize("failure,category", [({"raise": "timeout"}, "timeout"),
    ({"final_url": "https://evil.example/results.htm"}, "redirect_rejected")])
def test_exhibit_transport_failure_is_bounded_and_not_retried(failure, category):
    result, transport = run(index_fixture(entries=[{"name": "results.htm", "type": "EX-99.1",
        "description": "Earnings Release"}], exhibit_failure=failure))
    assert result["targets"][0]["exhibit"]["transport_outcome"] == category
    exhibit = next(url for url in transport.calls if url.endswith("results.htm"))
    assert transport.calls.count(exhibit) == 1


def test_index_budget_is_nontransferable_and_charge_before_dispatch():
    ledger = IndexRetrievalBudget()
    ledger.charge("AAPL", 2024, "filing_index")
    with pytest.raises(ProviderUnavailable):
        ledger.charge("AAPL", 2024, "filing_index")
    assert ledger.aggregate == 1
    assert PER_ISSUER_LIMIT == 7 and AGGREGATE_LIMIT == 14


def test_basic_eps_conflict_and_parser_incompatibility_remain_fail_closed():
    basic, _ = run(index_fixture(entries=[{"name": "results.htm", "type": "EX-99.1",
        "description": "Earnings Release"}], basic=True))
    assert all(not row["exhibit"]["parser"]["diluted_eps_available"] for row in basic["targets"])
    conflict, _ = run(index_fixture(entries=[{"name": "results.htm", "type": "EX-99.1",
        "description": "Earnings Release"}], conflicting=True))
    assert all(row["exhibit"]["parser"]["conflict_state"] for row in conflict["targets"])


def test_artifact_is_sanitized_and_runner_is_production_isolated():
    result, _ = run(index_fixture(entries=[{"name": "secret-results.htm", "type": "EX-99.1",
        "description": "Secret Earnings Release"}]))
    serialized = json.dumps(result)
    for forbidden in ("secret-results.htm", "Secret Earnings Release", "Fourth Quarter Ended",
            "operator@example.com", "document_url", "response_body", "headers"):
        assert forbidden not in serialized
    from app.services.outlook import configured_providers
    assert all(getattr(provider, "name", None) != RUNNER_VERSION for provider in configured_providers())


@pytest.mark.parametrize("changes,reason", [
    ({"user_agent": "invalid"}, "sec_compliant_user_agent_required"),
    ({"aggregate_budget": 13}, "index_retrieval_budget_mismatch"),
    ({"http_attempts": 2}, "index_retrieval_retries_enabled"),
    ({"follow_redirects": True}, "index_retrieval_redirects_enabled"),
])
def test_preflight_failures_dispatch_nothing(changes, reason):
    transport = FixtureTransport(index_fixture(entries=[])["responses"])
    arguments = {"user_agent": "operator@example.com", **changes}
    runner = IndexEnabledCandidateRetrievalRunner(transport, **arguments)
    with pytest.raises(ProviderUnavailable, match=reason):
        runner.run()
    assert transport.calls == []


def test_new_acknowledgment_and_runner_versions_do_not_mutate_v1():
    with pytest.raises(ProviderUnavailable):
        validate_index_retrieval_live_gate(live=True,
            acknowledgment="I ACKNOWLEDGE THE 10-ATTEMPT Q4 CANDIDATE-RETRIEVAL LIMIT",
            user_agent="operator@example.com")
    validate_index_retrieval_live_gate(live=True,
        acknowledgment=INDEX_RETRIEVAL_ACKNOWLEDGMENT, user_agent="operator@example.com")
    assert CandidateRetrievalRunner.runner_version == "direct-q4-candidate-retrieval-1"


def test_offline_cli_is_versioned_and_non_overwriting(tmp_path, monkeypatch, capsys):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(index_fixture(entries=[])), encoding="utf-8")
    repository = tmp_path / "repository"
    output = repository / "docs" / "diagnostics"
    import app.cli.certify_q4_index_retrieval as cli
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", repository)
    assert cli_main(["--fixture", str(fixture_path), "--output-dir", str(output)]) == 0
    path = capsys.readouterr().out.strip()
    assert "phase6b5c2a5j-index-retrieval-" in path
    assert json.loads(open(path, encoding="utf-8").read())["runner"] == RUNNER_VERSION
