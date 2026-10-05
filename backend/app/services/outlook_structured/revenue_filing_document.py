"""Unregistered, bounded SEC filing-document retrieval with per-key single-flight."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import re
from threading import Event, RLock
from time import monotonic
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.models.outlook_revenue_filing_document import (
    RetrievedRevenueFilingDocument, RevenueFilingDocumentBatchResult,
    RevenueFilingDocumentRequestAccounting,
)
from app.models.outlook_revenue_filing_selection import RevenueFilingSelectionResult
from .transport import SEC_GATE


POLICY_VERSION = "revenue-filing-document-retrieval-1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_SUCCESS_TTL_SECONDS = 21_600
DEFAULT_FAILURE_TTL_SECONDS = 60
DEFAULT_CAPACITY = 128
_ROLES = ("FY", "Q1", "Q2", "Q3")
_ACCESSION = re.compile(r"^(\d{10})-\d{2}-\d{6}$")
_DOCUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")


class DocumentTransportError(RuntimeError):
    def __init__(self, reason, *, status=None, received_bytes=None):
        super().__init__(reason)
        self.reason, self.status, self.received_bytes = reason, status, received_bytes


@dataclass(frozen=True)
class DocumentTransportResponse:
    status: int
    final_url: str
    body: bytes
    content_type: str | None = None
    content_length: int | None = None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DocumentTransportError("redirect_rejected", status=code)


class BoundedSecDocumentTransport:
    """One-attempt raw transport. Rate gating and accounting are owned by the service."""
    def request(self, url, *, timeout, max_bytes, user_agent):
        request = Request(url, headers={"User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain"})
        try:
            with build_opener(_NoRedirect).open(request, timeout=timeout) as response:
                length = response.headers.get("Content-Length")
                parsed_length = int(length) if length and length.isdigit() else None
                if parsed_length is not None and parsed_length > max_bytes:
                    raise DocumentTransportError("response_size_rejected",
                        status=response.status, received_bytes=0)
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise DocumentTransportError("response_size_rejected",
                        status=response.status, received_bytes=len(body))
                return DocumentTransportResponse(response.status, response.geturl(), body,
                    response.headers.get_content_type(), parsed_length)
        except HTTPError as exc:
            if 300 <= exc.code < 400:
                raise DocumentTransportError("redirect_rejected", status=exc.code) from None
            raise DocumentTransportError(_http_reason(exc.code), status=exc.code) from None


@dataclass(frozen=True)
class _Cached:
    expires_at: float
    body: bytes | None
    content_type: str | None
    fingerprint: str | None
    reason: str | None


class RevenueFilingDocumentCache:
    def __init__(self, *, clock=monotonic, capacity=DEFAULT_CAPACITY):
        self.clock, self.capacity = clock, capacity
        self.entries = OrderedDict()
        self.flights = {}
        self.lock = RLock()

    def acquire(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if entry and entry.expires_at > self.clock():
                self.entries.move_to_end(key)
                return "cached", entry, None
            if entry:
                del self.entries[key]
            flight = self.flights.get(key)
            if flight is None:
                flight = Event(); self.flights[key] = flight
                return "leader", None, flight
            return "follower", None, flight

    def finish(self, key, entry):
        with self.lock:
            self.entries[key] = entry; self.entries.move_to_end(key)
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
            flight = self.flights.pop(key)
            flight.set()


def _http_reason(status):
    if status in (403, 404, 429): return f"http_{status}"
    if 500 <= status <= 599: return "http_5xx"
    return "http_error"


def _canonical(document):
    if not re.fullmatch(r"\d{10}", document.cik): raise ValueError
    match = _ACCESSION.fullmatch(document.accession)
    if not match or match.group(1) != document.cik or not _DOCUMENT.fullmatch(document.primary_document):
        raise ValueError
    return ("https://www.sec.gov/Archives/edgar/data/"
        f"{int(document.cik)}/{document.accession.replace('-', '')}/{document.primary_document}")


def _validate_selected(item, selection):
    url = _canonical(item.document)
    parts = urlsplit(item.document.source_url)
    if (item.role != item.document.expected_role
            or item.document.issuer != selection.issuer or item.document.cik != selection.cik
            or item.document.target_fiscal_year != selection.target_fiscal_year
            or item.document.selection_state != "selected" or item.document.source_url != url
            or parts.scheme != "https" or parts.hostname != "www.sec.gov"
            or parts.username or parts.password or parts.query or parts.fragment
            or "%" in parts.path or ".." in parts.path):
        raise ValueError
    return url


class RevenueFilingDocumentRetriever:
    def __init__(self, transport=None, *, user_agent,
            timeout=DEFAULT_TIMEOUT_SECONDS, max_bytes=MAX_RESPONSE_BYTES,
            success_ttl=DEFAULT_SUCCESS_TTL_SECONDS, failure_ttl=DEFAULT_FAILURE_TTL_SECONDS,
            request_interval=1, cache=None, rate_gate=SEC_GATE, clock=monotonic):
        self.transport = transport or BoundedSecDocumentTransport()
        self.user_agent, self.timeout, self.max_bytes = user_agent, timeout, max_bytes
        self.success_ttl, self.failure_ttl = success_ttl, failure_ttl
        self.request_interval, self.rate_gate, self.clock = request_interval, rate_gate, clock
        self.cache = cache or RevenueFilingDocumentCache(clock=clock)

    def _failure(self, selection, reason, accounting, *, conflict=False):
        return RevenueFilingDocumentBatchResult(policy_version=POLICY_VERSION,
            state="conflict" if conflict else "unavailable", issuer=selection.issuer,
            cik=selection.cik, target_fiscal_year=selection.target_fiscal_year,
            reason=reason, request_accounting=RevenueFilingDocumentRequestAccounting(**accounting))

    def retrieve(self, selection: RevenueFilingSelectionResult):
        base = dict(logical_documents_requested=0, cache_success_hits=0, cache_failure_hits=0,
            http_attempts_charged=0, successes=0, failures=0, bytes_accepted=0,
            failure_position=None, failure_role=None, failure_reason=None)
        if selection.state != "selected":
            return self._failure(selection, "input_not_selected", base, conflict=True)
        if tuple(row.role for row in selection.selected_filings) != _ROLES:
            return self._failure(selection, "role_set_invalid", base, conflict=True)
        validated = []
        try:
            for item in selection.selected_filings:
                validated.append((item, _validate_selected(item, selection)))
        except (TypeError, ValueError):
            return self._failure(selection, "url_policy_rejected", base, conflict=True)

        documents = []
        for position, (item, url) in enumerate(validated, 1):
            base["logical_documents_requested"] += 1
            key = (POLICY_VERSION, item.document.cik, item.document.accession,
                item.document.primary_document)
            mode, entry, flight = self.cache.acquire(key)
            if mode == "follower":
                flight.wait()
                mode, entry, _ = self.cache.acquire(key)
            if mode == "cached":
                if entry.reason:
                    base["cache_failure_hits"] += 1
                    return self._failed_at(selection, base, position, item.role, entry.reason)
                base["cache_success_hits"] += 1
                cache_state = "success_hit"
            else:
                base["http_attempts_charged"] += 1
                try:
                    self.rate_gate.wait(self.request_interval)
                    response = self.transport.request(url, timeout=self.timeout,
                        max_bytes=self.max_bytes, user_agent=self.user_agent)
                    entry = self._accept(url, response)
                except TimeoutError:
                    entry = self._failed_entry("timeout")
                except OSError:
                    entry = self._failed_entry("connection_failure")
                except DocumentTransportError as exc:
                    entry = self._failed_entry(exc.reason)
                except Exception:
                    entry = self._failed_entry("transport_failure")
                self.cache.finish(key, entry)
                if entry.reason:
                    return self._failed_at(selection, base, position, item.role, entry.reason)
                cache_state = "miss"
            base["successes"] += 1; base["bytes_accepted"] += len(entry.body)
            documents.append(RetrievedRevenueFilingDocument(role=item.role,
                selected_document=item.document, selection_provenance=item.metadata_provenance,
                canonical_url=url, body=entry.body, byte_length=len(entry.body),
                fingerprint=entry.fingerprint, content_type=entry.content_type,
                retrieval_policy=POLICY_VERSION, cache_state=cache_state))
        return RevenueFilingDocumentBatchResult(policy_version=POLICY_VERSION, state="available",
            issuer=selection.issuer, cik=selection.cik,
            target_fiscal_year=selection.target_fiscal_year, documents=tuple(documents),
            request_accounting=RevenueFilingDocumentRequestAccounting(**base))

    def _accept(self, url, response):
        if response.final_url != url: raise DocumentTransportError("redirect_rejected")
        if response.status != 200: raise DocumentTransportError(_http_reason(response.status))
        if response.content_length is not None and response.content_length > self.max_bytes:
            raise DocumentTransportError("response_size_rejected")
        if len(response.body) > self.max_bytes: raise DocumentTransportError("response_size_rejected")
        if not response.body: raise DocumentTransportError("empty_response")
        content_type = (response.content_type or "").split(";", 1)[0].strip().lower()
        if content_type not in _CONTENT_TYPES: raise DocumentTransportError("content_type_rejected")
        digest = hashlib.sha256(response.body).hexdigest()
        return _Cached(self.clock() + self.success_ttl, bytes(response.body), content_type, digest, None)

    def _failed_entry(self, reason):
        return _Cached(self.clock() + self.failure_ttl, None, None, None, reason)

    def _failed_at(self, selection, accounting, position, role, reason):
        accounting.update(failures=1, failure_position=position, failure_role=role,
            failure_reason=reason)
        return self._failure(selection, reason, accounting)
