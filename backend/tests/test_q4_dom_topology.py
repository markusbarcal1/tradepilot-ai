"""Offline qualification for DOM-topology diagnostics and the future runner."""
from datetime import datetime
import inspect
import json

import pytest

from app.cli.certify_q4_dom_topology import main as cli_main
from app.services.outlook import configured_providers
from app.services.outlook_structured.q4_certification import FixtureTransport
from app.services.outlook_structured.q4_dom_topology import (
    DIAGNOSTIC_VERSION, PAIR_CAP, PERIOD_NODE_CAP, diagnose_dom_topology,
)
from app.services.outlook_structured.q4_dom_topology_runner import (
    ACKNOWLEDGMENT, RUNNER_VERSION, DomTopologyCertificationRunner, validate_live_gate,
)
from app.services.outlook_structured.q4_release_structure_runner import (
    AGGREGATE_LIMIT, CLASS_LIMITS, PER_ISSUER_LIMIT, ReleaseStructureBudget,
)
from app.services.outlook_structured.transport import ProviderUnavailable
from tests.test_q4_parser_layout_audit import document
from tests.test_q4_primary_relationship import runner_fixture


PERIOD = "Fourth Quarter Ended 2025-10-01 to 2025-12-31"
ROW = '<tr><td>Revenue (USD millions)</td><td>$987654321.123456</td></tr>'
TABLE = f"<table>{ROW}</table>"


CASES = [
    ("immediate-heading", f"<h2>{PERIOD}</h2>{TABLE}"),
    ("bounded-prose", f"<h2>{PERIOD}</h2><p>ordinary</p>{TABLE}"),
    ("two-tables", f"<h2>{PERIOD}</h2>{TABLE}{TABLE}"),
    ("two-headings", f"<h2>{PERIOD}</h2><h3>Q4 results</h3>{TABLE}"),
    ("annual-quarterly", f"<h2>Fiscal Year 2025</h2><h3>{PERIOD}</h3>{TABLE}"),
    ("conflicting-caption", f"<h2>{PERIOD}</h2><table><caption>Fiscal Year 2025</caption>{ROW}</table>"),
    ("nested-section", f"<section><h2>{PERIOD}</h2><section>{TABLE}</section></section>"),
    ("sibling-section", f"<section><h2>{PERIOD}</h2></section><section>{TABLE}</section>"),
    ("caption", f"<table><caption>{PERIOD}</caption>{ROW}</table>"),
    ("title-row", f"<table><tr><th>{PERIOD}</th></tr>{ROW}</table>"),
    ("unrelated-before", f"<p>{PERIOD}</p>{TABLE}"),
    ("unrelated-after", f"{TABLE}<p>{PERIOD}</p>"),
    ("multiple-quarter-headings", f"<h2>Q4 results</h2><h3>{PERIOD}</h3>{TABLE}"),
    ("duplicate-headings", f"<h2>{PERIOD}</h2><h2>{PERIOD}</h2>{TABLE}"),
    ("presentation-wrapper", f"<table><tr><td><h2>{PERIOD}</h2>{TABLE}</td></tr></table>"),
    ("nested-table", f"<h2>{PERIOD}</h2><table><tr><td>{TABLE}</td></tr></table>"),
    ("malformed-table", f"<h2>{PERIOD}</h2><table><tr><td>Revenue<td>$1</tr></table>"),
    ("hidden-heading", f"<h2 hidden>{PERIOD}</h2>{TABLE}"),
    ("colspan", f"<h2>{PERIOD}</h2><table><tr><th colspan='2'>Header</th></tr>{ROW}</table>"),
    ("rowspan", f"<h2>{PERIOD}</h2><table><tr><th rowspan='2'>Header</th></tr>{ROW}</table>"),
    ("metric-first", f"<h2>{PERIOD}</h2>{TABLE}"),
    ("metric-leading-blank", f"<h2>{PERIOD}</h2><table><tr><td></td><td>Revenue</td><td>$1</td></tr></table>"),
    ("inline-footnote", f"<h2>{PERIOD}</h2><table><tr><td>Revenue<sup>1</sup></td><td>$1</td></tr></table>"),
    ("total-revenue", f"<h2>{PERIOD}</h2><table><tr><td>Total revenue</td><td>$1</td></tr></table>"),
    ("consolidated-revenue", f"<h2>{PERIOD}</h2><table><tr><td>Consolidated revenue</td><td>$1</td></tr></table>"),
    ("exact-revenue", f"<h2>{PERIOD}</h2><table>{ROW}</table>"),
    ("gaap-diluted-eps", f"<h2>{PERIOD}</h2><table><tr><td>GAAP Diluted EPS</td><td>$1</td></tr></table>"),
    ("diluted-no-gaap", f"<h2>{PERIOD}</h2><table><tr><td>Diluted earnings per share</td><td>$1</td></tr></table>"),
    ("basic-eps", f"<h2>{PERIOD}</h2><table><tr><td>Basic EPS</td><td>$1</td></tr></table>"),
    ("gaap-nongaap", f"<h2>{PERIOD}</h2><table><tr><td>GAAP Diluted EPS</td><td>$1</td></tr><tr><td>Non-GAAP Diluted EPS</td><td>$2</td></tr></table>"),
    ("current-prior", f"<h2>{PERIOD}</h2><table><tr><th>Current</th><th>Prior</th></tr>{ROW}</table>"),
    ("quarter-annual", f"<h2>{PERIOD}</h2><table><tr><th>Quarter</th><th>Annual</th></tr>{ROW}</table>"),
    ("nine-tables", f"<h2>{PERIOD}</h2>" + TABLE * 9),
    ("structural-bound", f"<h2>{PERIOD}</h2>" + TABLE * 33),
    ("fiscal-mismatch", f"<h2>{PERIOD}</h2>{TABLE}"),
    ("noncalendar-fiscal", "<h2>Fourth Quarter Ended 2025-08-01 to 2025-10-31</h2>" + TABLE),
    ("ambiguous-period", f"<h2>{PERIOD}</h2><h3>Q4 FY2025</h3>{TABLE}"),
    ("duplicate-evidence", f"<h2 id='title'>{PERIOD}</h2><table aria-labelledby='title'>{ROW}</table>"),
]


@pytest.mark.parametrize("name,html", CASES, ids=[row[0] for row in CASES])
def test_all_phase5q_fixture_shapes_are_deterministic_bounded_and_sanitized(name, html):
    first = diagnose_dom_topology(document(html))
    second = diagnose_dom_topology(document(html))
    assert first == second
    assert first["diagnostic"] == DIAGNOSTIC_VERSION
    assert first["financial_qualification_performed"] is False
    assert first["structural_association_component_invoked"] is False
    assert first["fiscal_target_reconciliation_performed"] is False
    assert len(first["period_nodes"]) <= PERIOD_NODE_CAP
    assert len(first["pairs"]) <= PAIR_CAP
    serialized = json.dumps(first, sort_keys=True)
    for forbidden in ("2025-10-01", "2025-12-31", "987654321.123456", "USD millions"):
        assert forbidden not in serialized, name


@pytest.mark.parametrize("level", range(1, 7))
def test_native_headings_same_parent_immediately_preceding_table_match(level):
    result = diagnose_dom_topology(document(f"<h{level}>{PERIOD}</h{level}>{TABLE}"))
    node = result["period_nodes"][0]
    pair = result["pairs"][0]
    assert node["node_type"] == f"h{level}" and node["semantic_category"] == "native_heading"
    assert pair["same_parent"]["same_parent"] and pair["same_parent"]["heading_precedes_table"]
    assert pair["rule_outcomes"]["same_parent_sibling"] == "structurally_matches"
    assert result["summary"]["unique_topology_candidate_count"] == 1


def test_sibling_distance_eight_resolves_and_nine_caps():
    eight = diagnose_dom_topology(document(f"<h2>{PERIOD}</h2>" + "<p>x</p>"*8 + TABLE))
    nine = diagnose_dom_topology(document(f"<h2>{PERIOD}</h2>" + "<p>x</p>"*9 + TABLE))
    assert eight["pairs"][0]["same_parent"]["significant_nodes_between"] == 8
    assert eight["pairs"][0]["rule_outcomes"]["same_parent_sibling"] == "structurally_matches"
    assert nine["pairs"][0]["same_parent"]["traversal_cap_exceeded"]
    assert nine["pairs"][0]["rule_outcomes"]["same_parent_sibling"] == "capped"


def test_competing_headings_tables_sections_and_ordinary_prose_are_distinct():
    two_tables = diagnose_dom_topology(document(f"<h2>{PERIOD}</h2>{TABLE}{TABLE}"))
    assert two_tables["pairs"][0]["rule_outcomes"]["same_parent_sibling"] == "ambiguous"
    two_headings = diagnose_dom_topology(document(f"<h2>{PERIOD}</h2><h3>Q4 FY2025</h3>{TABLE}"))
    assert any(pair["same_parent"]["competing_heading_between"] for pair in two_headings["pairs"])
    prose = diagnose_dom_topology(document(f"<p>{PERIOD}</p>{TABLE}"))
    assert prose["period_nodes"][0]["semantic_category"] == "ordinary_block"
    assert prose["summary"]["unique_topology_candidate_count"] == 0


def test_explicit_section_caption_role_heading_and_title_reference_topology():
    section = diagnose_dom_topology(document(f"<section><h2>{PERIOD}</h2>{TABLE}</section>"))
    assert section["pairs"][0]["rule_outcomes"]["explicit_section"] == "structurally_matches"
    caption = diagnose_dom_topology(document(f"<table><caption>{PERIOD}</caption>{ROW}</table>"))
    assert caption["pairs"][0]["rule_outcomes"]["caption"] == "structurally_matches"
    role = diagnose_dom_topology(document(f"<div role='heading' aria-level='2'>{PERIOD}</div>{TABLE}"))
    assert role["period_nodes"][0]["role_heading_level_category"] == "valid_bounded"
    assert role["pairs"][0]["rule_outcomes"]["semantic_heading_role"] == "structurally_matches"
    invalid = diagnose_dom_topology(document(f"<div role='heading' aria-level='9'>{PERIOD}</div>{TABLE}"))
    assert invalid["period_nodes"][0]["role_heading_level_category"] == "invalid_or_missing"
    title = diagnose_dom_topology(document(f"<h2 id='secret-title'>{PERIOD}</h2><table aria-labelledby='secret-title'>{ROW}</table>"))
    assert title["pairs"][0]["rule_outcomes"]["title_reference"] == "reference_uniquely_resolves"
    assert "secret-title" not in json.dumps(title)


def test_caption_cardinality_depth_section_and_pair_bounds_fail_closed():
    captions = diagnose_dom_topology(document(f"<table><caption>{PERIOD}</caption><caption>Q4</caption>{ROW}</table>"))
    assert any(pair["caption"]["caption_cardinality"] == 2 for pair in captions["pairs"])
    deep = diagnose_dom_topology(document("<section>"*5 + f"<h2>{PERIOD}</h2>{TABLE}" + "</section>"*5))
    assert any(node["ancestor_depth_capped"] for node in deep["period_nodes"])
    many_periods = diagnose_dom_topology(document("".join(f"<h2>Q4 FY20{i:02d}</h2>" for i in range(30)) + TABLE*16))
    assert many_periods["cap_flags"]["period_node_cap_exceeded"]
    assert many_periods["cap_flags"]["pair_cap_exceeded"]
    assert many_periods["summary"]["unique_topology_candidate_count"] == 0


def test_table_observations_metric_bits_cap_colspan_rowspan_and_nested_state():
    html = (f"<h2>{PERIOD}</h2><table><tr><th colspan='2'>Header</th></tr>"
        "<tr><td rowspan='2'>GAAP Diluted EPS</td><td>$1</td></tr></table>")
    result = diagnose_dom_topology(document(html))
    table = result["tables"][0]
    assert table["colspan_present"] and table["nonunit_rowspan_present"]
    assert table["metric_category_bits"]
    nine = diagnose_dom_topology(document(f"<h2>{PERIOD}</h2>" + TABLE*9))
    assert nine["tables"][8]["current_cap_category"] == "beyond_first_eight"
    nested = diagnose_dom_topology(document(f"<table><tr><td>{TABLE}</td></tr></table>"))
    assert nested["tables"][0]["nested"] and nested["tables"][0]["phase3b_category"] == "rejected"


def test_aggressive_sentinel_leakage_and_fixed_schema_keys():
    sentinels = ["HEADING_SECRET_991", "2044-07-13", "2044-10-12", "987654321.123456",
        "0.876543219", "73.876543219%", "secret-file-991.htm", "https://secret.invalid/991",
        "SECRET_ACCESSION_991", "SECRET_HTML_ID_991", "SECRET_CLASS_991", "SECRET_STYLE_991",
        "SECRET_DATA_991", "SECRET_ARIA_991", "FOOTNOTE_SECRET_991", "credential=SECRET_991"]
    html = (f"<h2 id='{sentinels[9]}' class='{sentinels[10]}' style='{sentinels[11]}' "
        f"data-secret='{sentinels[12]}' aria-label='{sentinels[13]}'>Fourth Quarter Ended "
        f"{sentinels[1]} to {sentinels[2]} {sentinels[0]}</h2><table aria-labelledby='{sentinels[9]}'>"
        f"<tr><td>Revenue<sup>{sentinels[14]}</sup></td><td>${sentinels[3]}</td></tr>"
        f"<tr><td>EPS</td><td>{sentinels[4]} {sentinels[5]}</td></tr><tr><td>"
        + " ".join(sentinels[6:9] + [sentinels[15]]) + "</td></tr></table>")
    payload = diagnose_dom_topology(document(html))
    serialized = json.dumps(payload, sort_keys=True)
    assert not any(value in serialized for value in sentinels)
    forbidden_key_parts = ("raw", "text", "extracted_date", "url", "filename", "accession", "html_id",
        "class_name", "selector", "xpath", "attribute", "financial_value", "exception", "hash")
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert not any(part in key.lower() for part in forbidden_key_parts)
                walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(payload)


def run(value, **changes):
    transport = FixtureTransport(value["responses"])
    runner = DomTopologyCertificationRunner(transport,
        user_agent="TradePilot offline operator@example.com", **changes)
    return runner.run(), transport


def test_runner_identity_manifest_budget_and_no_financial_parser(monkeypatch):
    import app.services.outlook_structured.q4_dom_topology_runner as module
    calls = []
    original = module.diagnose_dom_topology
    monkeypatch.setattr(module, "diagnose_dom_topology", lambda doc: (calls.append(doc) or original(doc)))
    result, transport = run(runner_fixture())
    assert result["runner"] == RUNNER_VERSION and result["diagnostic"] == DIAGNOSTIC_VERSION
    assert result["schema_version"] == "1" and len(calls) == 4
    assert [(row["ticker"], row["fiscal_year"]) for row in result["manifest"]] == [
        ("AAPL", 2024), ("AAPL", 2025), ("NVDA", 2025), ("NVDA", 2026)]
    assert result["budget"]["attempts"] == AGGREGATE_LIMIT == 10
    assert result["budget"]["per_issuer"] == {"AAPL": 5, "NVDA": 5}
    assert CLASS_LIMITS["filing_index"] == 0 and not any(url.endswith("index.json") for url in transport.calls)
    assert "qualify_direct_q4" not in inspect.getsource(module)


def test_budget_transport_and_relationship_stops_are_preserved():
    ledger = ReleaseStructureBudget(); ledger.charge("AAPL", 2024, "selected_primary_document")
    with pytest.raises(ProviderUnavailable): ledger.charge("AAPL", 2024, "selected_primary_document")
    with pytest.raises(ProviderUnavailable): ledger.charge("AAPL", 2024, "filing_index")
    for relationship in ("none", "many"):
        result, _ = run(runner_fixture(relationship=relationship))
        assert result["budget"]["class_attempts"]["earnings_exhibit"] == 0
        assert all(row["topology"] is None for row in result["targets"])


@pytest.mark.parametrize("changes,reason", [
    ({"aggregate_budget": 9}, "dom_topology_budget_mismatch"),
    ({"http_attempts": 2}, "dom_topology_retries_enabled"),
    ({"follow_redirects": True}, "dom_topology_redirects_enabled"),
    ({"timeout": 6}, "dom_topology_transport_mismatch"),
    ({"max_bytes": 100}, "dom_topology_transport_mismatch"),
])
def test_preflight_guards_dispatch_nothing(changes, reason):
    transport = FixtureTransport(runner_fixture()["responses"])
    runner = DomTopologyCertificationRunner(transport, user_agent="operator@example.com", **changes)
    with pytest.raises(ProviderUnavailable, match=reason): runner.run()
    assert transport.calls == []


def test_runner_artifact_sanitization_registration_and_live_gate():
    result, _ = run(runner_fixture())
    serialized = json.dumps(result)
    for forbidden in ("release.htm", "eight-2024.htm", "accession", "document_url",
            "user_agent", "headers", "@example.com", "Fourth Quarter Ended", "$12.5"):
        assert forbidden not in serialized
    assert all(getattr(provider, "name", None) not in (RUNNER_VERSION, DIAGNOSTIC_VERSION)
        for provider in configured_providers())
    with pytest.raises(ProviderUnavailable, match="live_flag_required"):
        validate_live_gate(live=False, acknowledgment=ACKNOWLEDGMENT, user_agent="operator@example.com")
    with pytest.raises(ProviderUnavailable, match="exact_dom_topology"):
        validate_live_gate(live=True, acknowledgment="wrong", user_agent="operator@example.com")
    validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT, user_agent="operator@example.com")


def test_fixture_cli_is_immutable_and_offline(tmp_path, monkeypatch, capsys):
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(runner_fixture(relationship="none")), encoding="utf-8")
    repository = tmp_path / "repository"; output = repository / "docs" / "diagnostics"
    import app.cli.certify_q4_dom_topology as cli
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
