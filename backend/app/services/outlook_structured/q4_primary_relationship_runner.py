"""Unregistered future certification runner for explicit primary relationships."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re

from .q4_candidate_retrieval import BoundCandidate, CandidateRetrievalRunner
from .q4_certification import MANIFEST, FixtureTransport, _document_url, _rows
from .q4_direct import PARSER_VERSION, qualify_direct_q4
from .q4_discovery_policy import DISCOVERY_POLICY_VERSION, discover_q4_earnings_8k
from .q4_primary_relationship import (RELATIONSHIP_POLICY_VERSION, BoundPrimaryDocument,
    resolve_primary_exhibit99_relationship)
from .transport import ProviderUnavailable


RUNNER_VERSION = "direct-q4-primary-relationship-certification-1"
ACKNOWLEDGMENT = "I ACKNOWLEDGE THE 10-ATTEMPT Q4 PRIMARY-RELATIONSHIP CERTIFICATION LIMIT"
AGGREGATE_LIMIT = 10
PER_ISSUER_LIMIT = 5
CLASS_LIMITS = {"current_submissions": 2, "selected_primary_document": 4,
    "earnings_exhibit": 4, "filing_index": 0}
PER_TARGET_LIMITS = {"selected_primary_document": 1, "earnings_exhibit": 1}


class PrimaryRelationshipBudget:
    def __init__(self):
        self.aggregate = 0
        self.by_issuer = {"AAPL": 0, "NVDA": 0}
        self.by_class = {key: 0 for key in CLASS_LIMITS}
        self.by_target = {}

    def charge(self, ticker, fiscal_year, request_class):
        target = (ticker, fiscal_year, request_class)
        if (request_class not in CLASS_LIMITS or self.aggregate >= AGGREGATE_LIMIT
                or self.by_issuer[ticker] >= PER_ISSUER_LIMIT
                or self.by_class[request_class] >= CLASS_LIMITS[request_class]
                or request_class in PER_TARGET_LIMITS
                and self.by_target.get(target, 0) >= PER_TARGET_LIMITS[request_class]):
            raise ProviderUnavailable("primary_relationship_budget_exceeded")
        self.aggregate += 1
        self.by_issuer[ticker] += 1
        self.by_class[request_class] += 1
        self.by_target[target] = self.by_target.get(target, 0) + 1


class PrimaryRelationshipCertificationRunner(CandidateRetrievalRunner):
    runner_version = RUNNER_VERSION
    relationship_policy_version = RELATIONSHIP_POLICY_VERSION
    discovery_policy_version = DISCOVERY_POLICY_VERSION
    parser_version = PARSER_VERSION

    def __init__(self, transport, *, user_agent, manifest=MANIFEST, aggregate_budget=10,
            per_issuer_budget=5, class_limits=CLASS_LIMITS, http_attempts=1,
            follow_redirects=False, timeout=5.0, max_bytes=1048576):
        super().__init__(transport, user_agent=user_agent, manifest=manifest,
            aggregate_budget=aggregate_budget, per_issuer_budget=per_issuer_budget,
            class_limits=class_limits, http_attempts=http_attempts,
            follow_redirects=follow_redirects, timeout=timeout, max_bytes=max_bytes)
        self.ledger = PrimaryRelationshipBudget()

    def _preflight(self):
        if not re.search(r"\S+@\S+\.\S+", self.user_agent or ""):
            raise ProviderUnavailable("sec_compliant_user_agent_required")
        if self.manifest != MANIFEST:
            raise ProviderUnavailable("primary_relationship_manifest_mismatch")
        if (self.aggregate_budget != AGGREGATE_LIMIT
                or self.per_issuer_budget != PER_ISSUER_LIMIT
                or self.class_limits != CLASS_LIMITS):
            raise ProviderUnavailable("primary_relationship_budget_mismatch")
        if self.http_attempts != 1:
            raise ProviderUnavailable("primary_relationship_retries_enabled")
        if self.follow_redirects:
            raise ProviderUnavailable("primary_relationship_redirects_enabled")

    @staticmethod
    def _empty(target, reason):
        return {"ticker": target.ticker, "fiscal_year": target.fiscal_year,
            "discovery": {"boundary_status": "not_evaluated", "candidate_cardinality": 0,
                "binding_status": "not_attempted"},
            "primary": {"required": False, "attempted": False, "transport_outcome": None,
                "http_status": None, "received_bytes": None, "content_classification": None},
            "relationship": {"adapter_invoked": False, "state": "not_evaluated",
                "reason": None, "relationship_observations": 0,
                "distinct_safe_destinations": 0, "duplicate_collapses": 0,
                "ambiguous": False},
            "exhibit": {"required": False, "attempted": False, "transport_outcome": None,
                "http_status": None, "received_bytes": None, "content_classification": None},
            "parser": CandidateRetrievalRunner._parser_diagnostics(None, invoked=False),
            "state": "unavailable", "reason": reason, "requests_consumed": 0}

    def _target(self, target, rows):
        base = self._empty(target, "metadata_discovery_unavailable")
        discovery = discover_q4_earnings_8k(rows, period_end=target.period_end,
            approved_ten_k_accession=target.ten_k_accession)
        base["discovery"] = {"boundary_status": discovery.diagnostics["upper_boundary_status"],
            "candidate_cardinality": discovery.diagnostics["distinct_qualifying_candidates"],
            "binding_status": "not_attempted"}
        if discovery.state != "resolved" or len(discovery.candidates) != 1:
            base["reason"] = discovery.reason
            return base
        bound = self._bind(target, rows, discovery.candidates[0])
        if not isinstance(bound, BoundCandidate):
            base["discovery"]["binding_status"] = "failed"
            base["reason"] = "candidate_binding_failed"
            return base
        base["discovery"]["binding_status"] = "bound"
        before = self.ledger.aggregate
        primary_url = _document_url(target.cik, bound.accession, bound.primary_document)
        base["primary"].update(required=True, attempted=True)
        try:
            body = self._get(target, "selected_primary_document", primary_url)
        except Exception as exc:
            failure = self._failure(exc)
            base["primary"].update(transport_outcome=failure.category,
                http_status=failure.http_status, received_bytes=failure.received_bytes)
            base.update(reason="primary_transport_failure",
                requests_consumed=self.ledger.aggregate-before)
            return base
        request = self.requests[-1]
        base["primary"].update(transport_outcome="success", http_status=request["http_status"],
            received_bytes=request["received_bytes"])
        content, classification = self._decode(body)
        base["primary"]["content_classification"] = classification
        if content is None:
            base.update(reason="unsupported_primary_content",
                requests_consumed=self.ledger.aggregate-before)
            return base
        relationship = resolve_primary_exhibit99_relationship(BoundPrimaryDocument(
            ticker=target.ticker, issuer=target.issuer, cik=target.cik,
            accession=bound.accession, form=bound.form, fiscal_year=target.fiscal_year,
            period_end=target.period_end, filing_date=bound.filing_date,
            primary_url=primary_url, primary_document=bound.primary_document, html=content))
        base["relationship"] = {"adapter_invoked": True, "state": relationship.state,
            "reason": relationship.reason,
            "relationship_observations": relationship.relationship_observations,
            "distinct_safe_destinations": relationship.distinct_safe_destinations,
            "duplicate_collapses": relationship.duplicate_collapses,
            "ambiguous": relationship.state == "ambiguous"}
        if relationship.state != "resolved" or relationship.destination is None:
            base.update(reason=relationship.reason, requests_consumed=self.ledger.aggregate-before)
            return base
        base["exhibit"].update(required=True, attempted=True)
        try:
            exhibit_body = self._get(target, "earnings_exhibit", relationship.destination.url)
        except Exception as exc:
            failure = self._failure(exc)
            base["exhibit"].update(transport_outcome=failure.category,
                http_status=failure.http_status, received_bytes=failure.received_bytes)
            base.update(reason="exhibit_transport_failure",
                requests_consumed=self.ledger.aggregate-before)
            return base
        request = self.requests[-1]
        base["exhibit"].update(transport_outcome="success", http_status=request["http_status"],
            received_bytes=request["received_bytes"])
        exhibit_content, classification = self._decode(exhibit_body)
        base["exhibit"]["content_classification"] = classification
        if exhibit_content is None:
            base.update(reason="unsupported_exhibit_content",
                requests_consumed=self.ledger.aggregate-before)
            return base
        document = self._document(target, bound, relationship.destination.url,
            relationship.destination.document_id, exhibit_content)
        result = qualify_direct_q4((document,))
        base["parser"] = self._parser_diagnostics(result, invoked=True,
            source_family="earnings_release_table")
        base.update(state=result.status,
            reason="exhibit_parser_qualified" if base["parser"]["accepted_observations_count"]
            else "parser_incompatible", requests_consumed=self.ledger.aggregate-before)
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
        return {"schema_version": "1", "runner": RUNNER_VERSION,
            "relationship_policy": RELATIONSHIP_POLICY_VERSION,
            "discovery_policy": DISCOVERY_POLICY_VERSION, "parser": PARSER_VERSION,
            "mode": "offline" if isinstance(self.transport, FixtureTransport) else "live",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "manifest": [{"ticker": target.ticker, "fiscal_year": target.fiscal_year,
                "fiscal_quarter": "Q4", "period_end": target.period_end}
                for target in self.manifest],
            "budget": {"maximum": AGGREGATE_LIMIT, "attempts": self.ledger.aggregate,
                "per_issuer_maximum": PER_ISSUER_LIMIT, "per_issuer": self.ledger.by_issuer,
                "class_limits": CLASS_LIMITS, "class_attempts": self.ledger.by_class,
                "per_target_document_limits": PER_TARGET_LIMITS},
            "requests": self.requests, "targets": targets}


def validate_live_gate(*, live, acknowledgment, user_agent):
    if not live:
        raise ProviderUnavailable("live_flag_required")
    if acknowledgment != ACKNOWLEDGMENT:
        raise ProviderUnavailable("exact_primary_relationship_acknowledgment_required")
    if not re.search(r"\S+@\S+\.\S+", user_agent or ""):
        raise ProviderUnavailable("sec_compliant_user_agent_required")
