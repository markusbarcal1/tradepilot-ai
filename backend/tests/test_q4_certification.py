"""Offline safeguards for the fixed direct-Q4 live-certification runner."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import inspect
import json

import pytest

from app.cli.certify_q4 import main as certification_main
from app.cli.inspect_q4_metadata import main as metadata_main
from app.services.outlook_structured.q4_certification import (
    ACKNOWLEDGMENT, AGGREGATE_LIMIT, BudgetLedger, CertificationTransportError, FixtureTransport, MANIFEST,
    METADATA_ACKNOWLEDGMENT, MetadataOnlyDiscoveryRunner, Q4CertificationRunner,
    TransportResponse, _discover_eight_k, _document_url, _exhibit_candidates,
    validate_live_gate, validate_metadata_live_gate,
)
from app.services.outlook_structured.transport import ProviderUnavailable


def filing_xbrl(target):
    start = date.fromisoformat(target.period_end) - timedelta(days=90)
    return f'''<html><body>
    <dei:DocumentFiscalYearFocus>{target.fiscal_year}</dei:DocumentFiscalYearFocus>
    <dei:DocumentFiscalPeriodFocus>FY</dei:DocumentFiscalPeriodFocus>
    <dei:DocumentPeriodEndDate>{target.period_end}</dei:DocumentPeriodEndDate>
    <dei:EntityRegistrantName>{target.issuer}</dei:EntityRegistrantName>
    <xbrli:context id="q4"><xbrli:entity><xbrli:identifier>{int(target.cik)}</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>{start.isoformat()}</xbrli:startDate><xbrli:endDate>{target.period_end}</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
    <table><tr><th>Fourth Quarter Ended</th></tr><tr><td><ix:nonFraction name="us-gaap:Revenues" contextRef="q4" unitRef="usd" scale="0">1000</ix:nonFraction></td></tr></table>
    </body></html>'''


def release(target):
    start = date.fromisoformat(target.period_end) - timedelta(days=90)
    return f'''<table><tr><th>Fourth Quarter Ended {start.isoformat()} to {target.period_end}</th></tr>
    <tr><td>Revenue (USD ones)</td><td>$1000</td></tr></table>'''


def fixture(*, multiple_8k=False, missing_exhibit=False, historical=False):
    responses = {}
    for ticker in ("AAPL", "NVDA"):
        targets = [row for row in MANIFEST if row.ticker == ticker]
        recent = {name: [] for name in ("accessionNumber", "form", "reportDate", "filingDate", "primaryDocument", "items")}
        history_rows = deepcopy(recent)
        for index, target in enumerate(targets):
            destination = history_rows if historical and index == 0 else recent
            ten_doc = f"{ticker.lower()}-{target.fiscal_year}.htm"
            target_end = date.fromisoformat(target.period_end)
            for name, value in (("accessionNumber", target.ten_k_accession), ("form", "10-K"),
                    ("reportDate", target.period_end),
                    ("filingDate", (target_end + timedelta(days=25)).isoformat()),
                    ("primaryDocument", ten_doc), ("items", "")):
                destination[name].append(value)
            eight_accession = f"{target.cik}-{str(target.fiscal_year + 1)[-2:]}-{900000 + index:06d}"
            eight_doc, exhibit_doc = f"eight-{target.fiscal_year}.htm", f"ex99-{target.fiscal_year}.htm"
            count = 2 if multiple_8k and index == 0 else 1
            for duplicate in range(count):
                acc = eight_accession if duplicate == 0 else f"{target.cik}-{str(target.fiscal_year + 1)[-2:]}-{910000 + index:06d}"
                for name, value in (("accessionNumber", acc), ("form", "8-K"),
                        ("reportDate", target.period_end),
                        ("filingDate", (target_end + timedelta(days=20)).isoformat()),
                        ("primaryDocument", eight_doc), ("items", "2.02,9.01")):
                    destination[name].append(value)
            ten_url = _document_url(target.cik, target.ten_k_accession, ten_doc)
            responses[ten_url] = {"body": filing_xbrl(target)}
            eight_url = _document_url(target.cik, eight_accession, eight_doc)
            prefix = eight_url.rsplit("/", 1)[0]
            body = "<html>no exhibit</html>" if missing_exhibit else f'<table><tr><td>EX-99.1 earnings press release</td><td><a href="{exhibit_doc}">Financial Results</a></td></tr></table>'
            responses[eight_url] = {"body": body}
            responses[f"{prefix}/{exhibit_doc}"] = {"body": release(target)}
        submissions = {"filings": {"recent": recent, "files": []}}
        if historical:
            name = f"CIK{targets[0].cik}-submissions-001.json"
            submissions["filings"]["files"] = [{"name": name, "filingFrom": "2020-01-01", "filingTo": "2030-01-01"}]
            responses[f"https://data.sec.gov/submissions/{name}"] = {"json": history_rows}
        responses[f"https://data.sec.gov/submissions/CIK{targets[0].cik}.json"] = {"json": submissions}
    return {"responses": responses}


def run(payload, **changes):
    transport = FixtureTransport(payload["responses"])
    runner = Q4CertificationRunner(transport, user_agent="TradePilot test operator@example.com", **changes)
    return runner.run(), transport


def test_fixed_manifest_and_exact_approved_accessions():
    assert [(row.ticker, row.cik, row.fiscal_year, row.ten_k_accession) for row in MANIFEST] == [
        ("AAPL", "0000320193", 2024, "0000320193-24-000123"),
        ("AAPL", "0000320193", 2025, "0000320193-25-000079"),
        ("NVDA", "0001045810", 2025, "0001045810-25-000023"),
        ("NVDA", "0001045810", 2026, "0001045810-26-000021"),
    ]


def test_current_discovery_is_deterministic_bounded_and_accepts_compatible_fixture():
    result, transport = run(fixture())
    assert result["mode"] == "offline" and result["budget"]["attempts"] == 14
    assert len(transport.calls) == 14 and all(row["status"] == "accepted" for row in result["outcomes"])
    assert {row["ticker"] for row in result["observations"]} == {"AAPL", "NVDA"}
    assert json.dumps(result, sort_keys=True) == json.dumps(run(fixture())[0], sort_keys=True)


def test_at_most_one_historical_submissions_file_is_used_when_needed():
    result, _ = run(fixture(historical=True))
    assert result["budget"]["attempts"] == 16
    assert result["budget"]["per_class"]["AAPL"]["historical_submissions"] == 1
    assert result["budget"]["per_class"]["NVDA"]["historical_submissions"] == 1


def test_unresolved_10k_document_and_multiple_8ks_fail_closed():
    payload = fixture()
    aapl_url = "https://data.sec.gov/submissions/CIK0000320193.json"
    payload["responses"][aapl_url]["json"]["filings"]["recent"]["primaryDocument"][0] = "../hostile.htm"
    result, _ = run(payload)
    first = result["outcomes"][0]
    assert first["branches"]["ten_k"]["reason"] == "approved_10k_document_unresolved"
    assert first["branches"]["earnings_8k"]["parser_status"] == "accepted"
    result, _ = run(fixture(multiple_8k=True))
    assert result["outcomes"][0]["reason"] == "multiple_plausible_earnings_8ks"


def test_missing_exhibit_is_source_unavailable_not_missing_q4_data():
    result, _ = run(fixture(missing_exhibit=True))
    assert all(row["reason"] == "earnings_exhibit_unresolved" for row in result["outcomes"])
    assert "issuer_lacks_q4" not in json.dumps(result)


def test_nontransferable_class_issuer_and_aggregate_budgets_charge_before_dispatch():
    ledger = BudgetLedger()
    ledger.charge("AAPL", "current_submissions")
    with pytest.raises(ProviderUnavailable, match="request_class_attempt_limit"):
        ledger.charge("AAPL", "current_submissions")
    for request_class in ("historical_submissions", "ten_k_document", "ten_k_document",
            "eight_k_index", "eight_k_index", "earnings_exhibit", "earnings_exhibit"):
        ledger.charge("AAPL", request_class)
    assert ledger.issuer["AAPL"] == 8
    with pytest.raises(ProviderUnavailable, match="issuer_attempt_limit"):
        ledger.charge("AAPL", "historical_submissions")
    for request_class in ("current_submissions", "historical_submissions", "ten_k_document",
            "ten_k_document", "eight_k_index", "eight_k_index", "earnings_exhibit", "earnings_exhibit"):
        ledger.charge("NVDA", request_class)
    assert ledger.aggregate == AGGREGATE_LIMIT
    with pytest.raises(ProviderUnavailable, match="aggregate_attempt_limit"):
        ledger.charge("NVDA", "earnings_exhibit")


class FailingTransport:
    def __init__(self): self.calls = 0
    def request(self, *args, **kwargs): self.calls += 1; raise TimeoutError("secret-token")


def test_failed_timeout_request_is_charged_once_without_retry_or_secret_leak():
    transport = FailingTransport()
    result = Q4CertificationRunner(transport, user_agent="test@example.com").run()
    assert transport.calls == 2  # one current-submissions attempt per fixed issuer
    assert result["budget"]["attempts"] == 2
    assert "secret-token" not in json.dumps(result)
    assert {row["transport_outcome"] for row in result["requests"]} == {"timeout"}
    assert all(row["received_bytes"] is None for row in result["requests"])


def test_oversized_response_is_charged_and_not_retried():
    payload = fixture()
    url = "https://data.sec.gov/submissions/CIK0000320193.json"
    payload["responses"][url] = {"body": "x" * 101}
    result, transport = run(payload, max_bytes=100)
    assert transport.calls.count(url) == 1
    assert result["budget"]["per_class"]["AAPL"]["current_submissions"] == 1


def test_redirect_host_and_hostile_document_paths_are_rejected():
    payload = fixture()
    url = "https://data.sec.gov/submissions/CIK0000320193.json"
    payload["responses"][url]["final_url"] = "https://evil.example/steal"
    result, _ = run(payload)
    assert result["outcomes"][0]["status"] == "request_failed"
    assert result["requests"][0]["transport_outcome"] == "redirect_rejected"
    for value in ("../x.htm", "x.htm?secret=1", "https://evil.example/x.htm"):
        with pytest.raises(ProviderUnavailable):
            _document_url("0000320193", "0000320193-24-000123", value)


def test_exhibit_relationship_rejects_external_query_and_traversal_links():
    base = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/main.htm"
    html = '''<p>EX-99.1 earnings release <a href="https://evil.example/e.htm">results</a></p>
      <p>EX-99.2 earnings release <a href="../escape.htm">results</a></p>
      <p>EX-99.3 earnings release <a href="safe.htm?x=1">results</a></p>'''
    assert _exhibit_candidates(html, base) == ()


def test_cache_hit_does_not_charge_or_expand_budget():
    payload = fixture()
    url = "https://data.sec.gov/submissions/CIK0000320193.json"
    response = TransportResponse(200, url, json.dumps(payload["responses"][url]["json"]).encode())
    transport = FixtureTransport(payload["responses"])
    runner = Q4CertificationRunner(transport, user_agent="test@example.com", cache={url: response})
    result = runner.run()
    assert url not in transport.calls
    assert result["budget"]["attempts"] == 13
    assert next(row for row in result["requests"] if row["requested_url"] == url)["cache"] == "hit"


def test_live_gate_requires_flag_exact_acknowledgment_and_compliant_user_agent():
    with pytest.raises(ProviderUnavailable, match="live_flag_required"):
        validate_live_gate(live=False, acknowledgment=ACKNOWLEDGMENT, user_agent="test@example.com")
    with pytest.raises(ProviderUnavailable, match="exact_attempt"):
        validate_live_gate(live=True, acknowledgment="16", user_agent="test@example.com")
    with pytest.raises(ProviderUnavailable, match="user_agent"):
        validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT, user_agent="TradePilot")
    validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT, user_agent="TradePilot operator@example.com")


def test_offline_cli_uses_fixture_and_never_calls_live_transport(tmp_path, monkeypatch, capsys):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture()), encoding="utf-8")
    output = tmp_path / "repository" / "docs" / "diagnostics"
    import app.cli.certify_q4 as cli
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", tmp_path / "repository")
    assert certification_main(["--fixture", str(fixture_path), "--output-dir", str(output)]) == 0
    artifact = capsys.readouterr().out.strip()
    data = json.loads(open(artifact, encoding="utf-8").read())
    assert data["mode"] == "offline" and data["budget"]["attempts"] == 14


def test_runner_has_no_analyze_database_ai_or_production_registration():
    import app.services.outlook_structured.q4_certification as module
    source = open(module.__file__, encoding="utf-8").read().lower()
    assert "openai" not in source and "database" not in source and "configured_providers" not in source


def failed_document_fixture():
    payload = fixture()
    categories = iter((
        {"raise": "http_error", "http_status": 403},
        {"raise": "timeout"},
        {"raise": "redirect_rejected", "http_status": 302},
        {"raise": "connection_failure"},
    ))
    for ticker in ("AAPL", "NVDA"):
        submissions_url = f"https://data.sec.gov/submissions/CIK{next(row.cik for row in MANIFEST if row.ticker == ticker)}.json"
        recent = payload["responses"][submissions_url]["json"]["filings"]["recent"]
        keep = [index for index, form in enumerate(recent["form"]) if form == "10-K"]
        for name, values in list(recent.items()):
            recent[name] = [values[index] for index in keep]
        for target in (row for row in MANIFEST if row.ticker == ticker):
            document_id = f"{ticker.lower()}-{target.fiscal_year}.htm"
            payload["responses"][_document_url(target.cik, target.ten_k_accession, document_id)] = next(categories)
    return payload


def test_live_failure_shape_preserves_four_transport_failures_and_unresolved_8k_branches():
    result, transport = run(failed_document_fixture())
    assert result["budget"]["attempts"] == 6 and len(transport.calls) == 6
    assert [row["transport_outcome"] for row in result["requests"][1:3] + result["requests"][4:6]] == [
        "http_error", "timeout", "redirect_rejected", "connection_failure"]
    assert result["requests"][1]["http_status"] == 403
    assert result["requests"][2]["http_status"] is None
    assert all(row["status"] == "request_failed" for row in result["outcomes"])
    for outcome in result["outcomes"]:
        assert outcome["branches"]["ten_k"]["retrieval_status"] == "request_failed"
        assert outcome["branches"]["earnings_8k"]["discovery_status"] == "unresolved"
        assert outcome["branches"]["earnings_8k"]["reason"] == "earnings_8k_unresolved"
        assert outcome["reasons"] == ["ten_k_request_failed", "earnings_8k_unresolved"]
    assert result["candidate_count"] == 0 and result["observations"] == []


@pytest.mark.parametrize("failure,expected,status,received", [
    ({"raise": "response_size_rejected", "received_bytes": 1048577}, "response_size_rejected", None, 1048577),
    ({"raise": "transport_failure"}, "transport_failure", None, None),
    ({"status": 503, "body": "bounded"}, "http_error", 503, 7),
])
def test_bounded_transport_categories_are_deterministic_and_sanitized(failure, expected, status, received):
    url = "https://data.sec.gov/submissions/CIK0000320193.json"
    runner = Q4CertificationRunner(FixtureTransport({url: failure}), user_agent="secret-address@example.com")
    with pytest.raises(CertificationTransportError, match=expected):
        runner._get("AAPL", "current_submissions", url)
    row = runner.requests[0]
    assert row["transport_outcome"] == expected and row["http_status"] == status
    assert row["received_bytes"] == received
    serialized = json.dumps(row)
    assert "secret-address" not in serialized and "bounded" not in serialized


def test_url_policy_rejection_is_recorded_without_dispatch_or_budget_charge():
    transport = FixtureTransport({})
    runner = Q4CertificationRunner(transport, user_agent="test@example.com")
    with pytest.raises(CertificationTransportError, match="url_policy_rejected"):
        runner._get("AAPL", "ten_k_document", "https://evil.example/document.htm")
    assert transport.calls == [] and runner.ledger.aggregate == 0
    assert runner.requests[0]["ordinal_attempt"] is None
    assert runner.requests[0]["transport_outcome"] == "url_policy_rejected"


def test_failure_artifact_is_deterministic_and_contains_no_raw_payload_or_identity_secret():
    first, _ = run(failed_document_fixture())
    second, _ = run(failed_document_fixture())
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    serialized = json.dumps(first)
    assert "response_body" not in serialized and "authorization" not in serialized
    assert "operator@example.com" not in serialized


@pytest.mark.parametrize("field,replacement", [
    ("reportDate", "2026-02-01"),
    ("items", "9.01"),
])
def test_eight_k_discovery_requires_exact_report_date_and_explicit_item_202(field, replacement):
    payload = fixture()
    for ticker in ("AAPL", "NVDA"):
        cik = next(row.cik for row in MANIFEST if row.ticker == ticker)
        recent = payload["responses"][f"https://data.sec.gov/submissions/CIK{cik}.json"]["json"]["filings"]["recent"]
        for index, form in enumerate(recent["form"]):
            if form == "8-K":
                recent[field][index] = replacement
    result, transport = run(payload)
    assert all(row["branches"]["earnings_8k"]["reason"] == "earnings_8k_unresolved"
        for row in result["outcomes"])
    assert result["budget"]["attempts"] == 6
    assert not any("eight-" in url or "ex99-" in url for url in transport.calls)


def test_eight_k_discovery_counters_use_sequential_first_failure_semantics():
    rows = [
        {"form": "10-K", "report_date": "2025-12-31", "items": "2.02", "primary_document": "annual.htm"},
        {"form": "8-K", "report_date": "2025-12-30", "items": "", "primary_document": "../unsafe.htm"},
        {"form": "8-K/A", "report_date": "2025-12-31", "items": "9.01", "primary_document": "../unsafe.htm"},
        {"form": "8-K", "report_date": "2025-12-31", "items": "2.02,9.01", "primary_document": "../unsafe.htm"},
        {"form": "8-K", "report_date": "2025-12-31", "items": "2.02,9.01", "primary_document": "earnings.htm",
            "accession": "0001045810-26-000001"},
    ]
    candidates, counts = _discover_eight_k(rows, "2025-12-31")
    assert len(candidates) == 1 and candidates[0]["primary_document"] == "earnings.htm"
    assert counts == {"count_semantics": "sequential_first_failure", "count_limit": 4096,
        "counts_capped": False, "metadata_rows_examined": 5, "rows_rejected_by_form": 1,
        "eight_k_rows_examined": 4, "rows_rejected_by_exact_report_date": 1,
        "rows_rejected_by_item_202": 1, "rows_rejected_by_primary_document": 1,
        "qualifying_candidates": 1, "ambiguous_qualifying_candidates": 0}
    assert counts["metadata_rows_examined"] == counts["rows_rejected_by_form"] + counts["eight_k_rows_examined"]
    assert counts["eight_k_rows_examined"] == (counts["rows_rejected_by_exact_report_date"] +
        counts["rows_rejected_by_item_202"] + counts["rows_rejected_by_primary_document"] +
        counts["qualifying_candidates"])


def test_eight_k_discovery_reports_ambiguous_candidates_without_retaining_candidate_metadata():
    payload = fixture(multiple_8k=True)
    result, _ = run(payload)
    first = result["outcomes"][0]
    counts = first["branches"]["earnings_8k"]["discovery_diagnostics"]
    assert counts["qualifying_candidates"] == 2
    assert counts["ambiguous_qualifying_candidates"] == 2
    assert first["branches"]["earnings_8k"]["discovery_status"] == "ambiguous"
    serialized = json.dumps(counts)
    assert "0000320193-25-900000" not in serialized and "eight-2024.htm" not in serialized


def test_discovery_counts_are_bounded_and_explicitly_marked_when_capped():
    rows = [{"form": "10-K", "secret": f"unrelated-{index}"} for index in range(4097)]
    candidates, counts = _discover_eight_k(rows, "2025-12-31")
    assert candidates == () and counts["counts_capped"] is True
    assert counts["metadata_rows_examined"] == 4096
    assert counts["rows_rejected_by_form"] == 4096
    assert "unrelated-" not in json.dumps(counts)


def test_successful_and_unresolved_discovery_emit_bounded_sanitized_counts():
    successful, _ = run(fixture())
    for outcome in successful["outcomes"]:
        counts = outcome["branches"]["earnings_8k"]["discovery_diagnostics"]
        assert counts["qualifying_candidates"] == 1 and not counts["counts_capped"]
    failed, _ = run(failed_document_fixture())
    for outcome in failed["outcomes"]:
        counts = outcome["branches"]["earnings_8k"]["discovery_diagnostics"]
        assert counts["qualifying_candidates"] == 0
        assert counts["eight_k_rows_examined"] == 0


def metadata_run(payload, **changes):
    transport = FixtureTransport(payload["responses"])
    runner = MetadataOnlyDiscoveryRunner(transport,
        user_agent="TradePilot test operator@example.com", **changes)
    return runner.run(), transport


def test_metadata_only_mode_charges_exactly_two_submissions_requests_and_never_fetches_documents():
    result, transport = metadata_run(fixture())
    assert result["schema_version"] == "2"
    assert result["runner"] == "direct-q4-metadata-discovery-2"
    assert result["discovery_policy"] == "bounded-filing-window-item-202-1"
    assert result["budget"] == {"maximum": 2, "attempts": 2, "per_issuer_maximum": 1,
        "per_issuer": {"AAPL": 1, "NVDA": 1},
        "enabled_request_classes": ["current_submissions"]}
    assert len(transport.calls) == 2
    assert transport.calls == ["https://data.sec.gov/submissions/CIK0000320193.json",
        "https://data.sec.gov/submissions/CIK0001045810.json"]
    assert {row["request_class"] for row in result["requests"]} == {"current_submissions"}
    assert len(result["targets"]) == 4
    assert all(row["discovery_diagnostics"]["distinct_qualifying_candidates"] == 1
        for row in result["targets"])


def test_metadata_only_failure_does_not_retry_or_transfer_allowance():
    payload = fixture()
    aapl = "https://data.sec.gov/submissions/CIK0000320193.json"
    payload["responses"][aapl] = {"raise": "timeout"}
    result, transport = metadata_run(payload)
    assert transport.calls.count(aapl) == 1 and len(transport.calls) == 2
    assert result["budget"]["attempts"] == 2
    assert result["budget"]["per_issuer"] == {"AAPL": 1, "NVDA": 1}
    assert all(row["discovery_state"] == "request_failed" for row in result["targets"][:2])
    assert all(row["discovery_diagnostics"] is None for row in result["targets"][:2])
    assert all(row["received_bytes"] is None for row in result["requests"] if row["ticker"] == "AAPL")


def test_metadata_only_redirect_is_rejected_and_never_retried():
    payload = fixture()
    url = "https://data.sec.gov/submissions/CIK0000320193.json"
    payload["responses"][url]["final_url"] = "https://evil.example/redirect"
    result, transport = metadata_run(payload)
    assert transport.calls.count(url) == 1
    request = next(row for row in result["requests"] if row["ticker"] == "AAPL")
    assert request["transport_outcome"] == "redirect_rejected"
    assert request["received_bytes"] is not None


@pytest.mark.parametrize("changes,reason", [
    ({"user_agent": "invalid"}, "sec_compliant_user_agent_required"),
    ({"manifest": (replace(MANIFEST[0], fiscal_year=2023),) + MANIFEST[1:]}, "metadata_manifest_mismatch"),
    ({"aggregate_budget": 3}, "metadata_budget_mismatch"),
    ({"per_issuer_budget": 2}, "metadata_budget_mismatch"),
    ({"enabled_request_classes": ("current_submissions", "ten_k_document")}, "metadata_request_class_mismatch"),
    ({"http_attempts": 2}, "metadata_retries_enabled"),
    ({"follow_redirects": True}, "metadata_redirects_enabled"),
])
def test_metadata_only_preflight_failures_dispatch_nothing(changes, reason):
    transport = FixtureTransport(fixture()["responses"])
    arguments = {"user_agent": "test@example.com", **changes}
    runner = MetadataOnlyDiscoveryRunner(transport, **arguments)
    with pytest.raises(ProviderUnavailable, match=reason):
        runner.run()
    assert transport.calls == [] and runner.attempts == 0


def test_metadata_only_populates_all_four_sequential_counter_outcomes():
    payload = fixture(multiple_8k=True)
    aapl_url = "https://data.sec.gov/submissions/CIK0000320193.json"
    recent = payload["responses"][aapl_url]["json"]["filings"]["recent"]
    for index, form in enumerate(recent["form"]):
        if form == "8-K" and recent["reportDate"][index] == "2025-09-27":
            recent["items"][index] = "9.01"
    result, _ = metadata_run(payload)
    aapl_2024 = next(row for row in result["targets"] if row["ticker"] == "AAPL" and row["fiscal_year"] == 2024)
    aapl_2025 = next(row for row in result["targets"] if row["ticker"] == "AAPL" and row["fiscal_year"] == 2025)
    assert aapl_2024["discovery_state"] == "ambiguous"
    assert aapl_2024["discovery_diagnostics"]["ambiguous_qualifying_candidates"] == 2
    assert aapl_2025["discovery_state"] == "source_unavailable"
    assert aapl_2025["discovery_diagnostics"]["rows_rejected_by_item_202"] == 1
    assert all(row["discovery_diagnostics"]["count_semantics"] == "sequential_first_failure"
        for row in result["targets"])


def test_metadata_only_artifact_excludes_filing_level_metadata_and_secrets():
    result, _ = metadata_run(fixture(multiple_8k=True))
    serialized = json.dumps(result)
    for forbidden in ("900000", "eight-2024.htm", "2.02,9.01", "2024-10-18",
            "operator@example.com", "response_body", "headers"):
        assert forbidden not in serialized
    assert "primary_document" in serialized  # bounded counter name only


def test_metadata_only_class_has_no_document_parser_or_production_path():
    source = inspect.getsource(MetadataOnlyDiscoveryRunner)
    assert "_document_url" not in source
    assert "qualify_direct_q4" not in source
    assert "DirectQ4Document" not in source
    from app.services.outlook import configured_providers
    assert all(item.name != "sec_q4_metadata_discovery" for item in configured_providers())


def test_metadata_live_gate_requires_exact_flag_acknowledgment_and_contact():
    with pytest.raises(ProviderUnavailable, match="live_flag_required"):
        validate_metadata_live_gate(live=False, acknowledgment=METADATA_ACKNOWLEDGMENT,
            user_agent="test@example.com")
    with pytest.raises(ProviderUnavailable, match="acknowledgment"):
        validate_metadata_live_gate(live=True, acknowledgment="2", user_agent="test@example.com")
    with pytest.raises(ProviderUnavailable, match="user_agent"):
        validate_metadata_live_gate(live=True, acknowledgment=METADATA_ACKNOWLEDGMENT,
            user_agent="invalid")


def test_metadata_offline_cli_creates_non_overwriting_artifact(tmp_path, monkeypatch, capsys):
    fixture_path = tmp_path / "metadata.json"
    fixture_path.write_text(json.dumps(fixture()), encoding="utf-8")
    repository = tmp_path / "repository"
    output = repository / "docs" / "diagnostics"
    import app.cli.inspect_q4_metadata as cli
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", repository)
    assert metadata_main(["--fixture", str(fixture_path), "--output-dir", str(output)]) == 0
    first = capsys.readouterr().out.strip()
    artifact = json.loads(open(first, encoding="utf-8").read())
    assert artifact["mode"] == "offline" and artifact["budget"]["attempts"] == 2
    assert artifact["runner"] == "direct-q4-metadata-discovery-2"
    assert artifact["discovery_policy"] == "bounded-filing-window-item-202-1"
    assert "phase6b5c2a5h-metadata-discovery-v2-" in first
    class FixedDatetime:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    fixed = cli._output_path(output)
    fixed.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "MetadataOnlyDiscoveryRunner",
        lambda *args, **kwargs: pytest.fail("runner must not be constructed before overwrite check"))
    with pytest.raises(FileExistsError):
        metadata_main(["--fixture", str(fixture_path), "--output-dir", str(output)])
