"""Unregistered metadata-only SEC index-semantics diagnostic runner."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re

from .q4_candidate_retrieval import BoundCandidate, CandidateRetrievalRunner
from .q4_certification import MANIFEST, FixtureTransport, _rows
from .q4_discovery_policy import DISCOVERY_POLICY_VERSION, discover_q4_earnings_8k
from .q4_index_retrieval import _index_url
from .q4_index_semantics import DIAGNOSTIC_VERSION, inspect_index_semantics
from .transport import ProviderUnavailable


RUNNER_VERSION = "direct-q4-index-semantics-diagnostic-1"
ACKNOWLEDGMENT = "I ACKNOWLEDGE THE 6-ATTEMPT Q4 INDEX-SEMANTICS DIAGNOSTIC LIMIT"
AGGREGATE_LIMIT = 6
PER_ISSUER_LIMIT = 3
CLASS_LIMITS = {"current_submissions": 2, "filing_index": 4,
    "selected_primary_document": 0, "earnings_exhibit": 0, "filing_document": 0}
PER_TARGET_LIMITS = {"filing_index": 1}


class DiagnosticBudget:
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
            raise ProviderUnavailable("index_semantics_budget_exceeded")
        self.aggregate += 1
        self.by_issuer[ticker] += 1
        self.by_class[request_class] += 1
        self.by_target[target] = self.by_target.get(target, 0) + 1


class IndexSemanticsDiagnosticRunner(CandidateRetrievalRunner):
    runner_version = RUNNER_VERSION
    diagnostic_version = DIAGNOSTIC_VERSION
    discovery_policy_version = DISCOVERY_POLICY_VERSION

    def __init__(self, transport, *, user_agent, manifest=MANIFEST, aggregate_budget=6,
            per_issuer_budget=3, class_limits=CLASS_LIMITS, http_attempts=1,
            follow_redirects=False, timeout=5.0, max_bytes=1048576):
        super().__init__(transport, user_agent=user_agent, manifest=manifest,
            aggregate_budget=aggregate_budget, per_issuer_budget=per_issuer_budget,
            class_limits=class_limits, http_attempts=http_attempts,
            follow_redirects=follow_redirects, timeout=timeout, max_bytes=max_bytes)
        self.ledger = DiagnosticBudget()

    def _preflight(self):
        if not re.search(r"\S+@\S+\.\S+", self.user_agent or ""):
            raise ProviderUnavailable("sec_compliant_user_agent_required")
        if self.manifest != MANIFEST:
            raise ProviderUnavailable("index_semantics_manifest_mismatch")
        if (self.aggregate_budget != AGGREGATE_LIMIT
                or self.per_issuer_budget != PER_ISSUER_LIMIT
                or self.class_limits != CLASS_LIMITS):
            raise ProviderUnavailable("index_semantics_budget_mismatch")
        if self.http_attempts != 1:
            raise ProviderUnavailable("index_semantics_retries_enabled")
        if self.follow_redirects:
            raise ProviderUnavailable("index_semantics_redirects_enabled")

    @staticmethod
    def _empty(target, reason):
        return {"ticker": target.ticker, "fiscal_year": target.fiscal_year,
            "fiscal_quarter": "Q4",
            "discovery": {"boundary_status": "not_evaluated", "candidate_cardinality": 0,
                "binding_status": "not_attempted"},
            "index_transport": {"required": False, "attempted": False,
                "transport_outcome": None, "http_status": None, "received_bytes": None,
                "content_classification": None},
            "index_semantics": None, "state": "unavailable", "reason": reason,
            "requests_consumed": 0}

    def _target(self, target, rows):
        base = self._empty(target, "metadata_discovery_unavailable")
        discovery = discover_q4_earnings_8k(rows, period_end=target.period_end,
            approved_ten_k_accession=target.ten_k_accession)
        base["discovery"] = {
            "boundary_status": discovery.diagnostics["upper_boundary_status"],
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
        base["index_transport"].update(required=True, attempted=True)
        before = self.ledger.aggregate
        try:
            body = self._get(target, "filing_index", _index_url(target.cik, bound.accession))
        except Exception as exc:
            failure = self._failure(exc)
            base["index_transport"].update(transport_outcome=failure.category,
                http_status=failure.http_status, received_bytes=failure.received_bytes)
            base["reason"] = "index_transport_failure"
            base["requests_consumed"] = self.ledger.aggregate - before
            return base
        request = self.requests[-1]
        base["index_transport"].update(transport_outcome="success",
            http_status=request["http_status"], received_bytes=request["received_bytes"])
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            base["index_transport"]["content_classification"] = "unsupported"
            base["reason"] = "malformed_index_json"
            base["requests_consumed"] = self.ledger.aggregate - before
            return base
        base["index_transport"]["content_classification"] = "sec_index_json"
        base["index_semantics"] = inspect_index_semantics(payload)
        valid = base["index_semantics"]["structure"]["valid_list"]
        base.update(state="observed" if valid else "unavailable",
            reason="index_semantics_observed" if valid else "index_structure_unavailable",
            requests_consumed=self.ledger.aggregate - before)
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
            "diagnostic": DIAGNOSTIC_VERSION, "discovery_policy": DISCOVERY_POLICY_VERSION,
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
        raise ProviderUnavailable("exact_index_semantics_acknowledgment_required")
    if not re.search(r"\S+@\S+\.\S+", user_agent or ""):
        raise ProviderUnavailable("sec_compliant_user_agent_required")
