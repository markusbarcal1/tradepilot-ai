"""Offline-testable, two-attempt completion of the inline-revenue manifest."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit

from app.models.outlook_inline_revenue import SelectedFilingDocument
from .q4_certification import CertificationTransportError
from .transport import ProviderUnavailable


RUNNER_VERSION = "inline-revenue-manifest-metadata-completion-1"
SCHEMA_VERSION = "1"
MANIFEST_POLICY = "inline-revenue-certification-manifest-1"
TARGET_SET = "AAPL-FY2025-NVDA-FY2026-FY-Q1-Q2-Q3"
ACKNOWLEDGMENT = "I ACKNOWLEDGE THE 2-ATTEMPT INLINE-REVENUE METADATA LIMIT"
MAX_ATTEMPTS = 2
MAX_RESPONSE_BYTES = 1024 * 1024
ENDPOINTS = {
    "AAPL": "https://data.sec.gov/submissions/CIK0000320193.json",
    "NVDA": "https://data.sec.gov/submissions/CIK0001045810.json",
}


@dataclass(frozen=True)
class AnnualTarget:
    ticker: str
    issuer: str
    cik: str
    target_fiscal_year: int
    accession: str
    report_period_end: date
    primary_document: str
    source_url: str

    def selected(self, filing_date: date, acceptance_time=None):
        return SelectedFilingDocument(ticker=self.ticker, issuer=self.issuer, cik=self.cik,
            target_fiscal_year=self.target_fiscal_year, expected_role="FY",
            accession=self.accession, form="10-K", filing_date=filing_date,
            acceptance_time=acceptance_time, report_period_end=self.report_period_end,
            primary_document=self.primary_document, source_url=self.source_url,
            source_kind="inline_primary", selector_policy=RUNNER_VERSION)


ANNUAL_TARGETS = (
    AnnualTarget("AAPL", "Apple Inc.", "0000320193", 2025,
        "0000320193-25-000079", date(2025, 9, 27), "aapl-20250927.htm",
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"),
    AnnualTarget("NVDA", "NVIDIA Corporation", "0001045810", 2026,
        "0001045810-26-000021", date(2026, 1, 25), "nvda-20260125.htm",
        "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm"),
)


def _quarter(ticker, issuer, cik, fy, role, accession, filed, accepted, end, document):
    compact = accession.replace("-", "")
    return SelectedFilingDocument(ticker=ticker, issuer=issuer, cik=cik,
        target_fiscal_year=fy, expected_role=role, accession=accession, form="10-Q",
        filing_date=date.fromisoformat(filed),
        acceptance_time=datetime.fromisoformat(accepted.replace("Z", "+00:00")),
        report_period_end=date.fromisoformat(end), primary_document=document,
        source_url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{compact}/{document}",
        source_kind="inline_primary", selector_policy="phase6b5c2a5w1-preflight-1")


QUARTERLY_IDENTITIES = (
    _quarter("AAPL", "Apple Inc.", "0000320193", 2025, "Q1", "0000320193-25-000008",
        "2025-01-31", "2025-01-31T11:01:27Z", "2024-12-28", "aapl-20241228.htm"),
    _quarter("AAPL", "Apple Inc.", "0000320193", 2025, "Q2", "0000320193-25-000057",
        "2025-05-02", "2025-05-02T10:00:46Z", "2025-03-29", "aapl-20250329.htm"),
    _quarter("AAPL", "Apple Inc.", "0000320193", 2025, "Q3", "0000320193-25-000073",
        "2025-08-01", "2025-08-01T10:00:42Z", "2025-06-28", "aapl-20250628.htm"),
    _quarter("NVDA", "NVIDIA Corporation", "0001045810", 2026, "Q1", "0001045810-25-000116",
        "2025-05-28", "2025-05-28T20:32:57Z", "2025-04-27", "nvda-20250427.htm"),
    _quarter("NVDA", "NVIDIA Corporation", "0001045810", 2026, "Q2", "0001045810-25-000209",
        "2025-08-27", "2025-08-27T20:52:07Z", "2025-07-27", "nvda-20250727.htm"),
    _quarter("NVDA", "NVIDIA Corporation", "0001045810", 2026, "Q3", "0001045810-25-000230",
        "2025-11-19", "2025-11-19T21:36:17Z", "2025-10-26", "nvda-20251026.htm"),
)


@dataclass(frozen=True)
class CertificationManifest:
    schema_version: str
    manifest_policy: str
    target_set: str
    created_at: datetime
    roles: tuple[SelectedFilingDocument, ...]
    fingerprint: str

    def artifact(self):
        return {"schema_version": self.schema_version, "manifest_policy": self.manifest_policy,
            "target_set": self.target_set, "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "roles": [row.model_dump(mode="json") for row in self.roles],
            "fingerprint": self.fingerprint}


def _manifest(annual, created_at):
    rows = tuple(sorted((*annual, *QUARTERLY_IDENTITIES),
        key=lambda row: (row.ticker, {"FY": 0, "Q1": 1, "Q2": 2, "Q3": 3}[row.expected_role])))
    if len(rows) != 8 or [(row.ticker, row.expected_role) for row in rows] != [
            ("AAPL", "FY"), ("AAPL", "Q1"), ("AAPL", "Q2"), ("AAPL", "Q3"),
            ("NVDA", "FY"), ("NVDA", "Q1"), ("NVDA", "Q2"), ("NVDA", "Q3")]:
        raise ProviderUnavailable("manifest_integrity_failure")
    content = {"schema_version": SCHEMA_VERSION, "manifest_policy": MANIFEST_POLICY,
        "target_set": TARGET_SET, "roles": [row.model_dump(mode="json") for row in rows]}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return CertificationManifest(SCHEMA_VERSION, MANIFEST_POLICY, TARGET_SET, created_at,
        rows, hashlib.sha256(canonical.encode("utf-8")).hexdigest())


def validate_live_gate(*, live, acknowledgment, user_agent):
    if not live: raise ProviderUnavailable("metadata_request_not_authorized")
    if acknowledgment != ACKNOWLEDGMENT: raise ProviderUnavailable("metadata_request_not_authorized")
    if (not isinstance(user_agent, str) or "\n" in user_agent or "\r" in user_agent
            or not re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", user_agent)):
        raise ProviderUnavailable("sec_compliant_user_agent_required")


def _rows(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("filings"), dict):
        raise ProviderUnavailable("metadata_schema_invalid")
    recent = payload["filings"].get("recent")
    required = ("accessionNumber", "form", "reportDate", "filingDate", "primaryDocument")
    if not isinstance(recent, dict) or any(not isinstance(recent.get(name), list) for name in required):
        raise ProviderUnavailable("metadata_schema_invalid")
    lengths = {len(recent[name]) for name in required}
    if len(lengths) != 1 or next(iter(lengths), 0) > 4096:
        raise ProviderUnavailable("metadata_schema_invalid")
    acceptance = recent.get("acceptanceDateTime", [])
    if acceptance and (not isinstance(acceptance, list) or len(acceptance) != next(iter(lengths), 0)):
        raise ProviderUnavailable("metadata_schema_invalid")
    return tuple({"accession": recent["accessionNumber"][i], "form": recent["form"][i],
        "report_period": recent["reportDate"][i], "filing_date": recent["filingDate"][i],
        "primary_document": recent["primaryDocument"][i],
        "acceptance_time": acceptance[i] if acceptance else None}
        for i in range(next(iter(lengths), 0)))


def _complete(target, payload):
    rows = _rows(payload)
    accession_rows = [row for row in rows if row["accession"] == target.accession]
    if not accession_rows:
        return None, "missing_identity", "accession_mismatch", 0
    exact = [row for row in accession_rows if row["form"] == "10-K"
        and row["report_period"] == target.report_period_end.isoformat()
        and row["primary_document"] == target.primary_document]
    if not exact:
        reasons = []
        if all(row["form"] != "10-K" for row in accession_rows): reasons.append("form_mismatch")
        if all(row["report_period"] != target.report_period_end.isoformat() for row in accession_rows):
            reasons.append("report_period_mismatch")
        if all(row["primary_document"] != target.primary_document for row in accession_rows):
            reasons.append("primary_document_mismatch")
        return None, "conflict", reasons[0] if len(reasons) == 1 else "identity_conflict", 0
    if len(exact) > 1:
        return None, "ambiguous_identity", "ambiguous_identity", len(exact)
    row = exact[0]
    try: filing_date = date.fromisoformat(str(row["filing_date"]))
    except (TypeError, ValueError):
        return None, "missing_identity", "filing_date_missing", 1
    acceptance = None
    if row["acceptance_time"]:
        try:
            acceptance = datetime.fromisoformat(str(row["acceptance_time"]).replace("Z", "+00:00"))
            if acceptance.tzinfo is None: raise ValueError
        except (TypeError, ValueError):
            return None, "conflict", "identity_conflict", 1
    return target.selected(filing_date, acceptance), "completed", None, 1


class MetadataManifestCompletionRunner:
    """Two fixed metadata requests; never dispatches a filing-document URL."""
    def __init__(self, transport, *, user_agent, timeout=5, max_bytes=MAX_RESPONSE_BYTES,
            http_attempts=1, follow_redirects=False, clock=None):
        self.transport = transport; self.user_agent = user_agent; self.timeout = timeout
        self.max_bytes = max_bytes; self.http_attempts = http_attempts
        self.follow_redirects = follow_redirects
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.attempts = {"AAPL": 0, "NVDA": 0}; self.requests = []

    def _preflight(self):
        if self.http_attempts != 1: raise ProviderUnavailable("attempt_budget_exhausted")
        if self.follow_redirects: raise ProviderUnavailable("redirect_rejected")
        if self.timeout != 5 or not 1 <= self.max_bytes <= MAX_RESPONSE_BYTES:
            raise ProviderUnavailable("manifest_integrity_failure")

    def _get(self, ticker, url):
        if ENDPOINTS.get(ticker) != url:
            raise ProviderUnavailable("endpoint_not_allowed")
        if sum(self.attempts.values()) >= MAX_ATTEMPTS or self.attempts[ticker] >= 1:
            raise ProviderUnavailable("attempt_budget_exhausted")
        self.attempts[ticker] += 1  # charged before dispatch
        record = {"ticker": ticker, "endpoint": url, "ordinal_attempt": sum(self.attempts.values()),
            "transport_outcome": None, "http_status": None, "response_bytes": None}
        self.requests.append(record)
        try:
            response = self.transport.request(url, timeout=self.timeout,
                max_bytes=self.max_bytes, user_agent=self.user_agent)
            record["response_bytes"] = len(response.body); record["http_status"] = response.status
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
            record["transport_outcome"] = category
            record["http_status"] = exc.http_status
            record["response_bytes"] = exc.received_bytes
            raise ProviderUnavailable(category) from None

    def run(self):
        self._preflight(); outcomes = []; completed = []
        for target in ANNUAL_TARGETS:
            endpoint = ENDPOINTS[target.ticker]
            try:
                body = self._get(target.ticker, endpoint)
                try: payload = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise ProviderUnavailable("invalid_json") from None
                selected, state, reason, count = _complete(target, payload)
                if selected: completed.append(selected)
            except ProviderUnavailable as exc:
                selected, state, reason, count = None, "missing_identity", str(exc), 0
            outcomes.append({"ticker": target.ticker, "target_fiscal_year": target.target_fiscal_year,
                "role": "FY", "accession": target.accession, "form": "10-K",
                "report_period_end": target.report_period_end.isoformat(),
                "primary_document": target.primary_document, "source_url": target.source_url,
                "exact_match_count": count, "state": state, "failure_reason": reason,
                "filing_date": selected.filing_date.isoformat() if selected else None,
                "acceptance_time": (selected.acceptance_time.isoformat().replace("+00:00", "Z")
                    if selected and selected.acceptance_time else None)})
        manifest = None
        if len(completed) == 2:
            try: manifest = _manifest(tuple(completed), self.clock())
            except ProviderUnavailable: pass
        return {"schema_version": SCHEMA_VERSION, "runner": RUNNER_VERSION,
            "target_set": TARGET_SET, "mode": "offline" if self.transport.__class__.__name__ == "FixtureTransport" else "live",
            "budget": {"maximum": 2, "attempts_charged": sum(self.attempts.values()),
                "per_issuer_maximum": 1, "per_issuer": dict(self.attempts)},
            "requests": self.requests, "annual_results": outcomes,
            "manifest_ready": manifest is not None,
            "failure_reasons": [] if manifest else ["manifest_incomplete"],
            "manifest": manifest.artifact() if manifest else None}
