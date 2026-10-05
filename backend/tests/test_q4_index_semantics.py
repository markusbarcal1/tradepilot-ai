"""Fixture-only tests for the isolated index-semantics diagnostic."""
from copy import deepcopy
from datetime import datetime
import inspect
import json

import pytest

from app.cli.inspect_q4_index_semantics import main as cli_main
from app.services.outlook_structured.q4_certification import FixtureTransport, MANIFEST
from app.services.outlook_structured.q4_index_retrieval import _index_url
from app.services.outlook_structured.q4_index_semantics import (
    DESCRIPTION_PATH, DIAGNOSTIC_VERSION, ENTRY_LIMIT, NAME_PATH, TOKEN_LIMIT, TYPE_PATH,
    classify_description, inspect_index_semantics, normalize_type_token,
)
from app.services.outlook_structured.q4_index_semantics_runner import (
    ACKNOWLEDGMENT, AGGREGATE_LIMIT, CLASS_LIMITS, PER_ISSUER_LIMIT, RUNNER_VERSION,
    DiagnosticBudget, IndexSemanticsDiagnosticRunner, validate_live_gate,
)
from app.services.outlook_structured.transport import ProviderUnavailable
from tests.test_q4_candidate_retrieval import fixture


def payload(*, items=(), index_override=None, multiple=False):
    result = fixture(primary_sufficient=False, no_exhibit=True, multiple=multiple)
    if multiple:
        return result
    for index, target in enumerate(MANIFEST):
        accession = f"{target.cik}-{str(target.fiscal_year)[-2:]}-{800000 + index % 2:06d}"
        result["responses"][_index_url(target.cik, accession)] = (
            index_override or {"json": {"directory": {"item": list(items)}}})
    return result


def run(value, **changes):
    transport = FixtureTransport(value["responses"])
    runner = IndexSemanticsDiagnosticRunner(transport,
        user_agent="TradePilot offline operator@example.com", **changes)
    return runner.run(), transport


def test_exact_identities_manifest_budget_and_index_only_flow():
    result, transport = run(payload(items=[{"name": "one.htm", "type": "html",
        "description": "Press Release"}]))
    assert (result["runner"], result["diagnostic"], result["discovery_policy"]) == (
        RUNNER_VERSION, DIAGNOSTIC_VERSION, "bounded-filing-window-item-202-1")
    assert [(row["ticker"], row["fiscal_year"]) for row in result["manifest"]] == [
        ("AAPL", 2024), ("AAPL", 2025), ("NVDA", 2025), ("NVDA", 2026)]
    assert AGGREGATE_LIMIT == 6 and PER_ISSUER_LIMIT == 3
    assert CLASS_LIMITS == {"current_submissions": 2, "filing_index": 4,
        "selected_primary_document": 0, "earnings_exhibit": 0, "filing_document": 0}
    assert result["budget"]["attempts"] == 6
    assert result["budget"]["class_attempts"]["filing_index"] == 4
    assert all(url.endswith("index.json") or "submissions" in url for url in transport.calls)
    assert all(row["state"] == "observed" and row["requests_consumed"] == 1
        for row in result["targets"])


def test_budget_is_nontransferable_and_charged_before_dispatch():
    ledger = DiagnosticBudget()
    ledger.charge("AAPL", 2024, "filing_index")
    with pytest.raises(ProviderUnavailable):
        ledger.charge("AAPL", 2024, "filing_index")
    with pytest.raises(ProviderUnavailable):
        ledger.charge("AAPL", 2024, "selected_primary_document")
    assert ledger.aggregate == 1


@pytest.mark.parametrize("multiple,remove", [(True, False), (False, True)])
def test_unresolved_discovery_never_requests_index(multiple, remove):
    value = payload(multiple=multiple)
    if remove:
        url = "https://data.sec.gov/submissions/CIK0000320193.json"
        recent = value["responses"][url]["json"]["filings"]["recent"]
        keep = [i for i, form in enumerate(recent["form"]) if form == "10-K"]
        for key in recent:
            recent[key] = [recent[key][i] for i in keep]
    result, transport = run(value)
    if multiple:
        assert not result["targets"][0]["index_transport"]["attempted"]
        assert sum(url.endswith("index.json") and "/320193/" in url
            for url in transport.calls) == 1
    else:
        assert not any(url.endswith("index.json") and "/320193/" in url
            for url in transport.calls)
        assert all(not row["index_transport"]["attempted"]
            for row in result["targets"][:2])


def test_binding_drift_never_requests_index(monkeypatch):
    monkeypatch.setattr(IndexSemanticsDiagnosticRunner, "_bind", staticmethod(lambda *args: None))
    result, transport = run(payload())
    assert not any(url.endswith("index.json") for url in transport.calls)
    assert all(row["reason"] == "candidate_binding_failed" for row in result["targets"])


@pytest.mark.parametrize("override,category", [
    ({"raise": "timeout"}, "timeout"),
    ({"raise": "response_size_rejected", "received_bytes": 1048577}, "response_size_rejected"),
    ({"final_url": "https://evil.example/index.json"}, "redirect_rejected"),
])
def test_transport_failures_are_bounded_without_retry(override, category):
    result, transport = run(payload(index_override=override))
    assert result["targets"][0]["index_transport"]["transport_outcome"] == category
    first = next(url for url in transport.calls if url.endswith("index.json"))
    assert transport.calls.count(first) == 1


def test_malformed_and_missing_index_structures_fail_closed():
    malformed, _ = run(payload(index_override={"body": "{"}))
    assert all(row["reason"] == "malformed_index_json" for row in malformed["targets"])
    for body in ({}, {"directory": {}}, {"directory": {"item": {}}}):
        result, _ = run(payload(index_override={"json": body}))
        assert all(row["reason"] == "index_structure_unavailable" for row in result["targets"])


def test_observational_normalizer_field_counts_and_precedence():
    result = inspect_index_semantics({"directory": {"item": [
        {}, {"name": None, "type": None, "description": None},
        {"name": "safe.htm", "type": " html/xml ",
            "description": "Quarterly Results press release earnings"},
        {"name": "../bad", "type": "bad token!", "description": ""},
        {"name": 7, "type": 7, "description": 7}, "not-a-dict",
    ]}})
    assert result["name_path"] == {"schema_path": NAME_PATH, "present": 4, "absent": 2,
        "null": 1, "safe_basename": 1, "unsafe_or_unrepresentable": 3}
    types = result["type_path"]
    assert types["schema_path"] == TYPE_PATH and types["null"] == 1
    assert types["token_counts"] == {"HTML/XML": 1}
    assert types["other_or_unrepresentable"] == 2
    descriptions = result["description_path"]
    assert descriptions["schema_path"] == DESCRIPTION_PATH
    assert descriptions["category_counts"]["quarterly_results"] == 1
    assert descriptions["empty"] == 1 and descriptions["unrepresentable"] == 2
    assert result["cross_tab"]["counts"] == {"HTML/XML|quarterly_results": 1}


@pytest.mark.parametrize("value,expected", [
    (" EX-99.01 ", "EX-99.01"), ("text/html", "TEXT/HTML"),
    ("bad token", None), ("bad?token", None), ("x" * 33, None), (None, None),
])
def test_token_representation_is_conservative_not_semantic(value, expected):
    assert normalize_type_token(value) == expected


@pytest.mark.parametrize("value,expected", [
    ("earnings", "earnings"), ("Financial Results", "financial_results"),
    ("Quarterly Results", "quarterly_results"), ("Press Release", "press_release"),
    ("Results Release", "results_release"), ("Other", "other"), ("", "empty"),
    (7, "unrepresentable"),
])
def test_description_categories(value, expected):
    assert classify_description(value) == expected


def test_entry_token_and_cross_tab_bounds():
    items = [{"name": f"n{i}.htm", "type": f"T{i}", "description": "Other"}
        for i in range(ENTRY_LIMIT + 2)]
    result = inspect_index_semantics({"directory": {"item": items}})
    assert result["structure"]["entries_examined"] == ENTRY_LIMIT
    assert result["structure"]["saturation"] is True
    assert len(result["type_path"]["token_counts"]) == TOKEN_LIMIT
    assert result["type_path"]["saturation"] is True
    assert result["type_path"]["overflow_count"] == ENTRY_LIMIT - TOKEN_LIMIT
    assert len(result["cross_tab"]["counts"]) == TOKEN_LIMIT


def test_artifact_is_sanitized_and_has_no_financial_or_document_transition():
    source = inspect.getsource(IndexSemanticsDiagnosticRunner)
    assert "qualify_direct_q4" not in source and "direct_q4" not in source
    result, _ = run(payload(items=[{"name": "secret.htm", "type": "html",
        "description": "Secret quarterly results revenue 123"}]))
    serialized = json.dumps(result)
    for forbidden in ("secret.htm", "Secret quarterly", "revenue 123", "accession",
            "eight-2024.htm", "document_url", "user_agent", "headers", "@example.com"):
        assert forbidden not in serialized
    assert "accepted_observations" not in serialized
    assert "financial_values" not in serialized and "financial_tables" not in serialized


@pytest.mark.parametrize("changes,reason", [
    ({"user_agent": "invalid"}, "sec_compliant_user_agent_required"),
    ({"aggregate_budget": 5}, "index_semantics_budget_mismatch"),
    ({"http_attempts": 2}, "index_semantics_retries_enabled"),
    ({"follow_redirects": True}, "index_semantics_redirects_enabled"),
])
def test_preflight_failures_dispatch_nothing(changes, reason):
    transport = FixtureTransport(payload()["responses"])
    runner = IndexSemanticsDiagnosticRunner(transport,
        **{"user_agent": "operator@example.com", **changes})
    with pytest.raises(ProviderUnavailable, match=reason):
        runner.run()
    assert transport.calls == []


def test_live_gate_is_distinct_and_exact():
    with pytest.raises(ProviderUnavailable, match="live_flag_required"):
        validate_live_gate(live=False, acknowledgment=ACKNOWLEDGMENT,
            user_agent="operator@example.com")
    with pytest.raises(ProviderUnavailable, match="exact_index_semantics"):
        validate_live_gate(live=True, acknowledgment="wrong", user_agent="operator@example.com")
    validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT,
        user_agent="operator@example.com")


def test_fixture_cli_is_immutable_and_versioned(tmp_path, monkeypatch, capsys):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(payload()), encoding="utf-8")
    repository = tmp_path / "repository"
    output = repository / "docs" / "diagnostics"
    import app.cli.inspect_q4_index_semantics as cli
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", repository)

    class FixedDatetime:
        @classmethod
        def now(cls, timezone_value):
            return datetime(2026, 1, 1, tzinfo=timezone_value)

    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    args = ["--fixture", str(fixture_path), "--output-dir", str(output)]
    assert cli_main(args) == 0
    path = capsys.readouterr().out.strip()
    assert "phase6b5c2a5l-index-semantics-" in path
    assert json.loads(open(path, encoding="utf-8").read())["runner"] == RUNNER_VERSION
    with pytest.raises(FileExistsError):
        cli_main(args)


def test_production_isolation_and_frozen_identities():
    from app.services.outlook import configured_providers
    from app.services.outlook_structured.q4_direct import PARSER_VERSION
    from app.services.outlook_structured.q4_filing_index import INDEX_POLICY_VERSION
    from app.services.outlook_structured.q4_candidate_retrieval import RUNNER_VERSION as V1
    from app.services.outlook_structured.q4_index_retrieval import RUNNER_VERSION as V2
    assert (PARSER_VERSION, INDEX_POLICY_VERSION, V1, V2) == ("direct-q4-1",
        "sec-index-json-ex99-earnings-1", "direct-q4-candidate-retrieval-1",
        "direct-q4-candidate-retrieval-2")
    assert all(getattr(provider, "name", None) != RUNNER_VERSION
        for provider in configured_providers())
