"""Strictly bounded, offline-testable direct-Q4 SEC certification runner."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import re
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.models.outlook_q4 import DirectQ4Document
from .q4_direct import PARSER_VERSION, qualify_direct_q4
from .q4_discovery_policy import DISCOVERY_POLICY_VERSION, discover_q4_earnings_8k
from .transport import SEC_GATE, ProviderUnavailable


ACKNOWLEDGMENT = "I ACKNOWLEDGE THE 16-ATTEMPT LIMIT"
METADATA_ACKNOWLEDGMENT = "I ACKNOWLEDGE THE 2-ATTEMPT METADATA-ONLY LIMIT"
AGGREGATE_LIMIT = 16
PER_ISSUER_LIMIT = 8
CLASS_LIMITS = {
    "current_submissions": 1,
    "historical_submissions": 1,
    "ten_k_document": 2,
    "eight_k_index": 2,
    "earnings_exhibit": 2,
}
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SAFE_DOCUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
SAFE_HISTORY = re.compile(r"^CIK\d{10}-submissions-\d{3}\.json$")
OFFICIAL_HOSTS = {"www.sec.gov", "data.sec.gov"}
DISCOVERY_COUNT_LIMIT = 4096


@dataclass(frozen=True)
class CertificationTarget:
    ticker: str
    issuer: str
    cik: str
    fiscal_year: int
    period_end: str
    ten_k_accession: str


MANIFEST = (
    CertificationTarget("AAPL", "Apple Inc.", "0000320193", 2024, "2024-09-28", "0000320193-24-000123"),
    CertificationTarget("AAPL", "Apple Inc.", "0000320193", 2025, "2025-09-27", "0000320193-25-000079"),
    CertificationTarget("NVDA", "NVIDIA Corporation", "0001045810", 2025, "2025-01-26", "0001045810-25-000023"),
    CertificationTarget("NVDA", "NVIDIA Corporation", "0001045810", 2026, "2026-01-25", "0001045810-26-000021"),
)


@dataclass(frozen=True)
class TransportResponse:
    status: int
    final_url: str
    body: bytes


class CertificationTransport(Protocol):
    def request(self, url: str, *, timeout: float, max_bytes: int, user_agent: str) -> TransportResponse: ...


class CertificationTransportError(ProviderUnavailable):
    """Sanitized transport failure safe for bounded diagnostic artifacts."""
    def __init__(self, category, *, http_status=None, received_bytes=None):
        super().__init__(category)
        self.category = category
        self.http_status = http_status
        self.received_bytes = received_bytes


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class StrictSecTransport:
    """One HTTP transaction per call; redirects fail rather than hide attempts."""
    def __init__(self, interval: float = 1.0):
        self.interval = max(1.0, interval)
        self.opener = build_opener(_NoRedirect())

    def request(self, url, *, timeout, max_bytes, user_agent):
        SEC_GATE.wait(self.interval)
        request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json,text/html,text/plain"})
        try:
            with self.opener.open(request, timeout=timeout) as response:
                final_url = response.geturl()
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise CertificationTransportError("response_size_rejected",
                        http_status=response.status, received_bytes=len(body))
                return TransportResponse(response.status, final_url, body)
        except HTTPError as exc:
            if 300 <= exc.code < 400:
                raise CertificationTransportError("redirect_rejected", http_status=exc.code) from None
            raise CertificationTransportError("http_error", http_status=exc.code) from None
        except CertificationTransportError:
            raise
        except (TimeoutError,):
            raise CertificationTransportError("timeout") from None
        except URLError as exc:
            category = "timeout" if isinstance(exc.reason, TimeoutError) else "connection_failure"
            raise CertificationTransportError(category) from None
        except OSError:
            raise CertificationTransportError("connection_failure") from None
        except Exception:
            raise CertificationTransportError("transport_failure") from None


class FixtureTransport:
    """Injected deterministic responses; never performs network I/O."""
    def __init__(self, responses):
        self.responses = dict(responses)
        self.calls = []

    def request(self, url, *, timeout, max_bytes, user_agent):
        self.calls.append(url)
        row = self.responses.get(url)
        if row is None:
            raise CertificationTransportError("transport_failure")
        if row.get("raise"):
            category = str(row["raise"])
            allowed = {"timeout", "redirect_rejected", "response_size_rejected",
                "url_policy_rejected", "connection_failure", "transport_failure", "http_error"}
            raise CertificationTransportError(category if category in allowed else "transport_failure",
                http_status=row.get("http_status"), received_bytes=row.get("received_bytes"))
        body = row.get("body", "")
        if "json" in row:
            body = json.dumps(row["json"], sort_keys=True, separators=(",", ":"))
        data = body.encode("utf-8") if isinstance(body, str) else bytes(body)
        if len(data) > max_bytes:
            raise CertificationTransportError("response_size_rejected", received_bytes=len(data))
        return TransportResponse(int(row.get("status", 200)), row.get("final_url", url), data)


class BudgetLedger:
    def __init__(self):
        self.aggregate = 0
        self.issuer = {ticker: 0 for ticker in ("AAPL", "NVDA")}
        self.classes = {ticker: {name: 0 for name in CLASS_LIMITS} for ticker in self.issuer}

    def charge(self, ticker, request_class):
        if ticker not in self.issuer or request_class not in CLASS_LIMITS:
            raise ProviderUnavailable("request_outside_fixed_manifest")
        if self.aggregate >= AGGREGATE_LIMIT:
            raise ProviderUnavailable("aggregate_attempt_limit")
        if self.issuer[ticker] >= PER_ISSUER_LIMIT:
            raise ProviderUnavailable("issuer_attempt_limit")
        if self.classes[ticker][request_class] >= CLASS_LIMITS[request_class]:
            raise ProviderUnavailable("request_class_attempt_limit")
        self.aggregate += 1
        self.issuer[ticker] += 1
        self.classes[ticker][request_class] += 1
        return self.snapshot(ticker, request_class)

    def snapshot(self, ticker, request_class):
        return {
            "aggregate_remaining": AGGREGATE_LIMIT - self.aggregate,
            "issuer_remaining": PER_ISSUER_LIMIT - self.issuer[ticker],
            "class_remaining": CLASS_LIMITS[request_class] - self.classes[ticker][request_class],
        }


def _validate_url(url):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in OFFICIAL_HOSTS or parts.username or
            parts.password or parts.port is not None or parts.query or parts.fragment):
        raise ProviderUnavailable("invalid_sec_url")
    return parts.hostname


def _document_url(cik, accession, document):
    if not ACCESSION.fullmatch(accession) or not SAFE_DOCUMENT.fullmatch(document or ""):
        raise ProviderUnavailable("unsafe_document_identity")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}"


def _rows(payload):
    recent = payload.get("filings", {}).get("recent", payload) if isinstance(payload, dict) else {}
    accessions = recent.get("accessionNumber", []) if isinstance(recent, dict) else []
    result = []
    for index, accession in enumerate(accessions):
        def field(name):
            values = recent.get(name, [])
            return values[index] if isinstance(values, list) and index < len(values) else None
        result.append({"accession": accession, "form": field("form"), "report_date": field("reportDate"),
            "filing_date": field("filingDate"), "primary_document": field("primaryDocument"),
            "items": str(field("items") or "")})
    return result


def _history_name(payload, period_end):
    files = payload.get("filings", {}).get("files", []) if isinstance(payload, dict) else []
    matches = []
    for row in files if isinstance(files, list) else []:
        name, start, end = row.get("name"), row.get("filingFrom"), row.get("filingTo")
        if SAFE_HISTORY.fullmatch(str(name or "")) and str(start or "") <= period_end <= str(end or ""):
            matches.append(name)
    return matches[0] if len(matches) == 1 else None


def _discover_eight_k(rows, period_end):
    """Apply unchanged eligibility gates and return candidates plus bounded counts."""
    raw = {"metadata_rows_examined": len(rows), "rows_rejected_by_form": 0,
        "eight_k_rows_examined": 0, "rows_rejected_by_exact_report_date": 0,
        "rows_rejected_by_item_202": 0, "rows_rejected_by_primary_document": 0,
        "qualifying_candidates": 0, "ambiguous_qualifying_candidates": 0}
    eligible = []
    for row in rows:
        if row.get("form") not in ("8-K", "8-K/A"):
            raw["rows_rejected_by_form"] += 1
            continue
        raw["eight_k_rows_examined"] += 1
        if row.get("report_date") != period_end:
            raw["rows_rejected_by_exact_report_date"] += 1
            continue
        if not re.search(r"(?:^|,)\s*2\.02(?:\s|,|$)", row.get("items", "")):
            raw["rows_rejected_by_item_202"] += 1
            continue
        if not SAFE_DOCUMENT.fullmatch(str(row.get("primary_document") or "")):
            raw["rows_rejected_by_primary_document"] += 1
            continue
        eligible.append(row)
    raw["qualifying_candidates"] = len(eligible)
    raw["ambiguous_qualifying_candidates"] = len(eligible) if len(eligible) > 1 else 0
    diagnostics = {"count_semantics": "sequential_first_failure", "count_limit": DISCOVERY_COUNT_LIMIT,
        "counts_capped": any(value > DISCOVERY_COUNT_LIMIT for value in raw.values())}
    diagnostics.update({key: min(value, DISCOVERY_COUNT_LIMIT) for key, value in raw.items()})
    return tuple(eligible), diagnostics


def _exhibit_candidates(html, base_url):
    # An exhibit must be explicitly related to EX-99 and look like an earnings/results release.
    candidates = []
    for match in re.finditer(r"(?is)<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html):
        href = match.group(1).strip()
        if ".." in href.split("/") or urlsplit(href).query or urlsplit(href).fragment:
            continue
        nearby = re.sub(r"<[^>]+>", " ", html[max(0, match.start()-300):match.end()+300])
        if not re.search(r"\bEX-?99(?:\.\d+)?\b", nearby, re.I):
            continue
        if not re.search(r"earnings|financial results|press release|results", nearby, re.I):
            continue
        url = urljoin(base_url, href)
        parts = urlsplit(url)
        if parts.query or parts.fragment or not SAFE_DOCUMENT.fullmatch(parts.path.rsplit("/", 1)[-1]):
            continue
        try:
            _validate_url(url)
        except ProviderUnavailable:
            continue
        candidates.append(url)
    return tuple(dict.fromkeys(candidates))


class Q4CertificationRunner:
    def __init__(self, transport, *, user_agent, timeout=5.0, max_bytes=1048576, cache=None):
        self.transport, self.user_agent = transport, user_agent
        self.timeout, self.max_bytes = timeout, max_bytes
        self.cache = {} if cache is None else cache
        self.ledger = BudgetLedger()
        self.requests = []

    def _get(self, ticker, request_class, url):
        try:
            requested_host = _validate_url(url)
        except ProviderUnavailable:
            remaining = self.ledger.snapshot(ticker, request_class)
            self.requests.append({"ticker": ticker, "request_class": request_class,
                "ordinal_attempt": None, "requested_url": url, "validated_final_host": None,
                "cache": "miss", "transport_outcome": "url_policy_rejected",
                "http_status": None, "received_bytes": None, **remaining})
            raise CertificationTransportError("url_policy_rejected") from None
        if url in self.cache:
            response = self.cache[url]
            cache_hit = True
            ordinal = None
            remaining = self.ledger.snapshot(ticker, request_class)
        else:
            remaining = self.ledger.charge(ticker, request_class)  # charge before dispatch
            ordinal = self.ledger.aggregate
            cache_hit = False
            try:
                response = self.transport.request(url, timeout=self.timeout,
                    max_bytes=self.max_bytes, user_agent=self.user_agent)
            except CertificationTransportError as exc:
                self.requests.append({"ticker": ticker, "request_class": request_class,
                    "ordinal_attempt": ordinal, "requested_url": url, "validated_final_host": None,
                    "cache": "miss", "transport_outcome": exc.category,
                    "http_status": exc.http_status, "received_bytes": exc.received_bytes,
                    **remaining})
                raise
            except TimeoutError:
                failure = CertificationTransportError("timeout")
                self.requests.append({"ticker": ticker, "request_class": request_class,
                    "ordinal_attempt": ordinal, "requested_url": url, "validated_final_host": None,
                    "cache": "miss", "transport_outcome": failure.category,
                    "http_status": None, "received_bytes": None, **remaining})
                raise failure from None
            except OSError:
                failure = CertificationTransportError("connection_failure")
                self.requests.append({"ticker": ticker, "request_class": request_class,
                    "ordinal_attempt": ordinal, "requested_url": url, "validated_final_host": None,
                    "cache": "miss", "transport_outcome": failure.category,
                    "http_status": None, "received_bytes": None, **remaining})
                raise failure from None
            except Exception:
                failure = CertificationTransportError("transport_failure")
                self.requests.append({"ticker": ticker, "request_class": request_class,
                    "ordinal_attempt": ordinal, "requested_url": url, "validated_final_host": None,
                    "cache": "miss", "transport_outcome": failure.category,
                    "http_status": None, "received_bytes": None, **remaining})
                raise failure from None
            try:
                try:
                    final_host = _validate_url(response.final_url)
                except ProviderUnavailable:
                    raise CertificationTransportError("redirect_rejected",
                        http_status=response.status, received_bytes=len(response.body)) from None
                if final_host != requested_host:
                    raise CertificationTransportError("redirect_rejected",
                        http_status=response.status, received_bytes=len(response.body))
                if response.status != 200:
                    raise CertificationTransportError("http_error",
                        http_status=response.status, received_bytes=len(response.body))
                if len(response.body) > self.max_bytes:
                    raise CertificationTransportError("response_size_rejected",
                        http_status=response.status, received_bytes=len(response.body))
            except ProviderUnavailable as exc:
                failure = exc if isinstance(exc, CertificationTransportError) else CertificationTransportError("url_policy_rejected")
                self.requests.append({"ticker": ticker, "request_class": request_class,
                    "ordinal_attempt": ordinal, "requested_url": url, "validated_final_host": None,
                    "cache": "miss", "transport_outcome": failure.category,
                    "http_status": failure.http_status, "received_bytes": failure.received_bytes,
                    **remaining})
                raise failure from None
            self.cache[url] = response
        self.requests.append({"ticker": ticker, "request_class": request_class,
            "ordinal_attempt": ordinal, "requested_url": url,
            "validated_final_host": urlsplit(response.final_url).hostname,
            "cache": "hit" if cache_hit else "miss", "transport_outcome": "success",
            "http_status": response.status, "received_bytes": len(response.body), **remaining})
        return response.body.decode("utf-8", errors="replace")

    def _json(self, ticker, request_class, url):
        try:
            return json.loads(self._get(ticker, request_class, url))
        except (json.JSONDecodeError, UnicodeError):
            raise ProviderUnavailable("invalid_json") from None

    def run(self):
        outcomes, documents = [], []
        by_issuer = {ticker: [row for row in MANIFEST if row.ticker == ticker] for ticker in ("AAPL", "NVDA")}
        for ticker, targets in by_issuer.items():
            submissions_url = f"https://data.sec.gov/submissions/CIK{targets[0].cik}.json"
            try:
                submissions = self._json(ticker, "current_submissions", submissions_url)
            except ProviderUnavailable as exc:
                outcomes.extend(self._outcome(row, "request_failed", str(exc)) for row in targets)
                continue
            current_rows = _rows(submissions)
            history_rows = []
            unresolved_accessions = {row.ten_k_accession for row in targets} - {str(row.get("accession")) for row in current_rows}
            if unresolved_accessions:
                names = {_history_name(submissions, row.period_end) for row in targets if row.ten_k_accession in unresolved_accessions}
                names.discard(None)
                if len(names) == 1:
                    history_url = f"https://data.sec.gov/submissions/{next(iter(names))}"
                    try:
                        history_rows = _rows(self._json(ticker, "historical_submissions", history_url))
                    except ProviderUnavailable:
                        history_rows = []
            all_rows = current_rows + history_rows
            for target in targets:
                outcome, fetched = self._discover_target(target, all_rows)
                outcomes.append(outcome); documents.extend(fetched)
        result = qualify_direct_q4(documents)
        observations = [row.model_dump(mode="json") for row in result.observations]
        for outcome in outcomes:
            preexisting_reason = outcome["reason"]
            matching = [row for row in observations if row["ticker"] == outcome["ticker"] and row["fiscal_year"] == outcome["fiscal_year"]]
            target_candidates = [row for row in result.candidates if row.ticker == outcome["ticker"] and row.fiscal_year == outcome["fiscal_year"]]
            for family, branch_name in (("filing_xbrl", "ten_k"), ("earnings_release_table", "earnings_8k")):
                branch = outcome["branches"][branch_name]
                branch_observations = [row for row in matching if row["source_family"] == family]
                branch_candidates = [row for row in target_candidates if row.source_family == family]
                if branch["retrieval_status"] == "retrieved":
                    if any(row["version_status"] == "conflict" for row in branch_observations):
                        branch["parser_status"] = "conflict"
                    elif any(row["version_status"] == "current" for row in branch_observations):
                        branch["parser_status"] = "accepted"
                    elif branch_candidates:
                        branch["parser_status"] = "parser_incompatible"
                    else:
                        branch["parser_status"] = "metric_unavailable"
            if matching:
                outcome["status"] = "conflict" if any(row["version_status"] == "conflict" for row in matching) else "accepted"
                outcome["accepted_metrics"] = sorted({row["metric"] for row in matching if row["version_status"] == "current"})
            elif outcome["status"] == "request_failed" and all(
                    branch["discovery_status"] == "not_assessed" for branch in outcome["branches"].values()):
                pass
            elif any(branch["retrieval_status"] == "request_failed" for branch in outcome["branches"].values()):
                outcome["status"] = "request_failed"
            elif any(branch["parser_status"] == "parser_incompatible" for branch in outcome["branches"].values()):
                outcome["status"] = "parser_incompatible"
            elif any(branch["parser_status"] == "metric_unavailable" for branch in outcome["branches"].values()):
                outcome["status"] = "metric_unavailable"
            else:
                outcome["status"] = "source_unavailable"
            outcome["reasons"] = [branch["reason"] for branch in outcome["branches"].values() if branch["reason"]]
            if not outcome["reasons"] and preexisting_reason:
                outcome["reasons"] = [preexisting_reason]
            outcome["reason"] = "+".join(outcome["reasons"]) if outcome["reasons"] else None
        coverage = [{"ticker": row["ticker"], "fiscal_year": row["fiscal_year"],
            "fiscal_quarter": "Q4", "historical_before": "missing",
            "certification_status": row["status"], "accepted_metrics_after": row["accepted_metrics"]}
            for row in outcomes]
        return {"schema_version": "2", "runner": "direct-q4-certification-2",
            "parser_version": PARSER_VERSION, "mode": "offline" if isinstance(self.transport, FixtureTransport) else "live",
            "manifest": [row.__dict__ for row in MANIFEST], "budget": {"maximum": 16,
                "attempts": self.ledger.aggregate, "per_issuer": self.ledger.issuer,
                "per_class": self.ledger.classes}, "requests": self.requests,
            "outcomes": outcomes, "candidate_count": len(result.candidates),
            "rejection_count": sum(bool(row.rejection_reasons) for row in result.candidates),
            "observations": observations,
            "coverage_change": {"accepted_direct_q4": sum(row["version_status"] == "current" for row in observations),
                "targets": coverage}}

    def _discover_target(self, target, rows):
        outcome = self._outcome(target)
        fetched = []
        ten_branch, eight_branch = outcome["branches"]["ten_k"], outcome["branches"]["earnings_8k"]
        annual = [row for row in rows if row.get("accession") == target.ten_k_accession and row.get("form") in ("10-K", "10-K/A")]
        if len(annual) != 1 or not SAFE_DOCUMENT.fullmatch(str(annual[0].get("primary_document") or "")):
            ten_branch.update(discovery_status="unresolved", reason="approved_10k_document_unresolved")
        else:
            ten_k = annual[0]
            ten_branch.update(discovery_status="resolved", accession=target.ten_k_accession,
                document_id=ten_k["primary_document"])
            ten_k_url = _document_url(target.cik, target.ten_k_accession, ten_k["primary_document"])
            try:
                content = self._get(target.ticker, "ten_k_document", ten_k_url)
                ten_branch["retrieval_status"] = "retrieved"
                fetched.append(self._document(target, ten_k, ten_k_url, "filing_xbrl", content))
                outcome["documents"].append({"accession": target.ten_k_accession, "document_id": ten_k["primary_document"], "source_family": "filing_xbrl"})
            except ProviderUnavailable as exc:
                ten_branch.update(retrieval_status="request_failed", reason="ten_k_request_failed",
                    failure_category=str(exc))
        eight_ks, discovery_diagnostics = _discover_eight_k(rows, target.period_end)
        eight_branch["discovery_diagnostics"] = discovery_diagnostics
        if len(eight_ks) > 1:
            eight_branch.update(discovery_status="ambiguous", reason="multiple_plausible_earnings_8ks")
            return outcome, fetched
        if len(eight_ks) != 1 or not SAFE_DOCUMENT.fullmatch(str(eight_ks[0].get("primary_document") or "")):
            eight_branch.update(discovery_status="unresolved", reason="earnings_8k_unresolved")
            return outcome, fetched
        eight_k = eight_ks[0]
        if not ACCESSION.fullmatch(str(eight_k.get("accession") or "")):
            eight_branch.update(discovery_status="unresolved", reason="earnings_8k_accession_invalid")
            return outcome, fetched
        eight_branch.update(discovery_status="resolved", accession=eight_k["accession"],
            document_id=eight_k["primary_document"])
        index_url = _document_url(target.cik, eight_k["accession"], eight_k["primary_document"])
        try:
            index_content = self._get(target.ticker, "eight_k_index", index_url)
            eight_branch["retrieval_status"] = "primary_retrieved"
        except ProviderUnavailable as exc:
            eight_branch.update(retrieval_status="request_failed", reason="eight_k_request_failed",
                failure_category=str(exc))
            return outcome, fetched
        exhibits = _exhibit_candidates(index_content, index_url)
        expected_prefix = f"/Archives/edgar/data/{int(target.cik)}/{eight_k['accession'].replace('-', '')}/"
        exhibits = tuple(url for url in exhibits if urlsplit(url).path.startswith(expected_prefix))
        if len(exhibits) != 1:
            eight_branch.update(discovery_status="unresolved" if not exhibits else "ambiguous",
                reason="earnings_exhibit_unresolved" if not exhibits else "multiple_earnings_exhibits")
            return outcome, fetched
        exhibit_url = exhibits[0]
        try:
            content = self._get(target.ticker, "earnings_exhibit", exhibit_url)
            exhibit_row = dict(eight_k, primary_document=urlsplit(exhibit_url).path.rsplit("/", 1)[-1])
            fetched.append(self._document(target, exhibit_row, exhibit_url, "earnings_release_table", content))
            eight_branch.update(retrieval_status="retrieved", exhibit_document_id=exhibit_row["primary_document"])
            outcome["documents"].append({"accession": eight_k["accession"], "document_id": exhibit_row["primary_document"], "source_family": "earnings_release_table"})
        except ProviderUnavailable as exc:
            eight_branch.update(retrieval_status="request_failed", reason="earnings_exhibit_request_failed",
                failure_category=str(exc))
        return outcome, fetched

    @staticmethod
    def _document(target, row, url, family, content):
        try: filed = date.fromisoformat(str(row.get("filing_date")))
        except ValueError: filed = date.fromisoformat(target.period_end)
        return DirectQ4Document(ticker=target.ticker, issuer=target.issuer, cik=target.cik,
            fiscal_year=target.fiscal_year, accession=row["accession"], form=row["form"],
            document_url=url, document_id=urlsplit(url).path.rsplit("/", 1)[-1],
            filing_date=filed, source_family=family, content=content)

    @staticmethod
    def _outcome(target, status="source_unavailable", reason=None):
        branch = lambda: {"discovery_status": "not_assessed", "retrieval_status": "not_attempted",
            "parser_status": "not_run", "reason": None, "failure_category": None,
            "accession": None, "document_id": None, "exhibit_document_id": None,
            "discovery_diagnostics": None}
        return {"ticker": target.ticker, "cik": target.cik, "fiscal_year": target.fiscal_year,
            "fiscal_quarter": "Q4", "period_end": target.period_end,
            "approved_10k_accession": target.ten_k_accession, "status": status,
            "reason": reason, "reasons": [reason] if reason else [], "branches": {
                "ten_k": branch(), "earnings_8k": branch()}, "documents": [], "accepted_metrics": []}


def validate_live_gate(*, live, acknowledgment, user_agent):
    if not live:
        raise ProviderUnavailable("live_flag_required")
    if acknowledgment != ACKNOWLEDGMENT:
        raise ProviderUnavailable("exact_attempt_acknowledgment_required")
    if not re.search(r"\S+@\S+\.\S+", user_agent or ""):
        raise ProviderUnavailable("sec_compliant_user_agent_required")


class MetadataOnlyDiscoveryRunner:
    """Two-request submissions diagnostic with no document-retrieval path."""
    runner_version = "direct-q4-metadata-discovery-2"
    discovery_policy_version = DISCOVERY_POLICY_VERSION

    def __init__(self, transport, *, user_agent, manifest=MANIFEST, aggregate_budget=2,
            per_issuer_budget=1, enabled_request_classes=("current_submissions",),
            http_attempts=1, follow_redirects=False, timeout=5.0, max_bytes=1048576):
        self.transport, self.user_agent, self.manifest = transport, user_agent, tuple(manifest)
        self.aggregate_budget, self.per_issuer_budget = aggregate_budget, per_issuer_budget
        self.enabled_request_classes = tuple(enabled_request_classes)
        self.http_attempts, self.follow_redirects = http_attempts, follow_redirects
        self.timeout, self.max_bytes = timeout, max_bytes
        self.attempts = 0
        self.issuer_attempts = {"AAPL": 0, "NVDA": 0}
        self.requests = []

    def _preflight(self):
        if not re.search(r"\S+@\S+\.\S+", self.user_agent or ""):
            raise ProviderUnavailable("sec_compliant_user_agent_required")
        if self.manifest != MANIFEST:
            raise ProviderUnavailable("metadata_manifest_mismatch")
        if self.aggregate_budget != 2 or self.per_issuer_budget != 1:
            raise ProviderUnavailable("metadata_budget_mismatch")
        if self.enabled_request_classes != ("current_submissions",):
            raise ProviderUnavailable("metadata_request_class_mismatch")
        if self.http_attempts != 1:
            raise ProviderUnavailable("metadata_retries_enabled")
        if self.follow_redirects:
            raise ProviderUnavailable("metadata_redirects_enabled")

    @staticmethod
    def _category(exc):
        if isinstance(exc, CertificationTransportError):
            return exc
        if isinstance(exc, TimeoutError):
            return CertificationTransportError("timeout")
        if isinstance(exc, OSError):
            return CertificationTransportError("connection_failure")
        return CertificationTransportError("transport_failure")

    def _submissions(self, ticker, cik):
        if self.attempts >= self.aggregate_budget or self.issuer_attempts[ticker] >= self.per_issuer_budget:
            raise ProviderUnavailable("metadata_attempt_budget_exceeded")
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        _validate_url(url)
        self.attempts += 1  # charge before dispatch
        self.issuer_attempts[ticker] += 1
        ordinal = self.attempts
        remaining = {"aggregate_remaining": self.aggregate_budget - self.attempts,
            "issuer_remaining": self.per_issuer_budget - self.issuer_attempts[ticker]}
        try:
            response = self.transport.request(url, timeout=self.timeout,
                max_bytes=self.max_bytes, user_agent=self.user_agent)
            try:
                try:
                    final_host = _validate_url(response.final_url)
                except ProviderUnavailable:
                    raise CertificationTransportError("redirect_rejected",
                        http_status=response.status, received_bytes=len(response.body)) from None
                if final_host != "data.sec.gov":
                    raise CertificationTransportError("redirect_rejected",
                        http_status=response.status, received_bytes=len(response.body))
                if response.status != 200:
                    raise CertificationTransportError("http_error",
                        http_status=response.status, received_bytes=len(response.body))
                if len(response.body) > self.max_bytes:
                    raise CertificationTransportError("response_size_rejected",
                        http_status=response.status, received_bytes=len(response.body))
                payload = json.loads(response.body)
            except json.JSONDecodeError:
                raise CertificationTransportError("transport_failure",
                    http_status=response.status, received_bytes=len(response.body)) from None
            except ProviderUnavailable as exc:
                raise exc if isinstance(exc, CertificationTransportError) else CertificationTransportError("redirect_rejected")
        except Exception as exc:
            failure = self._category(exc)
            self.requests.append({"ticker": ticker, "request_class": "current_submissions",
                "ordinal_attempt": ordinal, "cache": "miss", "transport_outcome": failure.category,
                "http_status": failure.http_status, "received_bytes": failure.received_bytes, **remaining})
            raise failure from None
        self.requests.append({"ticker": ticker, "request_class": "current_submissions",
            "ordinal_attempt": ordinal, "cache": "miss", "transport_outcome": "success",
            "http_status": response.status, "received_bytes": len(response.body), **remaining})
        return payload

    def run(self):
        self._preflight()
        targets = []
        for ticker in ("AAPL", "NVDA"):
            issuer_targets = [target for target in self.manifest if target.ticker == ticker]
            try:
                rows = _rows(self._submissions(ticker, issuer_targets[0].cik))
                failure = None
            except ProviderUnavailable as exc:
                rows, failure = None, str(exc)
            for target in issuer_targets:
                if rows is None:
                    targets.append(self._target_result(target, "request_failed", failure, None))
                    continue
                discovery = discover_q4_earnings_8k(rows, period_end=target.period_end,
                    approved_ten_k_accession=target.ten_k_accession)
                state = {"resolved": "qualifying_candidate", "ambiguous": "ambiguous",
                    "unavailable": "source_unavailable"}[discovery.state]
                targets.append(self._target_result(target, state, discovery.reason,
                    discovery.diagnostics))
        return {"schema_version": "2", "runner": self.runner_version,
            "discovery_policy": self.discovery_policy_version,
            "mode": "offline" if isinstance(self.transport, FixtureTransport) else "live",
            "budget": {"maximum": 2, "attempts": self.attempts,
                "per_issuer_maximum": 1, "per_issuer": self.issuer_attempts,
                "enabled_request_classes": ["current_submissions"]},
            "requests": self.requests, "targets": targets}

    @staticmethod
    def _target_result(target, state, reason, diagnostics):
        return {"ticker": target.ticker, "cik": target.cik, "fiscal_year": target.fiscal_year,
            "fiscal_quarter": "Q4", "period_end": target.period_end,
            "discovery_state": state, "reason": reason,
            "discovery_diagnostics": diagnostics}


def validate_metadata_live_gate(*, live, acknowledgment, user_agent):
    if not live:
        raise ProviderUnavailable("live_flag_required")
    if acknowledgment != METADATA_ACKNOWLEDGMENT:
        raise ProviderUnavailable("exact_metadata_attempt_acknowledgment_required")
    if not re.search(r"\S+@\S+\.\S+", user_agent or ""):
        raise ProviderUnavailable("sec_compliant_user_agent_required")
