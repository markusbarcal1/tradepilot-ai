"""Offline safeguards for the eight-document revenue certification runner."""
from copy import deepcopy
import inspect
import json

import pytest

from app.cli.certify_inline_revenue_operands import main as cli_main
from app.services.outlook_structured.inline_revenue_document_certification import (
    ACKNOWLEDGMENT, ARTIFACT_SCHEMA, EXPECTED_FINGERPRINT, RUNNER_VERSION,
    EightDocumentCertificationRunner, assess_partition_replay_evidence,
    load_reviewed_manifest, reconstruct_revenue_operand,
    replay_certification_artifact_partitions, serialize_revenue_operand_replay_evidence,
    validate_live_gate,
)
from app.services.outlook_structured.inline_revenue_operand import (
    qualify_inline_revenue_operand, validate_revenue_operand_partition,
)
from app.services.outlook_structured.q4_certification import FixtureTransport
from app.services.outlook_structured.transport import ProviderUnavailable


MANIFEST_PATH = "../docs/diagnostics/phase6b5c2a5w2-inline-revenue-metadata-20261001.json"
HISTORICAL_CERTIFICATION_PATH = (
    "../docs/diagnostics/phase6b5c2a5w6-qualifier-v2-live-certification-20261001.json")
STARTS = {("AAPL", "FY"): "2024-09-29", ("AAPL", "Q1"): "2024-09-29",
    ("AAPL", "Q2"): "2024-12-29", ("AAPL", "Q3"): "2025-03-30",
    ("NVDA", "FY"): "2025-01-27", ("NVDA", "Q1"): "2025-01-27",
    ("NVDA", "Q2"): "2025-04-28", ("NVDA", "Q3"): "2025-07-28"}


@pytest.fixture
def artifact():
    return json.loads(open(MANIFEST_PATH, encoding="utf-8").read())


def body(role, *, facts=None):
    year = role.target_fiscal_year
    us_gaap, dei = f"http://fasb.org/us-gaap/{year}", f"http://xbrl.sec.gov/dei/{year}"
    start, end = STARTS[(role.ticker, role.expected_role)], role.report_period_end.isoformat()
    facts = facts if facts is not None else ('<ix:nonFraction name="us-gaap:Revenues" '
        'contextRef="ctx" unitRef="usd" decimals="INF">1000</ix:nonFraction>')
    return f'''<html xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:dei="{dei}"
      xmlns:us-gaap="{us_gaap}" xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
      <ix:nonNumeric name="dei:DocumentFiscalYearFocus">{role.target_fiscal_year}</ix:nonNumeric>
      <ix:nonNumeric name="dei:DocumentFiscalPeriodFocus">{role.expected_role}</ix:nonNumeric>
      <ix:nonNumeric name="dei:DocumentPeriodEndDate">{end}</ix:nonNumeric>
      <ix:nonNumeric name="dei:DocumentType">{role.form}</ix:nonNumeric>
      <xbrli:context id="ctx"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{role.cik}</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>{facts}</html>'''


def fixture(reviewed, overrides=None):
    overrides = overrides or {}
    return {role.source_url: overrides.get(role.source_url, {"body": body(role)})
        for role in reviewed.roles}


def run(artifact, *, overrides=None, **changes):
    reviewed = load_reviewed_manifest(artifact)
    transport = FixtureTransport(fixture(reviewed, overrides))
    runner = EightDocumentCertificationRunner(transport, reviewed,
        user_agent="TradePilot operator@example.com", **changes)
    return runner.run(), transport, runner


def test_valid_reviewed_manifest_loads_and_both_fingerprints_verify(artifact):
    reviewed = load_reviewed_manifest(artifact)
    assert len(reviewed.roles) == 8
    assert reviewed.stored_fingerprint == EXPECTED_FINGERPRINT
    assert reviewed.recomputed_fingerprint == EXPECTED_FINGERPRINT


def test_missing_manifest_and_wrong_expected_fingerprint_are_rejected(artifact):
    with pytest.raises(ProviderUnavailable, match="manifest_missing"):
        load_reviewed_manifest({})
    with pytest.raises(ProviderUnavailable, match="fingerprint_mismatch"):
        load_reviewed_manifest(artifact, expected_fingerprint="0" * 64)


@pytest.mark.parametrize("mutation,reason", [
    (lambda row: row.update(ticker="MSFT"), "manifest_role_identity_mismatch"),
    (lambda row: row.update(source_url="https://www.sec.gov/Archives/other.htm"), "manifest_fingerprint_mismatch"),
    (lambda row: row.update(filing_date="2025-10-30"), "manifest_fingerprint_mismatch"),
])
def test_altered_identity_breaks_manifest(artifact, mutation, reason):
    changed = deepcopy(artifact); mutation(changed["manifest"]["roles"][0])
    with pytest.raises(ProviderUnavailable, match=reason): load_reviewed_manifest(changed)


def test_missing_duplicate_and_reordered_roles_are_rejected(artifact):
    missing = deepcopy(artifact); missing["manifest"]["roles"].pop()
    with pytest.raises(ProviderUnavailable, match="role_count"): load_reviewed_manifest(missing)
    duplicate = deepcopy(artifact); duplicate["manifest"]["roles"][1] = deepcopy(duplicate["manifest"]["roles"][0])
    with pytest.raises(ProviderUnavailable, match="role_identity"): load_reviewed_manifest(duplicate)
    reordered = deepcopy(artifact); reordered["manifest"]["roles"][0:2] = reversed(reordered["manifest"]["roles"][0:2])
    with pytest.raises(ProviderUnavailable, match="role_identity"): load_reviewed_manifest(reordered)


@pytest.mark.parametrize("path,value,reason", [
    (("manifest_ready",), False, "manifest_not_ready"),
    (("manifest", "target_set"), "other", "target_set_mismatch"),
    (("manifest", "manifest_policy"), "other", "manifest_policy_mismatch"),
    (("manifest", "schema_version"), "2", "manifest_schema_mismatch"),
])
def test_incomplete_or_wrong_manifest_identity_rejected(artifact, path, value, reason):
    changed = deepcopy(artifact); target = changed
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    with pytest.raises(ProviderUnavailable, match=reason): load_reviewed_manifest(changed)


def test_exact_acknowledgement_required():
    with pytest.raises(ProviderUnavailable, match="acknowledgement_missing"):
        validate_live_gate(live=False, acknowledgment=ACKNOWLEDGMENT, user_agent="x@y.com")
    with pytest.raises(ProviderUnavailable, match="acknowledgement_missing"):
        validate_live_gate(live=True, acknowledgment="8", user_agent="x@y.com")
    validate_live_gate(live=True, acknowledgment=ACKNOWLEDGMENT,
        user_agent="TradePilot operator@example.com")


def test_eight_nontransferable_attempts_and_exact_url_allowlist(artifact):
    result, transport, runner = run(artifact)
    assert result["budget"]["attempts_charged"] == 8 and len(transport.calls) == 8
    assert set(result["budget"]["per_role"].values()) == {1}
    role = runner.manifest.roles[0]
    with pytest.raises(ProviderUnavailable, match="attempt_budget_exhausted"):
        runner._get(role, role.source_url)
    fresh = EightDocumentCertificationRunner(FixtureTransport({}), runner.manifest,
        user_agent="x@y.com")
    with pytest.raises(ProviderUnavailable, match="url_not_allowed"):
        fresh._get(role, "https://data.sec.gov/submissions/CIK0000320193.json")
    with pytest.raises(ProviderUnavailable, match="url_not_allowed"):
        fresh._get(role, role.source_url.replace(role.primary_document, "alternate.htm"))
    assert fresh.transport.calls == [] and sum(fresh.attempts.values()) == 0


@pytest.mark.parametrize("response,outcome", [
    ({"raise": "timeout"}, "timeout"),
    ({"raise": "redirect_rejected"}, "redirect_rejected"),
    ({"status": 503, "body": "bounded"}, "http_error"),
    ({"raise": "response_size_rejected", "received_bytes": 4194305}, "response_size_rejected"),
])
def test_transport_failure_charges_once_and_never_invokes_qualifier(artifact, response, outcome):
    reviewed = load_reviewed_manifest(artifact); target = reviewed.roles[0]
    calls = []
    def qualifier(*args): calls.append(args); return qualify_inline_revenue_operand(*args)
    result, transport, _ = run(artifact, overrides={target.source_url: response}, qualifier=qualifier)
    first = result["roles"][0]
    assert first["attempt_charged"] and first["transport_outcome"] == outcome
    assert first["qualifier_invoked"] is False and len(calls) == 7
    assert all(args[0] != target for args in calls)
    assert transport.calls.count(target.source_url) == 1


def test_successful_bodies_invoke_qualifier_once_per_role_and_validate_partitions_once(artifact):
    qualifier_calls, partition_calls = [], []
    def qualifier(*args): qualifier_calls.append(args[0].expected_role); return qualify_inline_revenue_operand(*args)
    def partition(**kwargs): partition_calls.append(tuple(kwargs)); return validate_revenue_operand_partition(**kwargs)
    result, _, _ = run(artifact, qualifier=qualifier, partition_validator=partition)
    assert len(qualifier_calls) == 8 and len(partition_calls) == 2
    assert all(row["qualifier_state"] == "qualified" for row in result["roles"])
    assert all(row["state"] == "valid" for row in result["partitions"])
    assert result["certification_complete"] is True


@pytest.mark.parametrize("facts,state,reason", [
    ("", "unavailable", "concept_unavailable"),
    ('<ix:nonFraction name="us-gaap:Revenues" contextRef="ctx" unitRef="usd" decimals="INF">1000</ix:nonFraction>'
     '<ix:nonFraction name="us-gaap:SalesRevenueNet" contextRef="ctx" unitRef="usd" decimals="INF">1000</ix:nonFraction>',
     "ambiguous", "ambiguous_concept"),
    ('<ix:nonFraction name="us-gaap:Revenues" contextRef="ctx" unitRef="usd" decimals="INF">1000</ix:nonFraction>'
     '<ix:nonFraction name="us-gaap:Revenues" contextRef="ctx" unitRef="usd" decimals="INF">1001</ix:nonFraction>',
     "conflict", "duplicate_conflict"),
])
def test_qualifier_failure_states_and_reasons_are_preserved(artifact, facts, state, reason):
    reviewed = load_reviewed_manifest(artifact); target = reviewed.roles[0]
    result, _, _ = run(artifact, overrides={target.source_url: {"body": body(target, facts=facts)}})
    first = result["roles"][0]
    assert first["qualifier_state"] == state and reason in first["qualifier_failure_reasons"]
    assert result["partitions"][0]["validator_invoked"] is False


def test_parser_cap_failure_and_source_body_are_sanitized(artifact):
    reviewed = load_reviewed_manifest(artifact); target = reviewed.roles[0]
    facts = ''.join('<ix:nonFraction name="us-gaap:Revenues" contextRef="ctx" unitRef="usd" decimals="INF">1000</ix:nonFraction>' for _ in range(257))
    result, _, _ = run(artifact, overrides={target.source_url: {"body": body(target, facts=facts) + "TOP_SECRET_BODY"}})
    assert result["roles"][0]["qualifier_failure_reasons"] == ["parser_cap_exceeded"]
    assert result["roles"][0]["parser_cap_states"] == ["parser_cap_exceeded"]
    assert "TOP_SECRET_BODY" not in json.dumps(result)


def test_anchor_failure_serializes_diagnostic_without_changing_runner_semantics(artifact):
    reviewed = load_reviewed_manifest(artifact); target = reviewed.roles[0]
    invalid = body(target).replace(target.report_period_end.isoformat(), "September 27, 2025", 1)
    result, transport, _ = run(artifact, overrides={target.source_url: {"body": invalid}})
    first = result["roles"][0]
    diagnostic = {row["required_local_name"]: row for row in first["fiscal_anchor_diagnostic"]["anchors"]}
    assert first["qualifier_state"] == "conflict"
    assert first["qualifier_failure_reasons"] == ["fiscal_anchor_conflict"]
    assert diagnostic["DocumentPeriodEndDate"]["qualification_branch"] == "period_end_parse_invalid"
    assert first["attempt_charged"] and first["qualifier_invoked"]
    assert transport.calls.count(target.source_url) == 1
    assert result["partitions"][0]["validator_invoked"] is False


def test_partition_conflict_is_preserved_without_any_value_arithmetic(artifact):
    calls = []
    def conflict(**kwargs):
        calls.append(kwargs)
        result = validate_revenue_operand_partition(**kwargs)
        return result.model_copy(update={"state": "conflict", "reasons": ("synthetic_conflict",),
            "residual_period_start": None, "residual_period_end": None, "residual_duration_days": None})
    result, _, _ = run(artifact, partition_validator=conflict)
    assert len(calls) == 2 and all(row["state"] == "conflict" for row in result["partitions"])
    assert "synthetic_conflict" in result["partitions"][0]["reasons"]
    source = inspect.getsource(EightDocumentCertificationRunner).lower()
    assert "subtract" not in source and "q4observation" not in source and "earningspershare" not in source


def test_deterministic_sanitized_artifact_and_isolation(artifact):
    first = run(artifact)[0]; second = run(artifact)[0]
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    serialized = json.dumps(first).lower()
    for forbidden in ("<html", "response_body", "user-agent", "operator@example.com", "request_headers"):
        assert forbidden not in serialized
    import app.services.outlook_structured.inline_revenue_document_certification as module
    source = inspect.getsource(module).lower()
    for forbidden in ("configured_providers", "database", "outlook_research", "openai"):
        assert forbidden not in source


def test_complete_replay_evidence_round_trip_preserves_validator_fields_and_provenance(artifact):
    role = load_reviewed_manifest(artifact).roles[0]
    operand = qualify_inline_revenue_operand(role, body(role).encode()).operand
    evidence = serialize_revenue_operand_replay_evidence(operand)
    rebuilt = reconstruct_revenue_operand(evidence.model_dump(mode="json"))
    assert rebuilt.role == operand.role
    assert rebuilt.expanded_qname == operand.expanded_qname
    assert (rebuilt.unit.numerator_measures, rebuilt.unit.denominator_measures,
        rebuilt.unit.structural_form, rebuilt.unit.currency) == (
        operand.unit.numerator_measures, operand.unit.denominator_measures,
        operand.unit.structural_form, operand.unit.currency)
    assert rebuilt.context.entity_scheme == operand.context.entity_scheme
    assert rebuilt.context.entity_value == operand.context.entity_value
    assert rebuilt.context.period_start == operand.context.period_start
    assert rebuilt.context.period_end == operand.context.period_end
    assert rebuilt.context.explicit_dimensions == operand.context.explicit_dimensions
    assert rebuilt.context.typed_dimension_count == operand.context.typed_dimension_count
    assert rebuilt.accounting_basis == operand.accounting_basis
    assert rebuilt.target_fiscal_year == operand.target_fiscal_year
    assert rebuilt.reporting_scope == operand.reporting_scope
    assert rebuilt.provenance == evidence.provenance


def test_replay_dto_preserves_bounded_dimension_and_typed_scope_state(artifact):
    role = load_reviewed_manifest(artifact).roles[0]
    operand = qualify_inline_revenue_operand(role, body(role).encode()).operand
    payload = serialize_revenue_operand_replay_evidence(operand).model_dump(mode="json")
    payload["context"]["explicit_dimensions"] = [[
        {"namespace_uri": "urn:test", "local_name": "Axis"},
        {"namespace_uri": "urn:test", "local_name": "Member"}]]
    payload["context"]["typed_dimension_count"] = 1
    completeness, evidence = assess_partition_replay_evidence(payload)
    rebuilt = reconstruct_revenue_operand(evidence)
    assert completeness.state == "complete"
    assert rebuilt.context.explicit_dimensions == evidence.context.explicit_dimensions
    assert rebuilt.context.typed_dimension_count == 1


def test_future_runner_schema_and_complete_evidence_replay_same_partitions(artifact):
    result, _, _ = run(artifact)
    assert result["schema_version"] == ARTIFACT_SCHEMA == "2"
    assert result["runner"] == RUNNER_VERSION == "inline-revenue-eight-document-certification-2"
    assert all(row["partition_replay_completeness"] == {
        "state": "complete", "missing_fields": []} for row in result["roles"])
    replay = replay_certification_artifact_partitions(result)
    assert all(row["state"] == "replayed" for row in replay["partitions"])
    for direct, replayed in zip(result["partitions"], replay["partitions"]):
        value = replayed["partition_result"]
        assert value["state"] == direct["state"]
        assert value["reasons"] == direct["reasons"]
        assert value["residual_period_start"] == direct["residual_period_start"]
        assert value["residual_period_end"] == direct["residual_period_end"]
        assert value["residual_duration_days"] == direct["residual_duration_days"]
        assert value["concept_identity"] == direct["concept_identity"]


@pytest.mark.parametrize("path", [
    ("schema_version",), ("role",), ("expanded_qname",), ("canonical_unit",),
    ("canonical_unit", "numerator_measures"),
    ("canonical_unit", "denominator_measures"),
    ("canonical_unit", "structural_form"), ("canonical_unit", "currency"),
    ("context", "entity_scheme"), ("context", "entity_value"),
    ("context", "explicit_dimensions"), ("context", "typed_dimension_count"),
    ("context", "period_start"), ("context", "period_end"),
    ("accounting_basis",), ("target_fiscal_year",), ("reporting_scope",),
    ("provenance",),
])
def test_missing_required_replay_field_is_never_inferred(artifact, path):
    role = load_reviewed_manifest(artifact).roles[0]
    payload = serialize_revenue_operand_replay_evidence(
        qualify_inline_revenue_operand(role, body(role).encode()).operand).model_dump(mode="json")
    target = payload
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]
    completeness, evidence = assess_partition_replay_evidence(payload)
    assert completeness.state == "incomplete" and evidence is None
    assert ".".join(path) in completeness.missing_fields


@pytest.mark.parametrize("field,value", [
    ("entity_scheme", "https://example.invalid/entity"),
    ("entity_value", "0000000000"),
])
def test_serialized_entity_mutation_matches_direct_validator_conflict(artifact, field, value):
    future, _, _ = run(artifact)
    changed = deepcopy(future)
    q1 = next(row for row in changed["roles"]
        if row["ticker"] == "AAPL" and row["role"] == "Q1")
    q1["partition_replay_evidence"]["context"][field] = value
    replayed = replay_certification_artifact_partitions(changed)["partitions"][0]

    reviewed = load_reviewed_manifest(artifact)
    direct = {role.expected_role: qualify_inline_revenue_operand(role, body(role).encode()).operand
        for role in reviewed.roles if role.ticker == "AAPL"}
    operand = direct["Q1"]
    direct["Q1"] = operand.model_copy(update={"context": operand.context.model_copy(
        update={field: value})})
    expected = validate_revenue_operand_partition(annual=direct["FY"], q1=direct["Q1"],
        q2=direct["Q2"], q3=direct["Q3"])
    assert replayed["partition_result"]["state"] == expected.state == "conflict"
    assert replayed["partition_result"]["reasons"] == list(expected.reasons)


def test_historical_phase5w6_artifact_remains_incomplete_and_unmodified():
    raw = open(HISTORICAL_CERTIFICATION_PATH, encoding="utf-8").read()
    historical = json.loads(raw)
    assert historical["schema_version"] == "1"
    replay = replay_certification_artifact_partitions(historical)
    assert all(row["state"] == "replay_unavailable" for row in replay["partitions"])
    assert all(row["reason"] == "incomplete_replay_evidence" for row in replay["partitions"])
    assert open(HISTORICAL_CERTIFICATION_PATH, encoding="utf-8").read() == raw


def test_cross_version_equivalence_diagnostic_survives_complete_replay(artifact):
    future, _, _ = run(artifact)
    q1 = next(row for row in future["roles"]
        if row["ticker"] == "AAPL" and row["role"] == "Q1")
    q1["partition_replay_evidence"]["expanded_qname"]["namespace_uri"] = (
        "http://fasb.org/us-gaap/2024")
    replayed = replay_certification_artifact_partitions(future)["partitions"][0]
    diagnostic = replayed["partition_result"]["concept_identity"]
    assert diagnostic["state"] == "certified_cross_version_equivalence"
    assert len(diagnostic["original_qnames"]) == 4
    assert len(diagnostic["certified_records"]) == 1


def test_replay_path_has_no_transport_or_network_operation():
    source = inspect.getsource(replay_certification_artifact_partitions).lower()
    for forbidden in ("transport", "request(", "httpx", "requests", "source_url"):
        assert forbidden not in source


def test_offline_documents_cli_uses_fixture_and_writes_sanitized_artifact(
        artifact, tmp_path, monkeypatch, capsys):
    reviewed = load_reviewed_manifest(artifact)
    fixture_path = tmp_path / "documents.json"
    fixture_path.write_text(json.dumps({"responses": fixture(reviewed)}), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(artifact), encoding="utf-8")
    repository = tmp_path / "repository"
    output = repository / "docs" / "diagnostics" / "result.json"
    import app.cli.certify_inline_revenue_operands as cli
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", repository)
    assert cli_main(["documents", "--fixture", str(fixture_path), "--manifest", str(manifest_path),
        "--expected-fingerprint", EXPECTED_FINGERPRINT, "--ack-max-attempts", "8",
        "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["mode"] == "offline" and result["certification_complete"] is True
    assert capsys.readouterr().out.strip() == str(output)
