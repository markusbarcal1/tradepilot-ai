"""Offline qualification for the release-structure diagnostic and future runner."""
from datetime import datetime
import inspect
import json

import pytest

from app.cli.certify_q4_release_structure import main as cli_main
from app.services.outlook import configured_providers
from app.services.outlook_structured.q4_certification import FixtureTransport, MANIFEST
from app.services.outlook_structured.q4_direct import qualify_direct_q4
from app.services.outlook_structured.q4_release_structure import (
    COUNT_CAP, DIAGNOSTIC_VERSION, diagnose_release_structure,
)
from app.services.outlook_structured.q4_release_structure_runner import (
    ACKNOWLEDGMENT, AGGREGATE_LIMIT, CLASS_LIMITS, PER_ISSUER_LIMIT, RUNNER_VERSION,
    ReleaseStructureBudget, ReleaseStructureCertificationRunner, validate_live_gate,
)
from app.services.outlook_structured.transport import ProviderUnavailable
from tests.test_q4_parser_layout_audit import CASES, PERIOD, document, table
from tests.test_q4_primary_relationship import runner_fixture


@pytest.mark.parametrize("name,html,expected_count,accepted,rejections", CASES,
    ids=[case[0] for case in CASES])
def test_all_phase5o_layouts_correlate_without_value_leakage(
        name, html, expected_count, accepted, rejections):
    source = document(html)
    diagnostic = diagnose_release_structure(source)
    actual = qualify_direct_q4((source,))
    assert diagnostic["diagnostic"] == DIAGNOSTIC_VERSION
    assert diagnostic["candidate_stages"]["predicted_direct_q4_candidates"] == len(actual.candidates)
    assert len(actual.candidates) == expected_count
    serialized = json.dumps(diagnostic, sort_keys=True)
    for value in ("12.5", "1.25", "48.0", "10.0", "12,500"):
        assert value not in serialized, name
    assert diagnostic["fiscal_target_reconciliation_performed"] is False


@pytest.mark.parametrize("html,reasons", [
    (f"<h2>{PERIOD}</h2><div>Revenue (USD millions) $987654321.123456</div>",
        {"no_literal_table", "period_only_outside_table", "no_exact_metric_label"}),
    ("<table><tr><td>layout</td></tr></table>" * 8 +
        table('<tr><td>Revenue (USD millions)</td><td>$987654321.123456</td></tr>'),
        {"financial_table_beyond_current_cap"}),
    (table('<tr><td></td><td>Revenue (USD millions)</td><td>$987654321.123456</td></tr>'),
        {"no_exact_metric_label", "normalized_metric_label_only"}),
    (table('<tr><td>Total revenue (USD millions)</td><td>$987654321.123456</td></tr>'),
        {"normalized_metric_label_only"}),
    (table('<tr><td>GAAP Diluted earnings per share (USD/share)</td><td>$987654321.123456</td></tr>'),
        {"normalized_metric_label_only"}),
    (table('<tr><td>Revenue</td><td>$987654321.123456</td></tr>'),
        {"metric_without_row_level_unit", "current_parser_candidate_exists"}),
])
def test_diagnostic_reason_categories_are_bounded_and_multi_causal(html, reasons):
    result = diagnose_release_structure(document(html))
    assert reasons <= set(result["zero_candidate_reasons"])
    assert all(reason in {
        "no_literal_table", "no_complete_table", "financial_table_beyond_current_cap",
        "no_in_table_period_pattern", "period_only_outside_table", "no_exact_metric_label",
        "normalized_metric_label_only", "metric_period_separated",
        "metric_without_later_numeric_shape", "metric_without_row_level_unit",
        "structural_ambiguity", "nested_or_malformed_structure",
        "current_parser_candidate_exists", "unresolved_structure"
    } for reason in result["zero_candidate_reasons"])


def test_structural_categories_phase3b_comparison_and_saturation():
    rich = table('<tr><th colspan="2">Revenue (USD millions)</th><th>$9</th></tr>'
        '<tr><td rowspan="2">GAAP Diluted EPS (USD/share)</td><td><strong>$1</strong></td></tr>')
    result = diagnose_release_structure(document(rich))
    assert result["counts"]["colspan_cells"] == 1
    assert result["counts"]["nonunit_rowspan_cells"] == 1
    assert result["counts"]["inline_fragmented_cells"] == 1
    assert result["phase3b_comparison"]["phase3b_rejects_structure_direct_retains"]
    saturated = diagnose_release_structure(document("<table></table>" * (COUNT_CAP + 20)))
    assert saturated["counts"]["table_starts"] == COUNT_CAP
    assert saturated["counts_saturated"] is True


def test_sentinel_sanitization_and_schema_contains_no_source_identity_or_value_fields():
    sentinels = ["SENTINEL_TICKER_PROSE", "secret-file-771.htm", "SECRET_ACCESSION_771",
        "https://secret.invalid/771", "HEADING_SECRET_771", "987654321.123456",
        "0.987654321", "73.987654321%", "ARBITRARY_CELL_SECRET_771",
        "FOOTNOTE_SECRET_771", "credential=SECRET_771"]
    html = (f'<h1>{sentinels[4]}</h1><table><tr><th>{PERIOD}</th></tr>'
        f'<tr><td>Revenue (USD millions) {sentinels[8]}</td><td>${sentinels[5]}</td></tr>'
        f'<tr><td>GAAP Diluted EPS (USD/share)</td><td>${sentinels[6]}</td></tr>'
        f'<tr><td>{sentinels[0]} {sentinels[1]} {sentinels[2]} {sentinels[3]}</td></tr>'
        f'<tr><td>{sentinels[7]} {sentinels[9]} {sentinels[10]}</td></tr></table>')
    serialized = json.dumps(diagnose_release_structure(document(html)), sort_keys=True)
    assert not any(value in serialized for value in sentinels)
    forbidden_keys = ("raw_text", "raw_html", "url", "filename", "accession", "document_id",
        "user_agent", "exception", "financial_value", "amount", "percentage")
    payload = json.loads(serialized)
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert not any(token in key.lower() for token in forbidden_keys)
                walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(payload)


def run(value, **changes):
    transport = FixtureTransport(value["responses"])
    runner = ReleaseStructureCertificationRunner(transport,
        user_agent="TradePilot offline operator@example.com", **changes)
    return runner.run(), transport


def test_runner_identities_fixed_manifest_budget_and_candidate_correlation():
    result, transport = run(runner_fixture())
    assert (result["diagnostic"], result["runner"], result["relationship_policy"],
        result["discovery_policy"], result["parser"]) == (
        DIAGNOSTIC_VERSION, RUNNER_VERSION, "sec-primary-explicit-exhibit99-relationship-1",
        "bounded-filing-window-item-202-1", "direct-q4-1")
    assert [(row["ticker"], row["fiscal_year"]) for row in result["manifest"]] == [
        ("AAPL", 2024), ("AAPL", 2025), ("NVDA", 2025), ("NVDA", 2026)]
    assert result["budget"]["attempts"] == AGGREGATE_LIMIT == 10
    assert result["budget"]["per_issuer"] == {"AAPL": 5, "NVDA": 5}
    assert CLASS_LIMITS == {"current_submissions": 2, "selected_primary_document": 4,
        "earnings_exhibit": 4, "filing_index": 0}
    assert all(row["structure"]["candidate_stages"]["predicted_direct_q4_candidates"]
        == row["actual_parser_candidate_count"] for row in result["targets"])
    assert len(transport.calls) == 10 and not any(url.endswith("index.json") for url in transport.calls)


def test_budget_is_nontransferable_and_charged_before_failed_dispatch():
    ledger = ReleaseStructureBudget()
    ledger.charge("AAPL", 2024, "selected_primary_document")
    with pytest.raises(ProviderUnavailable):
        ledger.charge("AAPL", 2024, "selected_primary_document")
    with pytest.raises(ProviderUnavailable):
        ledger.charge("AAPL", 2024, "filing_index")
    assert ledger.aggregate == 1
    value = runner_fixture()
    first = next(url for url in value["responses"] if "/eight-" in url)
    value["responses"][first] = {"raise": "timeout"}
    result, _ = run(value)
    assert result["budget"]["attempts"] >= 1
    assert any(row["primary"]["transport"] == "timeout" for row in result["targets"])


@pytest.mark.parametrize("failure", ["timeout", "redirect_rejected", "response_size_rejected"])
def test_bounded_transport_failure_stops_before_relationship_and_exhibit(failure):
    value = runner_fixture()
    for url in list(value["responses"]):
        if "/eight-" in url:
            value["responses"][url] = {"raise": failure}
    result, transport = run(value)
    assert all(row["primary"]["transport"] == failure for row in result["targets"])
    assert all(row["relationship"]["state"] == "not_evaluated" for row in result["targets"])
    assert result["budget"]["class_attempts"]["earnings_exhibit"] == 0


@pytest.mark.parametrize("relationship", ["none", "many"])
def test_relationship_failure_or_ambiguity_stops_without_exhibit(relationship):
    result, _ = run(runner_fixture(relationship=relationship))
    assert result["budget"]["class_attempts"]["earnings_exhibit"] == 0
    assert all(row["structure"] is None for row in result["targets"])


@pytest.mark.parametrize("changes,reason", [
    ({"aggregate_budget": 9}, "release_structure_budget_mismatch"),
    ({"http_attempts": 2}, "release_structure_retries_enabled"),
    ({"follow_redirects": True}, "release_structure_redirects_enabled"),
    ({"timeout": 6}, "release_structure_transport_mismatch"),
    ({"max_bytes": 100}, "release_structure_transport_mismatch"),
])
def test_runner_preflight_is_exact_and_dispatches_nothing(changes, reason):
    transport = FixtureTransport(runner_fixture()["responses"])
    runner = ReleaseStructureCertificationRunner(transport,
        user_agent="operator@example.com", **changes)
    with pytest.raises(ProviderUnavailable, match=reason): runner.run()
    assert transport.calls == []


def test_runner_artifact_is_sanitized_and_production_isolated():
    result, _ = run(runner_fixture())
    serialized = json.dumps(result, sort_keys=True)
    for forbidden in ("release.htm", "eight-2024.htm", "accession", "document_url",
            "user_agent", "headers", "@example.com", "Fourth Quarter Ended", "$12.5"):
        assert forbidden not in serialized
    assert all(getattr(provider, "name", None) not in (RUNNER_VERSION, DIAGNOSTIC_VERSION)
        for provider in configured_providers())
    source = inspect.getsource(diagnose_release_structure)
    assert "SecEvidenceProvider" not in source and "request(" not in source


def test_live_gate_requires_exact_flag_acknowledgment_and_contact():
    with pytest.raises(ProviderUnavailable, match="live_flag_required"):
        validate_live_gate(live=False, acknowledgment=ACKNOWLEDGMENT,
            user_agent="operator@example.com")
    with pytest.raises(ProviderUnavailable, match="exact_release_structure"):
        validate_live_gate(live=True, acknowledgment="wrong", user_agent="operator@example.com")
    with pytest.raises(ProviderUnavailable, match="sec_compliant"):
        validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT, user_agent="invalid")
    validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT,
        user_agent="operator@example.com")


def test_fixture_cli_writes_immutable_offline_artifact(tmp_path, monkeypatch, capsys):
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(runner_fixture(relationship="none")), encoding="utf-8")
    repository = tmp_path / "repository"
    output = repository / "docs" / "diagnostics"
    import app.cli.certify_q4_release_structure as cli
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", repository)
    class FixedDatetime:
        @classmethod
        def now(cls, tz): return datetime(2026, 1, 1, tzinfo=tz)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    args = ["--fixture", str(fixture), "--output-dir", str(output)]
    assert cli_main(args) == 0
    artifact = capsys.readouterr().out.strip()
    payload = json.loads(open(artifact, encoding="utf-8").read())
    assert payload["runner"] == RUNNER_VERSION and payload["mode"] == "offline"
    with pytest.raises(FileExistsError): cli_main(args)
