"""Offline fixture qualification for the explicit primary relationship adapter."""
from datetime import datetime
import inspect
import json

import pytest

from app.cli.certify_q4_primary_relationship import main as cli_main
from app.services.outlook_structured.q4_certification import FixtureTransport, MANIFEST, _exhibit_candidates
from app.services.outlook_structured.q4_primary_relationship import (
    RELATIONSHIP_POLICY_VERSION, BoundPrimaryDocument,
    resolve_primary_exhibit99_relationship,
)
from app.services.outlook_structured.q4_primary_relationship_runner import (
    ACKNOWLEDGMENT, AGGREGATE_LIMIT, CLASS_LIMITS, PER_ISSUER_LIMIT, RUNNER_VERSION,
    PrimaryRelationshipBudget, PrimaryRelationshipCertificationRunner, validate_live_gate,
)
from app.services.outlook_structured.transport import ProviderUnavailable
from tests.test_q4_candidate_retrieval import fixture, release


BASE = "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/report.htm"


def bound(html, *, url=BASE, document="report.htm", cik="0000000001",
        accession="0000000001-26-000001"):
    return BoundPrimaryDocument("TEST", "Test Inc.", cik, accession, "8-K", 2026,
        "2026-01-01", "2026-01-20", url, document, html)


def resolve(html, **changes):
    return resolve_primary_exhibit99_relationship(bound(html, **changes))


@pytest.mark.parametrize("label", ["99", "99.1", "99.01", "Exhibit 99",
    "Exhibit 99.1", "Exhibit 99.01"])
def test_explicit_supported_labels_resolve_without_earnings_purpose(label):
    result = resolve(f'<a href="release.htm">{label}</a>')
    assert result.state == "resolved"
    assert result.destination.document_id == "release.htm"
    assert result.destination.policy_version == RELATIONSHIP_POLICY_VERSION


def test_real_derived_separate_table_cells_resolve():
    result = resolve('<table><tr><td>99.1</td><td><a href="release.htm">'
        'Press release issued by synthetic issuer</a></td></tr></table>')
    assert result.state == "resolved" and result.destination.document_id == "release.htm"


def test_duplicate_observations_collapse_and_multiple_destinations_are_ambiguous():
    duplicate = resolve('<a href="release.htm">99.1</a><a href="./release.htm">99.1</a>')
    assert duplicate.state == "resolved" and duplicate.relationship_observations == 2
    assert duplicate.duplicate_collapses == 1
    multiple = resolve('<a href="one.htm">99.1</a><a href="two.htm">99.01</a>')
    assert multiple.state == "ambiguous" and multiple.distinct_safe_destinations == 2
    assert multiple.destination is None


@pytest.mark.parametrize("href", ["https://evil.example/x.htm", "http://www.sec.gov/x.htm",
    "../x.htm", "x.htm?q=1", "x.htm#part",
    "https://www.sec.gov/Archives/edgar/data/1/other/x.htm",
    "https://www.sec.gov/Archives/edgar/data/2/000000000126000001/x.htm",
    "nested/x.htm", "bad?.htm", "report.htm"])
def test_unsafe_cross_identity_and_self_destinations_fail_closed(href):
    result = resolve(f'<a href="{href}">99.1</a>')
    assert result.state == "unavailable" and result.destination is None


def test_unsupported_and_nearby_only_labels_are_not_promoted():
    assert resolve('<a href="release.htm">99.2</a>').state == "unavailable"
    html = '<p>EX-99.1 earnings release <a href="release.htm">Financial Results</a></p>'
    assert _exhibit_candidates(html, BASE)
    assert resolve(html).state == "unavailable"


def test_adapter_requires_exact_bound_primary_identity_and_supported_content():
    assert resolve("", url=BASE.replace("report.htm", "other.htm")).state == "invalid_input"
    assert resolve("", accession="bad").state == "invalid_input"
    value = bound("")
    object.__setattr__(value, "html", None)
    assert resolve_primary_exhibit99_relationship(value).reason == "unsupported_primary_content"


def runner_fixture(*, relationship="one", exhibit_failure=None):
    value = fixture(primary_sufficient=False, no_exhibit=True)
    for primary_url in [url for url in value["responses"] if "/eight-" in url]:
        year = int(primary_url.rsplit("eight-", 1)[1].split(".htm", 1)[0])
        target = next(row for row in MANIFEST if row.fiscal_year == year
            and str(int(row.cik)) in primary_url)
        if relationship == "none":
            html = '<a href="release.htm">Press release</a>'
        elif relationship == "many":
            html = '<a href="a.htm">99.1</a><a href="b.htm">99.01</a>'
        else:
            html = '<table><tr><td>99.1</td><td><a href="release.htm">Results</a></td></tr></table>'
        value["responses"][primary_url] = {"body": html}
        if relationship == "one":
            value["responses"][primary_url.rsplit("/", 1)[0] + "/release.htm"] = (
                exhibit_failure or {"body": release(target)})
    return value


def run(value, **changes):
    transport = FixtureTransport(value["responses"])
    runner = PrimaryRelationshipCertificationRunner(transport,
        user_agent="TradePilot offline operator@example.com", **changes)
    return runner.run(), transport


def test_exact_identities_manifest_and_future_budget():
    result, _ = run(runner_fixture())
    assert (result["runner"], result["relationship_policy"], result["discovery_policy"],
        result["parser"]) == (RUNNER_VERSION, RELATIONSHIP_POLICY_VERSION,
        "bounded-filing-window-item-202-1", "direct-q4-1")
    assert AGGREGATE_LIMIT == 10 and PER_ISSUER_LIMIT == 5
    assert CLASS_LIMITS == {"current_submissions": 2, "selected_primary_document": 4,
        "earnings_exhibit": 4, "filing_index": 0}
    assert [(row["ticker"], row["fiscal_year"]) for row in result["manifest"]] == [
        ("AAPL", 2024), ("AAPL", 2025), ("NVDA", 2025), ("NVDA", 2026)]
    assert result["budget"]["attempts"] == 10
    assert all(row["parser"]["accepted_observations_count"] == 2 for row in result["targets"])


def test_nontransferable_charge_before_dispatch_and_zero_index_allowance():
    ledger = PrimaryRelationshipBudget()
    ledger.charge("AAPL", 2024, "selected_primary_document")
    with pytest.raises(ProviderUnavailable):
        ledger.charge("AAPL", 2024, "selected_primary_document")
    with pytest.raises(ProviderUnavailable):
        ledger.charge("AAPL", 2024, "filing_index")
    assert ledger.aggregate == 1


@pytest.mark.parametrize("relationship,expected", [("none", "unavailable"),
    ("many", "ambiguous")])
def test_zero_or_ambiguous_relationship_never_requests_exhibit(relationship, expected):
    result, transport = run(runner_fixture(relationship=relationship))
    assert all(row["relationship"]["state"] == expected for row in result["targets"])
    assert result["budget"]["class_attempts"]["earnings_exhibit"] == 0
    assert not any(url.endswith("release.htm") for url in transport.calls)


def test_one_relationship_requests_one_exhibit_and_parser_once(monkeypatch):
    import app.services.outlook_structured.q4_primary_relationship_runner as module
    original = module.qualify_direct_q4
    calls = []
    monkeypatch.setattr(module, "qualify_direct_q4",
        lambda docs: (calls.append(tuple(docs)) or original(docs)))
    result, transport = run(runner_fixture())
    assert len(calls) == 4
    assert all(row["requests_consumed"] == 2 for row in result["targets"])
    assert all(sum(url.endswith("release.htm") for url in transport.calls
        if f"/{int(target.cik)}/" in url) == 2 for target in MANIFEST[::2])
    assert not any(url.endswith("index.json") for url in transport.calls)


def test_exhibit_transport_failure_never_invokes_parser(monkeypatch):
    import app.services.outlook_structured.q4_primary_relationship_runner as module
    monkeypatch.setattr(module, "qualify_direct_q4",
        lambda docs: pytest.fail("parser must not run"))
    result, _ = run(runner_fixture(exhibit_failure={"raise": "timeout"}))
    assert all(row["reason"] == "exhibit_transport_failure" for row in result["targets"])


@pytest.mark.parametrize("changes,reason", [
    ({"user_agent": "invalid"}, "sec_compliant_user_agent_required"),
    ({"aggregate_budget": 9}, "primary_relationship_budget_mismatch"),
    ({"http_attempts": 2}, "primary_relationship_retries_enabled"),
    ({"follow_redirects": True}, "primary_relationship_redirects_enabled"),
])
def test_preflight_failures_dispatch_nothing(changes, reason):
    transport = FixtureTransport(runner_fixture()["responses"])
    runner = PrimaryRelationshipCertificationRunner(transport,
        **{"user_agent": "operator@example.com", **changes})
    with pytest.raises(ProviderUnavailable, match=reason):
        runner.run()
    assert transport.calls == []


def test_artifact_is_sanitized_and_adapter_has_no_provider_or_parser_dependency():
    adapter_source = inspect.getsource(resolve_primary_exhibit99_relationship)
    assert "SecEvidenceProvider" not in adapter_source and "qualify_direct_q4" not in adapter_source
    result, _ = run(runner_fixture())
    serialized = json.dumps(result)
    for forbidden in ("release.htm", "eight-2024.htm", "accession", "document_url",
            "user_agent", "headers", "@example.com", "Fourth Quarter Ended"):
        assert forbidden not in serialized


def test_live_gate_is_exact_and_distinct():
    with pytest.raises(ProviderUnavailable, match="live_flag_required"):
        validate_live_gate(live=False, acknowledgment=ACKNOWLEDGMENT,
            user_agent="operator@example.com")
    with pytest.raises(ProviderUnavailable, match="exact_primary_relationship"):
        validate_live_gate(live=True, acknowledgment="wrong", user_agent="operator@example.com")
    validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT,
        user_agent="operator@example.com")


def test_fixture_cli_is_versioned_immutable_and_not_live(tmp_path, monkeypatch, capsys):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(runner_fixture(relationship="none")), encoding="utf-8")
    repository = tmp_path / "repository"
    output = repository / "docs" / "diagnostics"
    import app.cli.certify_q4_primary_relationship as cli
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", repository)
    class FixedDatetime:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 1, 1, tzinfo=tz)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    args = ["--fixture", str(path), "--output-dir", str(output)]
    assert cli_main(args) == 0
    artifact = capsys.readouterr().out.strip()
    assert json.loads(open(artifact, encoding="utf-8").read())["runner"] == RUNNER_VERSION
    with pytest.raises(FileExistsError):
        cli_main(args)


def test_frozen_identities_and_production_isolation():
    from app.services.outlook import configured_providers
    from app.services.outlook_structured.q4_direct import PARSER_VERSION
    from app.services.outlook_structured.q4_filing_index import INDEX_POLICY_VERSION
    from app.services.outlook_structured.q4_index_semantics import DIAGNOSTIC_VERSION
    from app.services.outlook_structured.q4_candidate_retrieval import RUNNER_VERSION as V1
    from app.services.outlook_structured.q4_index_retrieval import RUNNER_VERSION as V2
    assert (PARSER_VERSION, INDEX_POLICY_VERSION, DIAGNOSTIC_VERSION, V1, V2) == (
        "direct-q4-1", "sec-index-json-ex99-earnings-1", "sec-index-semantics-1",
        "direct-q4-candidate-retrieval-1", "direct-q4-candidate-retrieval-2")
    assert all(getattr(provider, "name", None) != RUNNER_VERSION
        for provider in configured_providers())
