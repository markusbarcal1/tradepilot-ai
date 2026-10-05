"""Unregistered future runner for bounded DOM-topology certification."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re

from .q4_candidate_retrieval import BoundCandidate
from .q4_certification import MANIFEST, FixtureTransport, _document_url, _rows
from .q4_direct import PARSER_VERSION
from .q4_discovery_policy import DISCOVERY_POLICY_VERSION, discover_q4_earnings_8k
from .q4_dom_topology import DIAGNOSTIC_VERSION, diagnose_dom_topology
from .q4_primary_relationship import (RELATIONSHIP_POLICY_VERSION, BoundPrimaryDocument,
    resolve_primary_exhibit99_relationship)
from .q4_release_structure_runner import (AGGREGATE_LIMIT, CLASS_LIMITS, PER_ISSUER_LIMIT,
    PER_TARGET_LIMITS, ReleaseStructureBudget, ReleaseStructureCertificationRunner)
from .transport import ProviderUnavailable


RUNNER_VERSION = "direct-q4-dom-topology-certification-1"
ACKNOWLEDGMENT = "I ACKNOWLEDGE THE 10-ATTEMPT Q4 DOM-TOPOLOGY DIAGNOSTIC LIMIT"


class DomTopologyCertificationRunner(ReleaseStructureCertificationRunner):
    runner_version = RUNNER_VERSION
    diagnostic_version = DIAGNOSTIC_VERSION

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ledger = ReleaseStructureBudget()

    def _preflight(self):
        if not re.search(r"\S+@\S+\.\S+", self.user_agent or ""):
            raise ProviderUnavailable("sec_compliant_user_agent_required")
        if self.manifest != MANIFEST:
            raise ProviderUnavailable("dom_topology_manifest_mismatch")
        if (self.aggregate_budget != AGGREGATE_LIMIT
                or self.per_issuer_budget != PER_ISSUER_LIMIT
                or self.class_limits != CLASS_LIMITS):
            raise ProviderUnavailable("dom_topology_budget_mismatch")
        if self.http_attempts != 1:
            raise ProviderUnavailable("dom_topology_retries_enabled")
        if self.follow_redirects:
            raise ProviderUnavailable("dom_topology_redirects_enabled")
        if self.timeout != 5.0 or self.max_bytes != 1048576:
            raise ProviderUnavailable("dom_topology_transport_mismatch")

    @staticmethod
    def _empty(target, reason):
        return {"ticker": target.ticker, "fiscal_year": target.fiscal_year,
            "fiscal_quarter": "Q4",
            "discovery": {"boundary_state": "not_evaluated", "candidate_cardinality": 0,
                "binding_state": "not_attempted"},
            "primary": {"required": False, "attempted": False, "transport": None,
                "status": None, "received_bytes": None, "content_classification": None},
            "relationship": {"state": "not_evaluated", "reason": None,
                "observation_count": 0, "distinct_safe_destination_count": 0,
                "ambiguity_state": False},
            "exhibit": {"required": False, "attempted": False, "transport": None,
                "status": None, "received_bytes": None, "content_classification": None},
            "topology": None,
            "final": {"state": "unavailable", "reason": reason, "requests_consumed": 0}}

    def _target(self, target, rows):
        base = self._empty(target, "metadata_discovery_unavailable")
        discovery = discover_q4_earnings_8k(rows, period_end=target.period_end,
            approved_ten_k_accession=target.ten_k_accession)
        base["discovery"] = {"boundary_state": discovery.diagnostics["upper_boundary_status"],
            "candidate_cardinality": discovery.diagnostics["distinct_qualifying_candidates"],
            "binding_state": "not_attempted"}
        if discovery.state != "resolved" or len(discovery.candidates) != 1:
            base["final"]["reason"] = discovery.reason
            return base
        bound = self._bind(target, rows, discovery.candidates[0])
        if not isinstance(bound, BoundCandidate):
            base["discovery"]["binding_state"] = "failed"
            base["final"]["reason"] = "candidate_binding_failed"
            return base
        base["discovery"]["binding_state"] = "bound"
        before = self.ledger.aggregate
        primary_url = _document_url(target.cik, bound.accession, bound.primary_document)
        base["primary"].update(required=True, attempted=True)
        try:
            body = self._get(target, "selected_primary_document", primary_url)
        except Exception as exc:
            failure = self._failure(exc)
            base["primary"].update(transport=failure.category, status=failure.http_status,
                received_bytes=failure.received_bytes)
            base["final"].update(reason="primary_transport_failure",
                requests_consumed=self.ledger.aggregate-before)
            return base
        request = self.requests[-1]
        base["primary"].update(transport="success", status=request["http_status"],
            received_bytes=request["received_bytes"])
        content, classification = self._decode(body)
        base["primary"]["content_classification"] = classification
        if content is None:
            base["final"].update(reason="unsupported_primary_content",
                requests_consumed=self.ledger.aggregate-before)
            return base
        relationship = resolve_primary_exhibit99_relationship(BoundPrimaryDocument(
            ticker=target.ticker, issuer=target.issuer, cik=target.cik,
            accession=bound.accession, form=bound.form, fiscal_year=target.fiscal_year,
            period_end=target.period_end, filing_date=bound.filing_date,
            primary_url=primary_url, primary_document=bound.primary_document, html=content))
        base["relationship"] = {"state": relationship.state, "reason": relationship.reason,
            "observation_count": relationship.relationship_observations,
            "distinct_safe_destination_count": relationship.distinct_safe_destinations,
            "ambiguity_state": relationship.state == "ambiguous"}
        if relationship.state != "resolved" or relationship.destination is None:
            base["final"].update(reason=relationship.reason,
                requests_consumed=self.ledger.aggregate-before)
            return base
        base["exhibit"].update(required=True, attempted=True)
        try:
            exhibit_body = self._get(target, "earnings_exhibit", relationship.destination.url)
        except Exception as exc:
            failure = self._failure(exc)
            base["exhibit"].update(transport=failure.category, status=failure.http_status,
                received_bytes=failure.received_bytes)
            base["final"].update(reason="exhibit_transport_failure",
                requests_consumed=self.ledger.aggregate-before)
            return base
        request = self.requests[-1]
        base["exhibit"].update(transport="success", status=request["http_status"],
            received_bytes=request["received_bytes"])
        exhibit_content, classification = self._decode(exhibit_body)
        base["exhibit"]["content_classification"] = classification
        if exhibit_content is None:
            base["final"].update(reason="unsupported_exhibit_content",
                requests_consumed=self.ledger.aggregate-before)
            return base
        document = self._document(target, bound, relationship.destination.url,
            relationship.destination.document_id, exhibit_content)
        base["topology"] = diagnose_dom_topology(document)
        base["final"].update(state="observed", reason="dom_topology_diagnostic_completed",
            requests_consumed=self.ledger.aggregate-before)
        return base

    def run(self):
        self._preflight()
        targets = []
        for ticker in ("AAPL", "NVDA"):
            issuer_targets = [target for target in self.manifest if target.ticker == ticker]
            metadata_target = issuer_targets[0]
            url = f"https://data.sec.gov/submissions/CIK{metadata_target.cik}.json"
            try:
                rows = _rows(json.loads(self._get(metadata_target, "current_submissions", url)))
            except Exception:
                rows = None
            for target in issuer_targets:
                targets.append(self._target(target, rows) if rows is not None
                    else self._empty(target, "metadata_transport_failure"))
        return {"schema_version": "1", "diagnostic": DIAGNOSTIC_VERSION,
            "runner": RUNNER_VERSION, "relationship_policy": RELATIONSHIP_POLICY_VERSION,
            "discovery_policy": DISCOVERY_POLICY_VERSION, "observed_parser": PARSER_VERSION,
            "mode": "offline" if isinstance(self.transport, FixtureTransport) else "live",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "manifest": [{"ticker": target.ticker, "fiscal_year": target.fiscal_year,
                "fiscal_quarter": "Q4"} for target in self.manifest],
            "budget": {"maximum": AGGREGATE_LIMIT, "attempts": self.ledger.aggregate,
                "per_issuer_maximum": PER_ISSUER_LIMIT, "per_issuer": self.ledger.by_issuer,
                "class_limits": CLASS_LIMITS, "class_attempts": self.ledger.by_class,
                "per_target_document_limits": PER_TARGET_LIMITS}, "targets": targets}


def validate_live_gate(*, live, acknowledgment, user_agent):
    if not live: raise ProviderUnavailable("live_flag_required")
    if acknowledgment != ACKNOWLEDGMENT:
        raise ProviderUnavailable("exact_dom_topology_acknowledgment_required")
    if not re.search(r"\S+@\S+\.\S+", user_agent or ""):
        raise ProviderUnavailable("sec_compliant_user_agent_required")
