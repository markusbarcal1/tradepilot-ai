"""Unregistered index-enabled Q4 retrieval certification runner."""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from .q4_candidate_retrieval import (BoundCandidate, CandidateRetrievalRunner,
    RETRIEVAL_ACKNOWLEDGMENT as V1_ACKNOWLEDGMENT)
from .q4_certification import MANIFEST, FixtureTransport, _document_url, _exhibit_candidates, _rows
from .q4_direct import PARSER_VERSION, qualify_direct_q4
from .q4_discovery_policy import DISCOVERY_POLICY_VERSION, discover_q4_earnings_8k
from .q4_filing_index import INDEX_POLICY_VERSION, discover_index_earnings_exhibits
from .transport import ProviderUnavailable


RUNNER_VERSION = "direct-q4-candidate-retrieval-2"
INDEX_RETRIEVAL_ACKNOWLEDGMENT = "I ACKNOWLEDGE THE 14-ATTEMPT Q4 INDEX-ENABLED RETRIEVAL LIMIT"
AGGREGATE_LIMIT = 14
CLASS_LIMITS = {"current_submissions": 2, "selected_primary_document": 4,
    "filing_index": 4, "earnings_exhibit": 4}
PER_ISSUER_LIMIT = 7
PER_TARGET_LIMITS = {"selected_primary_document": 1, "filing_index": 1,
    "earnings_exhibit": 1}


class IndexRetrievalBudget:
    def __init__(self):
        self.aggregate = 0
        self.by_issuer = {"AAPL": 0, "NVDA": 0}
        self.by_class = {key: 0 for key in CLASS_LIMITS}
        self.by_target = {}

    def charge(self, ticker, fiscal_year, request_class):
        target = (ticker, fiscal_year, request_class)
        if (self.aggregate >= AGGREGATE_LIMIT or self.by_issuer[ticker] >= PER_ISSUER_LIMIT
                or self.by_class[request_class] >= CLASS_LIMITS[request_class]
                or request_class in PER_TARGET_LIMITS
                and self.by_target.get(target, 0) >= PER_TARGET_LIMITS[request_class]):
            raise ProviderUnavailable("index_retrieval_budget_exceeded")
        self.aggregate += 1
        self.by_issuer[ticker] += 1
        self.by_class[request_class] += 1
        self.by_target[target] = self.by_target.get(target, 0) + 1


def _index_url(cik, accession):
    if not re.fullmatch(r"\d{10}", str(cik or "")) or not re.fullmatch(
            r"\d{10}-\d{2}-\d{6}", str(accession or "")):
        raise ProviderUnavailable("unsafe_index_identity")
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession.replace('-', '')}/index.json")


class IndexEnabledCandidateRetrievalRunner(CandidateRetrievalRunner):
    runner_version = RUNNER_VERSION
    discovery_policy_version = DISCOVERY_POLICY_VERSION
    index_policy_version = INDEX_POLICY_VERSION
    parser_version = PARSER_VERSION

    def __init__(self, transport, *, user_agent, manifest=MANIFEST, aggregate_budget=14,
            per_issuer_budget=7, class_limits=CLASS_LIMITS, http_attempts=1,
            follow_redirects=False, timeout=5.0, max_bytes=1048576):
        super().__init__(transport, user_agent=user_agent, manifest=manifest,
            aggregate_budget=aggregate_budget, per_issuer_budget=per_issuer_budget,
            class_limits=class_limits, http_attempts=http_attempts,
            follow_redirects=follow_redirects, timeout=timeout, max_bytes=max_bytes)
        self.ledger = IndexRetrievalBudget()

    def _preflight(self):
        if not re.search(r"\S+@\S+\.\S+", self.user_agent or ""):
            raise ProviderUnavailable("sec_compliant_user_agent_required")
        if self.manifest != MANIFEST:
            raise ProviderUnavailable("index_retrieval_manifest_mismatch")
        if (self.aggregate_budget != AGGREGATE_LIMIT or self.per_issuer_budget != PER_ISSUER_LIMIT
                or self.class_limits != CLASS_LIMITS):
            raise ProviderUnavailable("index_retrieval_budget_mismatch")
        if self.http_attempts != 1:
            raise ProviderUnavailable("index_retrieval_retries_enabled")
        if self.follow_redirects:
            raise ProviderUnavailable("index_retrieval_redirects_enabled")

    @staticmethod
    def _empty_parser():
        return CandidateRetrievalRunner._parser_diagnostics(None, invoked=False)

    def _retrieve_exhibit(self, base, target, bound, exhibit_url):
        base["exhibit"]["request_attempted"] = True
        try:
            body = self._get(target, "earnings_exhibit", exhibit_url)
        except Exception as exc:
            failure = self._failure(exc)
            base["exhibit"].update(transport_outcome=failure.category,
                http_status=failure.http_status, received_bytes=failure.received_bytes)
            base.update(status="unavailable", reason="exhibit_transport_failure")
            return base
        request = self.requests[-1]
        base["exhibit"].update(transport_outcome="success", http_status=request["http_status"],
            received_bytes=request["received_bytes"])
        content, classification = self._decode(body)
        base["exhibit"]["content_classification"] = classification
        if content is None:
            base.update(status="unavailable", reason="unsupported_exhibit_content")
            return base
        document_id = urlsplit(exhibit_url).path.rsplit("/", 1)[-1]
        result = qualify_direct_q4((self._document(target, bound, exhibit_url, document_id, content),))
        base["exhibit"]["parser"] = self._parser_diagnostics(result, invoked=True,
            source_family="earnings_release_table")
        base.update(status=result.status,
            reason="exhibit_parser_qualified" if base["exhibit"]["parser"]["accepted_observations_count"]
            else "parser_incompatible")
        return base

    def _target(self, target, rows):
        base = {"ticker": target.ticker, "fiscal_year": target.fiscal_year,
            "discovery": {},
            "primary": {"request_attempted": False, "transport_outcome": None,
                "http_status": None, "received_bytes": None, "content_classification": None,
                "relationship_count": 0, "parser": self._empty_parser()},
            "index": {"required": False, "request_attempted": False,
                "transport_outcome": None, "http_status": None, "received_bytes": None,
                "content_classification": None, "diagnostics": None, "ambiguous": False},
            "exhibit": {"request_attempted": False, "transport_outcome": None,
                "http_status": None, "received_bytes": None, "content_classification": None,
                "parser": self._empty_parser()},
            "status": "unavailable", "reason": "metadata_discovery_unavailable"}
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
        primary_url = _document_url(target.cik, bound.accession, bound.primary_document)
        base["primary"]["request_attempted"] = True
        try:
            body = self._get(target, "selected_primary_document", primary_url)
        except Exception as exc:
            failure = self._failure(exc)
            base["primary"].update(transport_outcome=failure.category,
                http_status=failure.http_status, received_bytes=failure.received_bytes)
            base["reason"] = "primary_transport_failure"
            return base
        request = self.requests[-1]
        base["primary"].update(transport_outcome="success", http_status=request["http_status"],
            received_bytes=request["received_bytes"])
        content, classification = self._decode(body)
        base["primary"]["content_classification"] = classification
        if content is None:
            base["reason"] = "unsupported_primary_content"
            return base
        primary_result = qualify_direct_q4((self._document(target, bound, primary_url,
            bound.primary_document, content),))
        base["primary"]["parser"] = self._parser_diagnostics(primary_result, invoked=True,
            source_family="earnings_release_table")
        if base["primary"]["parser"]["accepted_observations_count"]:
            base.update(status=primary_result.status, reason="primary_parser_qualified")
            return base
        relationships = _exhibit_candidates(content, primary_url)
        base["primary"]["relationship_count"] = min(len(relationships), 32)
        if len(relationships) == 1:
            return self._retrieve_exhibit(base, target, bound, relationships[0])
        if len(relationships) > 1:
            base.update(status="ambiguous", reason="primary_exhibit_relationship_ambiguous")
            return base

        base["index"]["required"] = True
        index_url = _index_url(target.cik, bound.accession)
        base["index"]["request_attempted"] = True
        try:
            index_body = self._get(target, "filing_index", index_url)
        except Exception as exc:
            failure = self._failure(exc)
            base["index"].update(transport_outcome=failure.category,
                http_status=failure.http_status, received_bytes=failure.received_bytes)
            base["reason"] = "index_transport_failure"
            return base
        request = self.requests[-1]
        base["index"].update(transport_outcome="success", http_status=request["http_status"],
            received_bytes=request["received_bytes"])
        try:
            index_payload = json.loads(index_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            base["index"]["content_classification"] = "unsupported"
            base["reason"] = "unsupported_index_content"
            return base
        base["index"]["content_classification"] = "sec_index_json"
        index_result = discover_index_earnings_exhibits(index_payload)
        base["index"]["diagnostics"] = index_result.diagnostics
        base["index"]["ambiguous"] = index_result.state == "ambiguous"
        if index_result.state != "resolved":
            base.update(status="ambiguous" if index_result.state == "ambiguous" else "unavailable",
                reason=index_result.reason)
            return base
        exhibit_url = _document_url(target.cik, bound.accession, index_result.documents[0])
        return self._retrieve_exhibit(base, target, bound, exhibit_url)

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
                targets.append(self._target(target, rows) if rows is not None else {
                    "ticker": target.ticker, "fiscal_year": target.fiscal_year,
                    "status": "unavailable", "reason": "metadata_transport_failure",
                    "discovery": {"boundary_status": "not_evaluated", "candidate_cardinality": 0,
                        "binding_status": "not_attempted"}, "primary": None, "index": None,
                    "exhibit": None})
        return {"schema_version": "1", "runner": self.runner_version,
            "discovery_policy": self.discovery_policy_version,
            "index_policy": self.index_policy_version, "parser": self.parser_version,
            "mode": "offline" if isinstance(self.transport, FixtureTransport) else "live",
            "budget": {"maximum": AGGREGATE_LIMIT, "attempts": self.ledger.aggregate,
                "per_issuer_maximum": PER_ISSUER_LIMIT, "per_issuer": self.ledger.by_issuer,
                "class_limits": CLASS_LIMITS, "class_attempts": self.ledger.by_class,
                "per_target_document_limits": PER_TARGET_LIMITS},
            "requests": self.requests, "targets": targets}


def validate_index_retrieval_live_gate(*, live, acknowledgment, user_agent):
    if not live:
        raise ProviderUnavailable("live_flag_required")
    if acknowledgment == V1_ACKNOWLEDGMENT or acknowledgment != INDEX_RETRIEVAL_ACKNOWLEDGMENT:
        raise ProviderUnavailable("exact_index_retrieval_acknowledgment_required")
    if not re.search(r"\S+@\S+\.\S+", user_agent or ""):
        raise ProviderUnavailable("sec_compliant_user_agent_required")
