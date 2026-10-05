"""Offline-testable eight-document certification for the frozen revenue qualifier."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.models.outlook_inline_revenue import (
    PartitionReplayCompleteness, RevenueOperandReplayContext,
    RevenueOperandReplayEvidence, RevenueOperandReplayOperand,
    RevenueOperandReplayProvenance, RevenueOperandReplayUnit, SelectedFilingDocument,
)
from .inline_revenue_manifest_metadata import MANIFEST_POLICY, SCHEMA_VERSION as MANIFEST_SCHEMA, TARGET_SET
from .inline_revenue_operand import (
    POLICY_VERSION as QUALIFIER_VERSION, qualify_inline_revenue_operand,
    validate_revenue_operand_partition,
)
from .q4_certification import CertificationTransportError
from .transport import ProviderUnavailable


RUNNER_VERSION = "inline-revenue-eight-document-certification-2"
ARTIFACT_SCHEMA = "2"
EXPECTED_FINGERPRINT = "b272d3c69d169a5332e148839bec8ef37c2d4a234b81388db09eeb00efbce55b"
ACKNOWLEDGMENT = "I ACKNOWLEDGE THE 8-ATTEMPT INLINE-REVENUE DOCUMENT CERTIFICATION LIMIT"
MAX_ATTEMPTS = 8
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
EXPECTED_ORDER = (("AAPL", 2025, "FY"), ("AAPL", 2025, "Q1"),
    ("AAPL", 2025, "Q2"), ("AAPL", 2025, "Q3"),
    ("NVDA", 2026, "FY"), ("NVDA", 2026, "Q1"),
    ("NVDA", 2026, "Q2"), ("NVDA", 2026, "Q3"))


@dataclass(frozen=True)
class ReviewedManifest:
    stored_fingerprint: str
    recomputed_fingerprint: str
    roles: tuple[SelectedFilingDocument, ...]


def _canonical_content(manifest):
    return {"schema_version": manifest["schema_version"],
        "manifest_policy": manifest["manifest_policy"], "target_set": manifest["target_set"],
        "roles": manifest["roles"]}


def _fingerprint(manifest):
    canonical = json.dumps(_canonical_content(manifest), sort_keys=True,
        separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_reviewed_manifest(payload, *, expected_fingerprint=EXPECTED_FINGERPRINT):
    if not isinstance(payload, dict) or "manifest_ready" not in payload:
        raise ProviderUnavailable("manifest_missing")
    if payload.get("manifest_ready") is not True:
        raise ProviderUnavailable("manifest_not_ready")
    manifest = payload.get("manifest")
    if not isinstance(manifest, dict): raise ProviderUnavailable("manifest_missing")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ProviderUnavailable("manifest_schema_mismatch")
    if manifest.get("manifest_policy") != MANIFEST_POLICY:
        raise ProviderUnavailable("manifest_policy_mismatch")
    if manifest.get("target_set") != TARGET_SET:
        raise ProviderUnavailable("target_set_mismatch")
    role_rows = manifest.get("roles")
    if not isinstance(role_rows, list) or len(role_rows) != 8:
        raise ProviderUnavailable("manifest_role_count_mismatch")
    identity = tuple((row.get("ticker"), row.get("target_fiscal_year"), row.get("expected_role"))
        if isinstance(row, dict) else (None, None, None) for row in role_rows)
    if identity != EXPECTED_ORDER or len(set(identity)) != 8:
        raise ProviderUnavailable("manifest_role_identity_mismatch")
    stored = manifest.get("fingerprint")
    recomputed = _fingerprint(manifest)
    if not isinstance(stored, str) or stored != recomputed or recomputed != expected_fingerprint:
        raise ProviderUnavailable("manifest_fingerprint_mismatch")
    roles = []
    try:
        for raw in role_rows:
            role = SelectedFilingDocument.model_validate(raw)
            parts = urlsplit(role.source_url)
            expected_path = (f"/Archives/edgar/data/{int(role.cik)}/"
                f"{role.accession.replace('-', '')}/{role.primary_document}")
            if (parts.scheme != "https" or parts.hostname != "www.sec.gov" or parts.path != expected_path
                    or parts.query or parts.fragment or role.selection_state != "selected"):
                raise ProviderUnavailable("manifest_role_identity_mismatch")
            roles.append(role)
    except (ValidationError, ValueError, ProviderUnavailable):
        raise ProviderUnavailable("manifest_role_identity_mismatch") from None
    return ReviewedManifest(stored, recomputed, tuple(roles))


def validate_live_gate(*, live, acknowledgment, user_agent):
    if not live: raise ProviderUnavailable("acknowledgement_missing")
    if acknowledgment != ACKNOWLEDGMENT: raise ProviderUnavailable("acknowledgement_missing")
    if (not isinstance(user_agent, str) or "\n" in user_agent or "\r" in user_agent
            or not re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", user_agent)):
        raise ProviderUnavailable("sec_compliant_user_agent_required")


def _role_key(role):
    return f"{role.ticker}-FY{role.target_fiscal_year}-{role.expected_role}"


def _qualified_payload(operand):
    start, end = operand.context.period_start, operand.context.period_end
    return {"expanded_qname": operand.expanded_qname.model_dump(mode="json"),
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "duration_days": (end - start).days + 1,
        "unit": operand.unit.model_dump(mode="json"), "currency": operand.unit.currency,
        "dimension_state": {"explicit_count": len(operand.context.explicit_dimensions),
            "typed_count": operand.context.typed_dimension_count},
        "exact_decimal_value": str(operand.numeric.normalized_value),
        "accounting_basis": operand.accounting_basis, "scope": operand.reporting_scope,
        "provenance": {"policy_version": operand.policy_version,
            "selector_policy": operand.selector_policy, "fact_ordinal": operand.fact_ordinal,
            "node_ordinal": operand.node_ordinal, "occurrence_ordinals": list(operand.occurrence_ordinals),
            "context_id": operand.context_id, "unit_id": operand.unit_id,
            "dei_anchor": operand.dei_anchor.model_dump(mode="json")},
        "duplicate_count": operand.duplicate_count}


def serialize_revenue_operand_replay_evidence(operand):
    """Retain exactly the typed validator inputs plus already-retained provenance."""
    return RevenueOperandReplayEvidence(schema_version="1", role=operand.role,
        expanded_qname=operand.expanded_qname,
        canonical_unit=RevenueOperandReplayUnit(
            numerator_measures=operand.unit.numerator_measures,
            denominator_measures=operand.unit.denominator_measures,
            structural_form=operand.unit.structural_form, currency=operand.unit.currency),
        context=RevenueOperandReplayContext(
            entity_scheme=operand.context.entity_scheme,
            entity_value=operand.context.entity_value,
            period_start=operand.context.period_start,
            period_end=operand.context.period_end,
            explicit_dimensions=operand.context.explicit_dimensions,
            typed_dimension_count=operand.context.typed_dimension_count),
        accounting_basis=operand.accounting_basis,
        target_fiscal_year=operand.target_fiscal_year,
        reporting_scope=operand.reporting_scope,
        provenance=RevenueOperandReplayProvenance(
            policy_version=operand.policy_version,
            selector_policy=operand.selector_policy,
            fact_ordinal=operand.fact_ordinal, node_ordinal=operand.node_ordinal,
            occurrence_ordinals=operand.occurrence_ordinals,
            context_id=operand.context_id, unit_id=operand.unit_id,
            dei_anchor=operand.dei_anchor))


def assess_partition_replay_evidence(payload):
    try:
        evidence = RevenueOperandReplayEvidence.model_validate(payload)
    except ValidationError as exc:
        fields = []
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"])
            if field and field not in fields:
                fields.append(field[:128])
        return PartitionReplayCompleteness(state="incomplete",
            missing_fields=tuple(fields[:32])), None
    return PartitionReplayCompleteness(state="complete"), evidence


def reconstruct_revenue_operand(evidence):
    if not isinstance(evidence, RevenueOperandReplayEvidence):
        evidence = RevenueOperandReplayEvidence.model_validate(evidence)
    return RevenueOperandReplayOperand(role=evidence.role,
        expanded_qname=evidence.expanded_qname, unit=evidence.canonical_unit,
        context=evidence.context, accounting_basis=evidence.accounting_basis,
        target_fiscal_year=evidence.target_fiscal_year,
        reporting_scope=evidence.reporting_scope, provenance=evidence.provenance)


def replay_certification_artifact_partitions(artifact):
    """Replay only complete schema-2 evidence; never repair historical artifacts."""
    rows = artifact.get("roles", ()) if isinstance(artifact, dict) else ()
    partitions = []
    for ticker, fiscal_year in (("AAPL", 2025), ("NVDA", 2026)):
        evidence_by_role = {}
        missing = []
        for role in ("FY", "Q1", "Q2", "Q3"):
            row = next((item for item in rows if isinstance(item, dict)
                and item.get("ticker") == ticker
                and item.get("target_fiscal_year") == fiscal_year
                and item.get("role") == role), None)
            payload = row.get("partition_replay_evidence") if row else None
            completeness, evidence = assess_partition_replay_evidence(payload)
            if completeness.state != "complete":
                names = completeness.missing_fields or ("partition_replay_evidence",)
                missing.extend(f"{role}.{name}" for name in names)
            else:
                evidence_by_role[role] = reconstruct_revenue_operand(evidence)
        if missing:
            partitions.append({"ticker": ticker, "target_fiscal_year": fiscal_year,
                "state": "replay_unavailable", "reason": "incomplete_replay_evidence",
                "missing_fields": missing[:32], "partition_result": None})
            continue
        result = validate_revenue_operand_partition(annual=evidence_by_role["FY"],
            q1=evidence_by_role["Q1"], q2=evidence_by_role["Q2"],
            q3=evidence_by_role["Q3"])
        partitions.append({"ticker": ticker, "target_fiscal_year": fiscal_year,
            "state": "replayed", "reason": None, "missing_fields": [],
            "partition_result": result.model_dump(mode="json")})
    return {"replay_schema_version": "1", "source_artifact_schema": (
        artifact.get("schema_version") if isinstance(artifact, dict) else None),
        "partitions": partitions}


class EightDocumentCertificationRunner:
    def __init__(self, transport, manifest, *, user_agent, timeout=5,
            max_bytes=MAX_RESPONSE_BYTES, http_attempts=1, follow_redirects=False,
            qualifier=qualify_inline_revenue_operand,
            partition_validator=validate_revenue_operand_partition):
        self.transport = transport; self.manifest = manifest; self.user_agent = user_agent
        self.timeout = timeout; self.max_bytes = max_bytes; self.http_attempts = http_attempts
        self.follow_redirects = follow_redirects; self.qualifier = qualifier
        self.partition_validator = partition_validator
        self.attempts = {_role_key(role): 0 for role in manifest.roles}; self.requests = []

    def _preflight(self):
        if self.http_attempts != 1: raise ProviderUnavailable("attempt_budget_exhausted")
        if self.follow_redirects: raise ProviderUnavailable("redirect_rejected")
        if self.timeout != 5 or self.max_bytes != MAX_RESPONSE_BYTES:
            raise ProviderUnavailable("manifest_role_identity_mismatch")

    def _get(self, role, url):
        key = _role_key(role)
        if key not in self.attempts or url != role.source_url:
            raise ProviderUnavailable("url_not_allowed")
        if sum(self.attempts.values()) >= MAX_ATTEMPTS or self.attempts[key] >= 1:
            raise ProviderUnavailable("attempt_budget_exhausted")
        self.attempts[key] += 1
        record = {"role_key": key, "url": url, "attempt_charged": True,
            "ordinal_attempt": sum(self.attempts.values()), "transport_outcome": None,
            "http_status": None, "response_bytes": None}
        self.requests.append(record)
        try:
            response = self.transport.request(url, timeout=self.timeout,
                max_bytes=self.max_bytes, user_agent=self.user_agent)
            record["http_status"] = response.status; record["response_bytes"] = len(response.body)
            if response.final_url != url:
                record["transport_outcome"] = "redirect_rejected"
                raise ProviderUnavailable("redirect_rejected")
            if response.status != 200:
                record["transport_outcome"] = "http_error"
                raise ProviderUnavailable("http_error")
            record["transport_outcome"] = "success"
            return response.body
        except CertificationTransportError as exc:
            category = exc.category if exc.category in {"timeout", "redirect_rejected",
                "response_size_rejected", "http_error", "transport_failure", "connection_failure"} else "transport_failure"
            record["transport_outcome"] = category; record["http_status"] = exc.http_status
            record["response_bytes"] = exc.received_bytes
            raise ProviderUnavailable(category) from None

    def run(self):
        self._preflight(); results = []; operands = {}
        for role in self.manifest.roles:
            key = _role_key(role); qualifier_result = None; failure = None
            try:
                body = self._get(role, role.source_url)
                qualifier_result = self.qualifier(role, body)
            except ProviderUnavailable as exc:
                failure = str(exc)
            source_facts = tuple(qualifier_result.source_facts) if qualifier_result else ()
            compatible = sum(not row.rejection_reasons for row in source_facts)
            state = qualifier_result.state if qualifier_result else None
            if state and state != "qualified": failure = f"qualifier_{state}"
            replay_evidence = (serialize_revenue_operand_replay_evidence(qualifier_result.operand)
                if qualifier_result and qualifier_result.state == "qualified" else None)
            replay_completeness = PartitionReplayCompleteness(
                state="complete" if replay_evidence else "incomplete",
                missing_fields=() if replay_evidence else ("qualified_operand",))
            row = {"ticker": role.ticker, "target_fiscal_year": role.target_fiscal_year,
                "role": role.expected_role, "accession": role.accession, "form": role.form,
                "filing_date": role.filing_date.isoformat(),
                "report_period_end": role.report_period_end.isoformat(),
                "primary_document": role.primary_document, "source_url": role.source_url,
                "attempt_charged": self.attempts[key] == 1,
                "transport_outcome": next((request["transport_outcome"] for request in self.requests
                    if request["role_key"] == key), None),
                "http_status": next((request["http_status"] for request in self.requests
                    if request["role_key"] == key), None),
                "response_bytes": next((request["response_bytes"] for request in self.requests
                    if request["role_key"] == key), None),
                "qualifier_invoked": qualifier_result is not None,
                "qualifier_state": state,
                "qualifier_failure_reasons": list(qualifier_result.failure_reasons) if qualifier_result else [],
                "parser_cap_states": list(qualifier_result.cap_states) if qualifier_result else [],
                "fiscal_anchor_diagnostic": (qualifier_result.fiscal_anchor_diagnostic.model_dump(mode="json")
                    if qualifier_result and qualifier_result.fiscal_anchor_diagnostic else None),
                "supported_revenue_fact_count": len(source_facts),
                "compatible_candidate_count": compatible, "failure_reason": failure,
                "qualified_operand": (_qualified_payload(qualifier_result.operand)
                    if qualifier_result and qualifier_result.state == "qualified" else None),
                "partition_replay_evidence": (replay_evidence.model_dump(mode="json")
                    if replay_evidence else None),
                "partition_replay_completeness": replay_completeness.model_dump(mode="json")}
            if qualifier_result and qualifier_result.state == "qualified": operands[key] = qualifier_result.operand
            results.append(row)
        partitions = []
        for ticker, fy in (("AAPL", 2025), ("NVDA", 2026)):
            role_operands = {name.lower() if name != "FY" else "annual":
                operands.get(f"{ticker}-FY{fy}-{name}") for name in ("FY", "Q1", "Q2", "Q3")}
            if all(role_operands.values()):
                result = self.partition_validator(**role_operands)
                partitions.append({"ticker": ticker, "target_fiscal_year": fy,
                    "validator_invoked": True, "state": result.state, "reasons": list(result.reasons),
                    "partition_policy_version": result.partition_policy_version,
                    "concept_identity": (result.concept_identity.model_dump(mode="json")
                        if result.concept_identity else None),
                    "residual_period_start": result.residual_period_start.isoformat() if result.residual_period_start else None,
                    "residual_period_end": result.residual_period_end.isoformat() if result.residual_period_end else None,
                    "residual_duration_days": result.residual_duration_days})
            else:
                partitions.append({"ticker": ticker, "target_fiscal_year": fy,
                    "validator_invoked": False, "state": "unavailable",
                    "reasons": ["partition_unavailable"], "residual_period_start": None,
                    "residual_period_end": None, "residual_duration_days": None,
                    "partition_policy_version": None, "concept_identity": None})
        return {"schema_version": ARTIFACT_SCHEMA, "runner": RUNNER_VERSION,
            "qualifier": QUALIFIER_VERSION, "target_set": TARGET_SET,
            "reviewed_manifest_fingerprint": self.manifest.stored_fingerprint,
            "recomputed_manifest_fingerprint": self.manifest.recomputed_fingerprint,
            "mode": "offline" if self.transport.__class__.__name__ == "FixtureTransport" else "live",
            "budget": {"maximum": 8, "attempts_charged": sum(self.attempts.values()),
                "per_role_maximum": 1, "per_role": dict(self.attempts)},
            "requests": self.requests, "roles": results, "partitions": partitions,
            "certification_complete": all(row["qualified_operand"] is not None for row in results)
                and all(row["state"] == "valid" for row in partitions)}
