"""Fixture-only coverage for the isolated candidate-retrieval certification runner."""
from copy import deepcopy
from datetime import date, timedelta
import inspect
import json

import pytest

from app.services.outlook_structured.q4_candidate_retrieval import (
    AGGREGATE_LIMIT, CLASS_LIMITS, RETRIEVAL_ACKNOWLEDGMENT, RUNNER_VERSION,
    CandidateRetrievalRunner, RetrievalBudget, validate_retrieval_live_gate,
)
from app.services.outlook_structured.q4_certification import (
    FixtureTransport, MANIFEST, _document_url,
)
from app.services.outlook_structured.transport import ProviderUnavailable
from app.cli.certify_q4_candidate_retrieval import main as retrieval_main


def release(target, *, basic=False, conflicting=False):
    start = date.fromisoformat(target.period_end) - timedelta(days=89)
    eps = "GAAP Basic EPS" if basic else "GAAP Diluted EPS"
    extra = '<tr><td>Revenue USD ones</td><td>$2000</td></tr>' if conflicting else ""
    return (f'<table><tr><th>Fourth Quarter Ended {start.isoformat()} to {target.period_end}</th></tr>'
        f'<tr><td>Revenue USD ones</td><td>$1000</td></tr>{extra}'
        f'<tr><td>{eps} USD/share</td><td>$2.50</td></tr></table>')


def fixture(*, primary_sufficient=True, multiple=False, no_exhibit=False, external=False,
        primary_failure=None, exhibit_failure=None, basic=False, conflicting=False):
    responses = {}
    for ticker in ("AAPL", "NVDA"):
        targets = [target for target in MANIFEST if target.ticker == ticker]
        recent = {key: [] for key in ("accessionNumber", "form", "reportDate", "filingDate",
            "primaryDocument", "items")}
        for index, target in enumerate(targets):
            end = date.fromisoformat(target.period_end)
            annual_date = (end + timedelta(days=25)).isoformat()
            filing_date = (end + timedelta(days=20)).isoformat()
            accession = f"{target.cik}-{str(target.fiscal_year)[-2:]}-{800000 + index:06d}"
            primary = f"eight-{target.fiscal_year}.htm"
            values = ((target.ten_k_accession, "10-K", target.period_end, annual_date,
                f"annual-{target.fiscal_year}.htm", ""),
                (accession, "8-K", "unrelated-report-date", filing_date, primary, "2.02,9.01"))
            if multiple and index == 0:
                values += ((f"{target.cik}-{str(target.fiscal_year)[-2:]}-{810000 + index:06d}",
                    "8-K/A", "", filing_date, f"amended-{target.fiscal_year}.htm", "2.02"),)
            for values_row in values:
                for key, value in zip(recent, values_row):
                    recent[key].append(value)
            primary_url = _document_url(target.cik, accession, primary)
            exhibit = f"ex99-{target.fiscal_year}.htm"
            exhibit_url = primary_url.rsplit("/", 1)[0] + "/" + exhibit
            if primary_failure and index == 0 and ticker == "AAPL":
                responses[primary_url] = primary_failure
            elif primary_sufficient:
                responses[primary_url] = {"body": release(target, basic=basic,
                    conflicting=conflicting)}
            else:
                href = "https://evil.example/ex99.htm" if external else exhibit
                links = "" if no_exhibit else (f'<p>EX-99.1 earnings release '
                    f'<a href="{href}">Financial Results</a></p>')
                responses[primary_url] = {"body": f"<html>{links}</html>"}
                if not external and not no_exhibit:
                    responses[exhibit_url] = exhibit_failure or {"body": release(target,
                        basic=basic, conflicting=conflicting)}
        responses[f"https://data.sec.gov/submissions/CIK{targets[0].cik}.json"] = {
            "json": {"filings": {"recent": recent, "files": []}}}
    return {"responses": responses}


def run(payload, **changes):
    transport = FixtureTransport(payload["responses"])
    runner = CandidateRetrievalRunner(transport,
        user_agent="TradePilot offline operator@example.com", **changes)
    return runner.run(), transport


def test_one_candidate_binds_to_one_primary_and_primary_success_stops():
    result, transport = run(fixture())
    assert result["runner"] == RUNNER_VERSION
    assert result["discovery_policy"] == "bounded-filing-window-item-202-1"
    assert result["parser"] == "direct-q4-1"
    assert result["budget"]["attempts"] == 6
    assert result["budget"]["class_attempts"] == {"current_submissions": 2,
        "selected_primary_document": 4, "filing_index": 0, "earnings_exhibit": 0}
    assert all(row["retrieval"]["primary_sufficient_for_parser"] for row in result["targets"])
    assert all(row["parser"]["revenue_available"] for row in result["targets"])
    assert all(row["parser"]["diluted_eps_available"] for row in result["targets"])
    assert not any("ex99-" in url for url in transport.calls)


@pytest.mark.parametrize("multiple,mutation,reason", [
    (False, "remove", "no_plausible_candidate"),
    (True, None, "multiple_plausible_candidates"),
])
def test_zero_or_ambiguous_metadata_spends_no_target_document_allowance(multiple, mutation, reason):
    payload = fixture(multiple=multiple)
    if mutation == "remove":
        url = "https://data.sec.gov/submissions/CIK0000320193.json"
        recent = payload["responses"][url]["json"]["filings"]["recent"]
        keep = [i for i, form in enumerate(recent["form"]) if form == "10-K"]
        for key in recent:
            recent[key] = [recent[key][i] for i in keep]
    result, _ = run(payload)
    target = result["targets"][0]
    assert target["reason"] == reason
    assert target["retrieval"]["selected_primary_request_attempted"] is False


def test_candidate_identity_drift_fails_binding():
    payload = fixture()
    url = "https://data.sec.gov/submissions/CIK0000320193.json"
    rows = __import__("app.services.outlook_structured.q4_certification", fromlist=["_rows"])._rows(
        payload["responses"][url]["json"])
    target = MANIFEST[0]
    from app.services.outlook_structured.q4_discovery_policy import discover_q4_earnings_8k
    candidate = dict(discover_q4_earnings_8k(rows, period_end=target.period_end,
        approved_ten_k_accession=target.ten_k_accession).candidates[0])
    candidate["report_date"] = "drifted"
    assert CandidateRetrievalRunner._bind(target, rows, candidate) is None


@pytest.mark.parametrize("field,value", [("accessionNumber", "unsafe"),
    ("primaryDocument", "../unsafe.htm")])
def test_unsafe_candidate_identity_causes_zero_document_requests(field, value):
    payload = fixture()
    url = "https://data.sec.gov/submissions/CIK0000320193.json"
    recent = payload["responses"][url]["json"]["filings"]["recent"]
    index = recent["form"].index("8-K")
    recent[field][index] = value
    result, _ = run(payload)
    assert result["targets"][0]["retrieval"]["selected_primary_request_attempted"] is False


def test_primary_can_require_one_deterministic_exhibit_without_index():
    result, _ = run(fixture(primary_sufficient=False))
    assert result["budget"]["attempts"] == AGGREGATE_LIMIT
    assert result["budget"]["class_attempts"] == {"current_submissions": 2,
        "selected_primary_document": 4, "filing_index": 0, "earnings_exhibit": 4}
    assert all(row["exhibit"]["request_attempted"] for row in result["targets"])
    assert all(row["reason"] == "exhibit_parser_qualified" for row in result["targets"])


def test_multiple_exhibits_are_ambiguous_and_not_retrieved():
    payload = fixture(primary_sufficient=False)
    primary_url = next(url for url in payload["responses"] if "eight-2024.htm" in url)
    payload["responses"][primary_url] = {"body": '<p>EX-99.1 earnings release <a href="a.htm">Results</a></p>'
        '<p>EX-99.2 earnings release <a href="b.htm">Results</a></p>'}
    result, _ = run(payload)
    first = result["targets"][0]
    assert first["reason"] == "earnings_exhibit_ambiguous"
    assert first["exhibit"]["eligible_references"] == 2
    assert first["exhibit"]["request_attempted"] is False


@pytest.mark.parametrize("external,no_exhibit", [(True, False), (False, True)])
def test_external_or_missing_exhibit_is_unavailable_without_guessing(external, no_exhibit):
    result, _ = run(fixture(primary_sufficient=False, external=external, no_exhibit=no_exhibit))
    assert all(row["reason"] == "parser_incompatible_no_eligible_exhibit" for row in result["targets"])
    assert all(not row["exhibit"]["request_attempted"] for row in result["targets"])


@pytest.mark.parametrize("failure,category,status,received", [
    ({"final_url": "https://evil.example/x"}, "redirect_rejected", 200, None),
    ({"raise": "timeout"}, "timeout", None, None),
    ({"raise": "response_size_rejected", "received_bytes": 1048577},
        "response_size_rejected", None, 1048577),
])
def test_primary_transport_failures_are_bounded_without_retry(failure, category, status, received):
    payload = fixture(primary_failure=failure)
    result, transport = run(payload)
    first = result["targets"][0]
    assert first["retrieval"]["transport_outcome"] == category
    assert first["retrieval"]["http_status"] == status
    if received is not None:
        assert first["retrieval"]["received_bytes"] == received
    primary = next(url for url in transport.calls if "eight-2024.htm" in url)
    assert transport.calls.count(primary) == 1


def test_failed_target_does_not_donate_allowance_and_aggregate_never_exceeds_ten():
    result, _ = run(fixture(primary_sufficient=False, primary_failure={"raise": "timeout"}))
    assert result["budget"]["attempts"] <= AGGREGATE_LIMIT
    assert result["budget"]["per_issuer"]["AAPL"] <= 5
    assert result["budget"]["per_issuer"]["NVDA"] <= 5
    assert result["budget"]["class_attempts"]["selected_primary_document"] == 4
    assert result["budget"]["class_attempts"]["earnings_exhibit"] == 3


def test_budget_is_charged_before_dispatch_and_cannot_transfer_classes():
    ledger = RetrievalBudget()
    with pytest.raises(ProviderUnavailable):
        ledger.charge("AAPL", 2024, "filing_index")
    assert ledger.aggregate == 0
    ledger.charge("AAPL", 2024, "selected_primary_document")
    with pytest.raises(ProviderUnavailable):
        ledger.charge("AAPL", 2024, "selected_primary_document")
    assert ledger.aggregate == 1


def test_parser_incompatibility_basic_eps_and_conflicts_remain_fail_closed():
    basic, _ = run(fixture(primary_sufficient=True, basic=True))
    assert all(row["parser"]["diluted_eps_available"] is False for row in basic["targets"])
    assert all(row["parser"]["revenue_available"] is True for row in basic["targets"])
    conflicts, _ = run(fixture(primary_sufficient=True, conflicting=True))
    assert all(row["parser"]["conflict_state"] is True for row in conflicts["targets"])
    assert all(row["parser"]["revenue_available"] is False for row in conflicts["targets"])


def test_sanitized_artifact_retains_no_bodies_candidate_identity_or_secrets():
    result, _ = run(fixture(primary_sufficient=False))
    serialized = json.dumps(result)
    for forbidden in ("Fourth Quarter Ended", "800000", "eight-2024.htm", "ex99-2024.htm",
            "operator@example.com", "response_body", "headers", "document_url"):
        assert forbidden not in serialized


@pytest.mark.parametrize("changes,reason", [
    ({"user_agent": "invalid"}, "sec_compliant_user_agent_required"),
    ({"aggregate_budget": 11}, "retrieval_budget_mismatch"),
    ({"class_limits": {**CLASS_LIMITS, "earnings_exhibit": 5}}, "retrieval_budget_mismatch"),
    ({"http_attempts": 2}, "retrieval_retries_enabled"),
    ({"follow_redirects": True}, "retrieval_redirects_enabled"),
])
def test_preflight_mismatch_fails_before_dispatch(changes, reason):
    transport = FixtureTransport(fixture()["responses"])
    arguments = {"user_agent": "operator@example.com", **changes}
    runner = CandidateRetrievalRunner(transport, **arguments)
    with pytest.raises(ProviderUnavailable, match=reason):
        runner.run()
    assert transport.calls == []


def test_live_gate_uses_new_exact_acknowledgment():
    with pytest.raises(ProviderUnavailable):
        validate_retrieval_live_gate(live=True,
            acknowledgment="I ACKNOWLEDGE THE 2-ATTEMPT METADATA-ONLY LIMIT",
            user_agent="operator@example.com")
    validate_retrieval_live_gate(live=True, acknowledgment=RETRIEVAL_ACKNOWLEDGMENT,
        user_agent="operator@example.com")


def test_runner_is_unregistered_and_legacy_runners_remain_distinct():
    source = inspect.getsource(CandidateRetrievalRunner)
    assert "configured_providers" not in source and "research" not in source.lower()
    from app.services.outlook import configured_providers
    assert all(item.name != RUNNER_VERSION for item in configured_providers())
    from app.services.outlook_structured.q4_certification import (
        MetadataOnlyDiscoveryRunner, Q4CertificationRunner,
    )
    assert MetadataOnlyDiscoveryRunner.runner_version == "direct-q4-metadata-discovery-2"
    assert not issubclass(CandidateRetrievalRunner, Q4CertificationRunner)


def test_offline_cli_is_versioned_non_overwriting_and_sanitized(tmp_path, monkeypatch, capsys):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture()), encoding="utf-8")
    repository = tmp_path / "repository"
    output = repository / "docs" / "diagnostics"
    import app.cli.certify_q4_candidate_retrieval as cli
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", repository)
    assert retrieval_main(["--fixture", str(fixture_path), "--output-dir", str(output)]) == 0
    artifact_path = capsys.readouterr().out.strip()
    artifact = json.loads(open(artifact_path, encoding="utf-8").read())
    assert artifact["runner"] == RUNNER_VERSION and artifact["mode"] == "offline"
    assert "phase6b5c2a5i-candidate-retrieval-" in artifact_path
    assert "Fourth Quarter Ended" not in json.dumps(artifact)
