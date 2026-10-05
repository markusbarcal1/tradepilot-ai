"""Offline tests for exact revenue-only Q4 derivation."""
from copy import deepcopy
from decimal import Decimal
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.outlook_revenue_q4 import RevenueQ4DerivationInput, RevenueQ4Operand
from app.services.outlook_structured.revenue_q4_derivation import (
    derivation_input_from_certified_artifact, derive_revenue_q4,
)


ARTIFACT = Path(__file__).parents[2] / "docs/diagnostics/phase6b5c2a5w10a-schema2-live-revenue-partition-certification-20261002.json"


@pytest.fixture(scope="module")
def artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.mark.parametrize("ticker,year,expected,start,end,operands,accessions", [
    ("AAPL", 2025, Decimal("102466000000"), "2025-06-29", "2025-09-27",
     ("416161000000", "124300000000", "95359000000", "94036000000"),
     ("0000320193-25-000079", "0000320193-25-000008", "0000320193-25-000057", "0000320193-25-000073")),
    ("NVDA", 2026, Decimal("68127000000"), "2025-10-27", "2026-01-25",
     ("215938000000", "44062000000", "46743000000", "57006000000"),
     ("0001045810-26-000021", "0001045810-25-000116", "0001045810-25-000209", "0001045810-25-000230")),
])
def test_certified_artifact_derives_offline_with_full_provenance(
        artifact, ticker, year, expected, start, end, operands, accessions):
    inputs = derivation_input_from_certified_artifact(artifact, ticker=ticker, fiscal_year=year)
    result = derive_revenue_q4(inputs)
    assert result.state == "derived" and result.reasons == ()
    observation = result.observation
    assert observation.exact_decimal_value == expected
    assert (str(observation.period_start), str(observation.period_end), observation.duration_days) == (start, end, 91)
    assert tuple(str(row.exact_decimal_value) for row in observation.operand_provenance) == operands
    assert tuple(row.accession for row in observation.operand_provenance) == accessions
    assert tuple(row.original_qname for row in observation.operand_provenance) == observation.concept_identity.original_qnames
    assert observation.source_kind == "derived" and observation.derivation_policy == "revenue-q4-derivation-1"
    assert observation.concept_identity.state == "certified_cross_version_equivalence"
    assert observation.exact_decimal_value + sum((Decimal(value) for value in operands[1:]), Decimal(0)) == Decimal(operands[0])


def _input(artifact):
    return derivation_input_from_certified_artifact(artifact, ticker="AAPL", fiscal_year=2025)


@pytest.mark.parametrize("field,reason", [("annual", "missing_fy_operand"),
    ("q1", "missing_q1_operand"), ("q2", "missing_q2_operand"), ("q3", "missing_q3_operand")])
def test_missing_operand_is_unavailable_without_derivation(artifact, field, reason):
    inputs = _input(artifact).model_copy(update={field: None})
    result = derive_revenue_q4(inputs)
    assert result.state == "unavailable" and reason in result.reasons and result.observation is None


def test_invalid_partition_or_reasons_prevent_arithmetic(artifact):
    inputs = _input(artifact)
    bad = inputs.partition.model_copy(update={"state": "conflict", "reasons": ("synthetic",)})
    result = derive_revenue_q4(inputs.model_copy(update={"partition": bad}))
    assert result.state == "conflict" and result.observation is None
    suspicious = inputs.partition.model_copy(update={"reasons": ("synthetic",)})
    assert derive_revenue_q4(inputs.model_copy(update={"partition": suspicious})).state == "conflict"


@pytest.mark.parametrize("mutation,reason", [
    (lambda row: row.model_copy(update={"canonical_unit": row.canonical_unit.model_copy(
        update={"structural_form": "divide"})}), "unit_mismatch"),
    (lambda row: row.model_copy(update={"canonical_unit": row.canonical_unit.model_copy(
        update={"currency": "EUR"})}), "currency_mismatch"),
    (lambda row: row.model_copy(update={"context": row.context.model_copy(
        update={"entity_value": "other"})}), "entity_mismatch"),
    (lambda row: row.model_copy(update={"accounting_basis": "other"}), "accounting_basis_mismatch"),
    (lambda row: row.model_copy(update={"reporting_scope": "other"}), "reporting_scope_mismatch"),
    (lambda row: row.model_copy(update={"target_fiscal_year": 2024}), "fiscal_year_mismatch"),
    (lambda row: row.model_copy(update={"ticker": "OTHER"}), "issuer_mismatch"),
])
def test_non_concept_identity_mismatch_fails_closed(artifact, mutation, reason):
    inputs = _input(artifact)
    result = derive_revenue_q4(inputs.model_copy(update={"q1": mutation(inputs.q1)}))
    assert result.state == "conflict" and reason in result.reasons


def test_dimension_and_residual_geometry_mismatch_fail_closed(artifact):
    inputs = _input(artifact)
    dimension = (({"namespace_uri": "urn:test", "local_name": "Axis"},
        {"namespace_uri": "urn:test", "local_name": "Member"}),)
    context = inputs.q1.context.model_copy(update={"explicit_dimensions": dimension})
    assert derive_revenue_q4(inputs.model_copy(update={"q1": inputs.q1.model_copy(update={"context": context})})).state == "conflict"
    partition = inputs.partition.model_copy(update={"residual_duration_days": 90})
    assert "residual_period_invalid" in derive_revenue_q4(inputs.model_copy(update={"partition": partition})).reasons


def test_zero_is_valid_and_negative_fails_closed(artifact):
    inputs = _input(artifact)
    total = inputs.q1.exact_decimal_value + inputs.q2.exact_decimal_value + inputs.q3.exact_decimal_value
    zero = derive_revenue_q4(inputs.model_copy(update={"annual": inputs.annual.model_copy(
        update={"exact_decimal_value": total})}))
    assert zero.state == "derived" and zero.observation.exact_decimal_value == Decimal(0)
    negative = derive_revenue_q4(inputs.model_copy(update={"annual": inputs.annual.model_copy(
        update={"exact_decimal_value": total - 1})}))
    assert negative.state == "conflict" and negative.reasons == ("negative_derived_revenue",)


def test_float_is_rejected_and_decimal_exactness_is_preserved(artifact):
    payload = _input(artifact).annual.model_dump()
    payload["exact_decimal_value"] = 0.1
    with pytest.raises(ValidationError, match="binary floating point"):
        RevenueQ4Operand.model_validate(payload)
    inputs = _input(artifact)
    fractional = Decimal("416161000000.00000000000000000001")
    result = derive_revenue_q4(inputs.model_copy(update={"annual": inputs.annual.model_copy(
        update={"exact_decimal_value": fractional})}))
    assert result.observation.exact_decimal_value == Decimal("102466000000.00000000000000000001")


def test_incomplete_or_unqualified_artifact_is_unavailable(artifact):
    changed = deepcopy(artifact); changed["roles"][0]["partition_replay_completeness"]["state"] = "incomplete"
    assert derive_revenue_q4(_input(changed)).state == "unavailable"
    changed = deepcopy(artifact); changed["roles"][0]["qualifier_state"] = "conflict"
    assert derive_revenue_q4(_input(changed)).state == "unavailable"


def test_typed_unqualified_or_incomplete_operand_still_fails_closed(artifact):
    inputs = _input(artifact)
    unqualified = inputs.annual.model_copy(update={"qualifier_state": "conflict"})
    assert derive_revenue_q4(inputs.model_copy(update={"annual": unqualified})).reasons == ("operand_unqualified",)
    incomplete = inputs.annual.model_copy(update={"replay_state": "incomplete"})
    assert derive_revenue_q4(inputs.model_copy(update={"annual": incomplete})).reasons == ("incomplete_replay_evidence",)


def test_exact_same_qname_partition_derives(artifact):
    inputs = _input(artifact); qname = inputs.annual.expanded_qname
    operands = [row.model_copy(update={"expanded_qname": qname}) for row in
        (inputs.annual, inputs.q1, inputs.q2, inputs.q3)]
    concept = inputs.partition.concept_identity.model_copy(update={"state": "exact_qname",
        "original_qnames": (qname,) * 4, "certified_records": ()})
    partition = inputs.partition.model_copy(update={"concept_identity": concept})
    result = derive_revenue_q4(RevenueQ4DerivationInput(annual=operands[0], q1=operands[1],
        q2=operands[2], q3=operands[3], partition=partition))
    assert result.state == "derived" and result.observation.concept_identity.state == "exact_qname"


def test_no_network_eps_or_direct_q4_path_exists():
    import app.services.outlook_structured.revenue_q4_derivation as module
    source = inspect.getsource(module).lower()
    for forbidden in ("requests", "httpx", "transport", "earningspershare", "diluted", "q4_direct"):
        assert forbidden not in source
