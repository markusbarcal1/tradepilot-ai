"""Offline-qualified, unregistered candidate-retrieval certification runner."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import re
from urllib.parse import urlsplit

from app.models.outlook_q4 import DirectQ4Document
from .q4_certification import (CertificationTransportError, FixtureTransport, MANIFEST,
    _document_url, _exhibit_candidates, _rows, _validate_url)
from .q4_direct import PARSER_VERSION, qualify_direct_q4
from .q4_discovery_policy import DISCOVERY_POLICY_VERSION, discover_q4_earnings_8k
from .transport import ProviderUnavailable


RUNNER_VERSION = "direct-q4-candidate-retrieval-1"
RETRIEVAL_ACKNOWLEDGMENT = "I ACKNOWLEDGE THE 10-ATTEMPT Q4 CANDIDATE-RETRIEVAL LIMIT"
AGGREGATE_LIMIT = 10
CLASS_LIMITS = {"current_submissions": 2, "selected_primary_document": 4,
    "filing_index": 0, "earnings_exhibit": 4}
PER_ISSUER_LIMIT = 5
PER_TARGET_LIMITS = {"selected_primary_document": 1, "earnings_exhibit": 1}
SAFE_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SAFE_DOCUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


@dataclass(frozen=True)
class BoundCandidate:
    ticker: str
    fiscal_year: int
    cik: str
    accession: str
    form: str
    filing_date: str
    report_date: str
    items: str
    primary_document: str


class RetrievalBudget:
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
            raise ProviderUnavailable("candidate_retrieval_budget_exceeded")
        self.aggregate += 1
        self.by_issuer[ticker] += 1
        self.by_class[request_class] += 1
        self.by_target[target] = self.by_target.get(target, 0) + 1


class CandidateRetrievalRunner:
    """Rediscover, bind, and minimally retrieve candidates without production reachability."""
    runner_version = RUNNER_VERSION
    discovery_policy_version = DISCOVERY_POLICY_VERSION
    parser_version = PARSER_VERSION

    def __init__(self, transport, *, user_agent, manifest=MANIFEST, aggregate_budget=10,
            per_issuer_budget=5, class_limits=CLASS_LIMITS, http_attempts=1,
            follow_redirects=False, timeout=5.0, max_bytes=1048576):
        self.transport, self.user_agent, self.manifest = transport, user_agent, tuple(manifest)
        self.aggregate_budget, self.per_issuer_budget = aggregate_budget, per_issuer_budget
        self.class_limits = dict(class_limits)
        self.http_attempts, self.follow_redirects = http_attempts, follow_redirects
        self.timeout, self.max_bytes = timeout, max_bytes
        self.ledger, self.requests = RetrievalBudget(), []

    def _preflight(self):
        if not re.search(r"\S+@\S+\.\S+", self.user_agent or ""):
            raise ProviderUnavailable("sec_compliant_user_agent_required")
        if self.manifest != MANIFEST:
            raise ProviderUnavailable("retrieval_manifest_mismatch")
        if (self.aggregate_budget != AGGREGATE_LIMIT or self.per_issuer_budget != PER_ISSUER_LIMIT
                or self.class_limits != CLASS_LIMITS):
            raise ProviderUnavailable("retrieval_budget_mismatch")
        if self.http_attempts != 1:
            raise ProviderUnavailable("retrieval_retries_enabled")
        if self.follow_redirects:
            raise ProviderUnavailable("retrieval_redirects_enabled")

    @staticmethod
    def _failure(exc):
        if isinstance(exc, CertificationTransportError):
            return exc
        if isinstance(exc, TimeoutError):
            return CertificationTransportError("timeout")
        if isinstance(exc, OSError):
            return CertificationTransportError("connection_failure")
        return CertificationTransportError("transport_failure")

    def _get(self, target, request_class, url):
        try:
            requested_host = _validate_url(url)
        except ProviderUnavailable:
            raise CertificationTransportError("url_policy_rejected") from None
        self.ledger.charge(target.ticker, target.fiscal_year, request_class)
        ordinal = self.ledger.aggregate
        try:
            response = self.transport.request(url, timeout=self.timeout,
                max_bytes=self.max_bytes, user_agent=self.user_agent)
            try:
                final_host = _validate_url(response.final_url)
            except ProviderUnavailable:
                raise CertificationTransportError("redirect_rejected",
                    http_status=response.status, received_bytes=len(response.body)) from None
            if final_host != requested_host or response.final_url != url:
                raise CertificationTransportError("redirect_rejected",
                    http_status=response.status, received_bytes=len(response.body))
            if response.status != 200:
                raise CertificationTransportError("http_error", http_status=response.status,
                    received_bytes=len(response.body))
            if len(response.body) > self.max_bytes:
                raise CertificationTransportError("response_size_rejected",
                    http_status=response.status, received_bytes=len(response.body))
        except Exception as exc:
            failure = self._failure(exc)
            self.requests.append({"ticker": target.ticker, "fiscal_year": target.fiscal_year,
                "request_class": request_class, "ordinal_attempt": ordinal,
                "transport_outcome": failure.category, "http_status": failure.http_status,
                "received_bytes": failure.received_bytes})
            raise failure from None
        self.requests.append({"ticker": target.ticker, "fiscal_year": target.fiscal_year,
            "request_class": request_class, "ordinal_attempt": ordinal,
            "transport_outcome": "success", "http_status": response.status,
            "received_bytes": len(response.body)})
        return response.body

    @staticmethod
    def _bind(target, rows, candidate):
        identity = (candidate.get("accession"), candidate.get("form"),
            candidate.get("filing_date"), candidate.get("report_date"), candidate.get("items"),
            candidate.get("primary_document"))
        matches = [row for row in rows if (row.get("accession"), row.get("form"),
            row.get("filing_date"), str(row.get("report_date") or ""),
            str(row.get("items") or ""), row.get("primary_document")) == identity]
        if len(matches) != 1 or not SAFE_ACCESSION.fullmatch(str(candidate.get("accession") or "")):
            return None
        if not SAFE_DOCUMENT.fullmatch(str(candidate.get("primary_document") or "")):
            return None
        return BoundCandidate(target.ticker, target.fiscal_year, target.cik, *identity)

    @staticmethod
    def _decode(body):
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return None, "unsupported_binary"
        return text, "html_like" if re.search(r"<html|<table|<div|<body", text, re.I) else "text_like"

    @staticmethod
    def _document(target, bound, url, document_id, content):
        return DirectQ4Document(ticker=target.ticker, issuer=target.issuer, cik=target.cik,
            fiscal_year=target.fiscal_year, accession=bound.accession, form=bound.form,
            document_url=url, document_id=document_id,
            filing_date=date.fromisoformat(bound.filing_date), source_family="earnings_release_table",
            content=content)

    @staticmethod
    def _parser_diagnostics(result, *, invoked, source_family=None):
        rejections = sorted(set(result.rejection_reasons)) if result else []
        observations = tuple(result.observations) if result else ()
        return {"parser_invoked": invoked, "source_family": source_family,
            "candidate_observations_count": len(result.candidates) if result else 0,
            "accepted_observations_count": sum(row.version_status == "current" for row in observations),
            "rejection_categories": rejections[:32],
            "rejection_categories_capped": len(rejections) > 32,
            "conflict_state": any(row.version_status == "conflict" for row in observations),
            "revenue_available": any(row.metric == "revenue" and row.version_status == "current" for row in observations),
            "diluted_eps_available": any(row.metric == "diluted_eps" and row.version_status == "current" for row in observations)}

    def _target(self, target, rows):
        base = {"ticker": target.ticker, "fiscal_year": target.fiscal_year,
            "discovery": {}, "retrieval": {"selected_primary_request_attempted": False,
                "transport_outcome": None, "http_status": None, "received_bytes": None,
                "content_classification": None, "primary_sufficient_for_parser": False},
            "exhibit": {"required": False, "filing_index_request_attempted": False,
                "eligible_references": 0, "ambiguous": False,
                "request_attempted": False, "transport_outcome": None,
                "http_status": None, "received_bytes": None},
            "parser": self._parser_diagnostics(None, invoked=False),
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
        if bound is None:
            base["discovery"]["binding_status"] = "failed"
            base["reason"] = "candidate_binding_failed"
            return base
        base["discovery"]["binding_status"] = "bound"
        primary_url = _document_url(target.cik, bound.accession, bound.primary_document)
        base["retrieval"]["selected_primary_request_attempted"] = True
        try:
            body = self._get(target, "selected_primary_document", primary_url)
        except CertificationTransportError as exc:
            base["retrieval"].update(transport_outcome=exc.category,
                http_status=exc.http_status, received_bytes=exc.received_bytes)
            base["reason"] = "primary_transport_failure"
            return base
        request = self.requests[-1]
        base["retrieval"].update(transport_outcome="success", http_status=request["http_status"],
            received_bytes=request["received_bytes"])
        content, classification = self._decode(body)
        base["retrieval"]["content_classification"] = classification
        if content is None:
            base["reason"] = "unsupported_primary_content"
            return base
        primary_result = qualify_direct_q4((self._document(target, bound, primary_url,
            bound.primary_document, content),))
        base["parser"] = self._parser_diagnostics(primary_result, invoked=True,
            source_family="earnings_release_table")
        if base["parser"]["accepted_observations_count"]:
            base["retrieval"]["primary_sufficient_for_parser"] = True
            base.update(status=primary_result.status, reason="primary_parser_qualified")
            return base
        base["exhibit"]["required"] = True
        exhibits = _exhibit_candidates(content, primary_url)
        base["exhibit"]["eligible_references"] = min(len(exhibits), 32)
        if len(exhibits) > 1:
            base["exhibit"]["ambiguous"] = True
            base["reason"] = "earnings_exhibit_ambiguous"
            return base
        if not exhibits:
            base["reason"] = "parser_incompatible_no_eligible_exhibit"
            return base
        exhibit_url = exhibits[0]
        if urlsplit(exhibit_url).path.rsplit("/", 1)[0] != urlsplit(primary_url).path.rsplit("/", 1)[0]:
            base["reason"] = "exhibit_relationship_invalid"
            return base
        base["exhibit"]["request_attempted"] = True
        try:
            exhibit_body = self._get(target, "earnings_exhibit", exhibit_url)
        except CertificationTransportError as exc:
            base["exhibit"].update(transport_outcome=exc.category,
                http_status=exc.http_status, received_bytes=exc.received_bytes)
            base["reason"] = "exhibit_transport_failure"
            return base
        request = self.requests[-1]
        base["exhibit"].update(transport_outcome="success", http_status=request["http_status"],
            received_bytes=request["received_bytes"])
        exhibit_content, classification = self._decode(exhibit_body)
        if exhibit_content is None:
            base["reason"] = "unsupported_exhibit_content"
            return base
        document_id = urlsplit(exhibit_url).path.rsplit("/", 1)[-1]
        exhibit_result = qualify_direct_q4((self._document(target, bound, exhibit_url,
            document_id, exhibit_content),))
        base["parser"] = self._parser_diagnostics(exhibit_result, invoked=True,
            source_family="earnings_release_table")
        base.update(status=exhibit_result.status,
            reason="exhibit_parser_qualified" if base["parser"]["accepted_observations_count"]
            else "parser_incompatible")
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
            except (CertificationTransportError, json.JSONDecodeError):
                rows = None
            for target in issuer_targets:
                targets.append(self._target(target, rows) if rows is not None else {
                    "ticker": target.ticker, "fiscal_year": target.fiscal_year,
                    "status": "unavailable", "reason": "metadata_transport_failure",
                    "discovery": {"boundary_status": "not_evaluated", "candidate_cardinality": 0,
                        "binding_status": "not_attempted"}, "retrieval": None, "exhibit": None,
                    "parser": self._parser_diagnostics(None, invoked=False)})
        return {"schema_version": "1", "runner": self.runner_version,
            "discovery_policy": self.discovery_policy_version, "parser": self.parser_version,
            "mode": "offline" if isinstance(self.transport, FixtureTransport) else "live",
            "budget": {"maximum": AGGREGATE_LIMIT, "attempts": self.ledger.aggregate,
                "per_issuer_maximum": PER_ISSUER_LIMIT, "per_issuer": self.ledger.by_issuer,
                "class_limits": CLASS_LIMITS, "class_attempts": self.ledger.by_class,
                "per_target_document_limits": PER_TARGET_LIMITS},
            "requests": self.requests, "targets": targets}


def validate_retrieval_live_gate(*, live, acknowledgment, user_agent):
    if not live:
        raise ProviderUnavailable("live_flag_required")
    if acknowledgment != RETRIEVAL_ACKNOWLEDGMENT:
        raise ProviderUnavailable("exact_retrieval_acknowledgment_required")
    if not re.search(r"\S+@\S+\.\S+", user_agent or ""):
        raise ProviderUnavailable("sec_compliant_user_agent_required")
