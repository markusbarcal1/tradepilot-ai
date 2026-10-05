"""Bounded SEC Company Facts normalization for internal historical research.

This service is deliberately disconnected from Outlook analysis and presentation.
"""
from collections import OrderedDict, defaultdict
from concurrent.futures import Future
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from threading import RLock

from app.models.outlook_financial_history import (
    HistoricalFinancialDiagnostics, HistoricalFinancialObservation,
    HistoricalFinancialSnapshot, MissingFinancialPeriod, RejectedFinancialFact,
)
from app.models.outlook_revenue_filing_selection import SecSubmissionFilingRow, SecSubmissionsSelectionInput
from app.models.outlook_revenue_history_snapshot import RevenueHistoricalAcquisition
from .sec import sec_symbol, ticker_mapping
from .transport import Cache, JsonClient, ProviderUnavailable

REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
DILUTED_EPS_CONCEPT = "EarningsPerShareDiluted"
BASIC_EPS_CONCEPT = "EarningsPerShareBasic"
SUPPORTED = {
    "revenue": (REVENUE_CONCEPTS, "USD", "not_applicable"),
    "diluted_eps": ((DILUTED_EPS_CONCEPT,), "USD/shares", "diluted"),
}
QUARTER_MIN_DAYS = 70
QUARTER_MAX_DAYS = 105
MAX_VERSIONS_PER_PERIOD = 4
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
ACQUISITION_POLICY = "revenue-historical-acquisition-1"


class _PerKeyCache:
    """Bounded success/failure cache whose load coordination is scoped per key."""
    def __init__(self, failure_ttl=60, clock=None, capacity=128):
        from time import monotonic
        self.failure_ttl, self.clock, self.capacity = failure_ttl, clock or monotonic, capacity
        self.entries, self.flights, self.lock = OrderedDict(), {}, RLock()

    def get(self, key, loader, ttl):
        with self.lock:
            entry = self.entries.get(key)
            if entry and entry[0] > self.clock():
                self.entries.move_to_end(key)
                if entry[2]: raise ProviderUnavailable("cached_provider_failure")
                return entry[1], "success_hit"
            if entry: del self.entries[key]
            future = self.flights.get(key); leader = future is None
            if leader: future = Future(); self.flights[key] = future
        if not leader:
            result = future.result()
            if result[1] == "failure": raise ProviderUnavailable("provider_request_failed")
            return result
        try:
            value = loader()
        except Exception:
            with self.lock:
                self.entries[key] = (self.clock() + self.failure_ttl, None, True)
                self._trim(); self.flights.pop(key).set_result((None, "failure"))
            raise ProviderUnavailable("provider_request_failed") from None
        result = (value, "miss")
        with self.lock:
            self.entries[key] = (self.clock() + ttl, value, False)
            self._trim(); self.flights.pop(key).set_result(result)
        return result

    def _trim(self):
        while len(self.entries) > self.capacity: self.entries.popitem(last=False)


def adapt_sec_submissions(payload, *, issuer, cik, source_identity):
    """Copy bounded recent submissions metadata without assigning fiscal roles."""
    if not isinstance(payload, dict) or not isinstance(payload.get("filings"), dict):
        raise ProviderUnavailable("submissions_schema_invalid")
    raw_cik = payload.get("cik")
    if raw_cik is not None and str(raw_cik).zfill(10) != cik:
        raise ProviderUnavailable("submissions_issuer_mismatch")
    raw_name = payload.get("name")
    if raw_name is not None and str(raw_name) != issuer:
        raise ProviderUnavailable("submissions_issuer_mismatch")
    recent = payload["filings"].get("recent")
    required = ("accessionNumber", "form", "filingDate", "reportDate", "primaryDocument")
    if not isinstance(recent, dict) or any(not isinstance(recent.get(name), list) for name in required):
        raise ProviderUnavailable("submissions_schema_invalid")
    lengths = {len(recent[name]) for name in required}
    if len(lengths) != 1 or next(iter(lengths), 0) > 4096:
        raise ProviderUnavailable("submissions_schema_invalid")
    count = next(iter(lengths), 0); acceptance = recent.get("acceptanceDateTime")
    if acceptance is not None and (not isinstance(acceptance, list) or len(acceptance) != count):
        raise ProviderUnavailable("submissions_schema_invalid")
    rows = tuple(SecSubmissionFilingRow(accession=recent["accessionNumber"][i] or None,
        form=recent["form"][i] or None, filing_date=_date(recent["filingDate"][i]),
        acceptance_time=_datetime(acceptance[i]) if acceptance else None,
        report_period_end=_date(recent["reportDate"][i]),
        primary_document=recent["primaryDocument"][i] or None, source_ordinal=i)
        for i in range(count))
    return SecSubmissionsSelectionInput(issuer=issuer, cik=cik,
        source_identity=source_identity, rows=rows)


def _acquisition_fingerprint(snapshot, submissions):
    observations = [row.model_dump(mode="json", exclude={"retrieved_at", "acceptance_time"})
        for row in snapshot.observations]
    rejected = [row.model_dump(mode="json") for row in snapshot.rejected]
    content = {"policy": ACQUISITION_POLICY, "ticker": snapshot.ticker,
        "issuer": snapshot.issuer, "cik": snapshot.cik, "observations": observations,
        "rejected": rejected, "missing_periods": [row.model_dump(mode="json") for row in snapshot.missing_periods],
        "submissions": submissions.model_dump(mode="json")}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canonical.encode()).hexdigest()


def _date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _datetime(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _decimal(value):
    if isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _quarter_index(year, quarter):
    return year * 4 + int(quarter[1]) - 1


def _period_from_index(index):
    return index // 4, f"Q{index % 4 + 1}"


def _submission_index(payload):
    recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload, dict) else {}
    rows = {}
    for index, accession in enumerate(recent.get("accessionNumber", [])):
        def field(name):
            values = recent.get(name, [])
            return values[index] if index < len(values) else None
        if ACCESSION.fullmatch(str(accession or "")):
            rows[accession] = {"form": field("form"), "filed": field("filingDate"),
                "accepted": field("acceptanceDateTime"), "primary_document": field("primaryDocument"),
                "report_date": field("reportDate")}
    return rows


def _source_url(cik, accession, primary_document=None):
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}"
    return f"{base}/{primary_document}" if primary_document else f"{base}/"


def comparison_compatibility(left, right, comparison):
    """Strict future comparison gate; returns eligibility plus explicit reasons."""
    reasons = []
    for field in ("metric", "original_concept", "currency", "original_unit",
                  "accounting_basis", "share_basis", "reporting_scope",
                  "duration_semantics"):
        if getattr(left, field) != getattr(right, field):
            reasons.append(f"incompatible_{field}")
    if not left.comparison_eligible or not right.comparison_eligible:
        reasons.append("inactive_or_conflicted_version")
    left_index = _quarter_index(left.fiscal_year, left.fiscal_quarter)
    right_index = _quarter_index(right.fiscal_year, right.fiscal_quarter)
    if comparison == "sequential":
        if right_index - left_index != 1:
            reasons.append("not_adjacent_fiscal_quarters")
    elif comparison == "year_over_year":
        if not (right.fiscal_year == left.fiscal_year + 1 and
                right.fiscal_quarter == left.fiscal_quarter):
            reasons.append("not_matching_prior_year_fiscal_quarter")
    else:
        reasons.append("unsupported_comparison_type")
    return not reasons, tuple(dict.fromkeys(reasons))


def normalize_companyfacts(companyfacts, submissions, ticker, retrieved_at, *,
                           max_source_facts=256, max_quarters=8,
                           max_annual_periods=5, request_diagnostics=None):
    """Normalize only explicit standalone quarterly revenue and diluted EPS facts."""
    symbol = str(ticker).strip().upper()
    cik = str(companyfacts.get("cik") or "").zfill(10)
    issuer = str(companyfacts.get("entityName") or symbol)
    facts = companyfacts.get("facts") if isinstance(companyfacts, dict) else None
    us_gaap = facts.get("us-gaap", {}) if isinstance(facts, dict) else {}
    submission_rows = _submission_index(submissions)
    rejected, candidates = [], []
    source_count = processed = 0

    def reject(concept, reason, row=None, metric=None):
        row = row or {}
        if len(rejected) < 256:
            rejected.append(RejectedFinancialFact(metric=metric, concept=concept,
                accession=row.get("accn"), fiscal_year=row.get("fy") if isinstance(row.get("fy"), int) else None,
                fiscal_period=str(row.get("fp")) if row.get("fp") is not None else None,
                period_start=_date(row.get("start")), period_end=_date(row.get("end")), reason=reason))

    def rows_for(concept, unit):
        node = us_gaap.get(concept, {})
        units = node.get("units", {}) if isinstance(node, dict) else {}
        return units.get(unit, []) if isinstance(units.get(unit, []), list) else []

    def row_rank(row):
        return (str(row.get("end") or ""), str(row.get("filed") or ""), str(row.get("accn") or ""))

    streams = []
    for metric, (concepts, expected_unit, share_basis) in SUPPORTED.items():
        for concept in concepts:
            node = us_gaap.get(concept, {})
            units = node.get("units", {}) if isinstance(node, dict) else {}
            for unit, rows in units.items():
                if not isinstance(rows, list):
                    continue
                source_count += len(rows)
                stream = [(metric, concept, expected_unit, share_basis, unit, row)
                    for row in sorted(rows, key=row_rank, reverse=True)]
                if stream:
                    streams.append(stream)

    def rank(item):
        row = item[-1]
        return (str(row.get("end") or ""), str(row.get("filed") or ""), str(row.get("accn") or ""))

    # Interleave newest-first concept/unit streams so one dense concept cannot
    # consume the global processing budget before another supported metric is seen.
    raw = []
    for index in range(max((len(stream) for stream in streams), default=0)):
        tier = [stream[index] for stream in streams if index < len(stream)]
        raw.extend(sorted(tier, key=rank, reverse=True))
        if len(raw) >= max_source_facts:
            break

    annual_seen = defaultdict(set)
    for metric, concept, expected_unit, share_basis, unit, row in raw[:max_source_facts]:
        if processed >= max_source_facts:
            break
        processed += 1
        if unit != expected_unit:
            reject(concept, "incompatible_unit", row, metric)
            continue
        form = row.get("form")
        if form not in ("10-Q", "10-Q/A", "10-K", "10-K/A"):
            reject(concept, "unsupported_form", row, metric)
            continue
        start, end, filed = _date(row.get("start")), _date(row.get("end")), _date(row.get("filed"))
        if not start or not end or not filed or start > end:
            reject(concept, "invalid_period_or_filing_date", row, metric)
            continue
        duration = (end - start).days + 1
        fp = row.get("fp")
        if fp == "FY" and duration > QUARTER_MAX_DAYS:
            year = row.get("fy")
            if year in annual_seen[metric] or len(annual_seen[metric]) >= max_annual_periods:
                continue
            annual_seen[metric].add(year)
            reject(concept, "annual_period_not_normalized_in_this_phase", row, metric)
            continue
        if not QUARTER_MIN_DAYS <= duration <= QUARTER_MAX_DAYS:
            reject(concept, "not_standalone_quarter", row, metric)
            continue
        if form in ("10-K", "10-K/A") and fp != "FY":
            reject(concept, "ambiguous_annual_filing_context", row, metric)
            continue
        if form in ("10-Q", "10-Q/A") and fp not in ("Q1", "Q2", "Q3", "Q4"):
            reject(concept, "unresolved_fiscal_identity", row, metric)
            continue
        if not isinstance(row.get("fy"), int):
            reject(concept, "unresolved_fiscal_identity", row, metric)
            continue
        value = _decimal(row.get("val"))
        accession = str(row.get("accn") or "")
        if value is None or not ACCESSION.fullmatch(accession):
            reject(concept, "invalid_value_or_accession", row, metric)
            continue
        metadata = submission_rows.get(accession, {})
        if metadata.get("form") and metadata["form"] != row.get("form"):
            reject(concept, "filing_metadata_conflict", row, metric)
            continue
        primary = metadata.get("primary_document")
        candidates.append({"metric": metric, "concept": concept, "unit": unit,
            "share_basis": share_basis, "row": row, "start": start, "end": end,
            "filed": filed, "duration": duration, "value": value, "accession": accession,
            "accepted": _datetime(metadata.get("accepted")),
            "report_date": _date(metadata.get("report_date")),
            "url": _source_url(cik, accession, primary)})

    # Basic EPS is explicitly diagnosed and never substituted. It is appended
    # only after supported facts so diagnostics cannot exhaust the rejection cap.
    basic_rows = sorted(rows_for(BASIC_EPS_CONCEPT, "USD/shares"), key=row_rank, reverse=True)
    source_count += len(basic_rows)
    for row in basic_rows[:max_quarters]:
        reject(BASIC_EPS_CONCEPT, "basic_eps_not_diluted", row, "diluted_eps")

    # Resolve the period represented by a fact independently from the host
    # filing's FY/FP. An exact report-date match establishes an anchor. Repeated
    # comparative disclosures may inherit only an unambiguous exact-date anchor.
    by_context = defaultdict(list)
    for candidate in candidates:
        by_context[(candidate["metric"], candidate["concept"], candidate["unit"],
            candidate["start"], candidate["end"])].append(candidate)

    resolved_candidates = []
    for context_rows in by_context.values():
        anchors = set()
        claims = set()
        for candidate in context_rows:
            row = candidate["row"]
            form = row["form"]
            claim = (row["fy"], "Q4" if form in ("10-K", "10-K/A") else row["fp"])
            claims.add(claim)
            if candidate["report_date"] == candidate["end"]:
                anchors.add(claim)
        if len(anchors) == 1:
            identity = next(iter(anchors))
        elif not anchors and len(claims) == 1 and all(
                candidate["row"]["form"] in ("10-Q", "10-Q/A") for candidate in context_rows):
            # Company Facts FY/FP remains usable when every exact context agrees;
            # this preserves bounded older coverage absent from recent submissions.
            identity = next(iter(claims))
        else:
            reason = "conflicting_fiscal_identity" if len(anchors) > 1 or len(claims) > 1 else "unresolved_fiscal_identity"
            for candidate in context_rows:
                reject(candidate["concept"], reason, candidate["row"], candidate["metric"])
            continue
        for candidate in context_rows:
            candidate["fiscal_year"], candidate["fiscal_quarter"] = identity
            resolved_candidates.append(candidate)

    by_period = defaultdict(list)
    for candidate in resolved_candidates:
        by_period[(candidate["metric"], candidate["fiscal_year"],
            candidate["fiscal_quarter"])].append(candidate)

    retained_periods = {}
    for metric in SUPPORTED:
        keys = sorted((key for key in by_period if key[0] == metric),
            key=lambda key: _quarter_index(key[1], key[2]), reverse=True)[:max_quarters]
        retained_periods[metric] = set(keys)

    observations = []
    for key, period_rows in sorted(by_period.items(), key=lambda item: _quarter_index(item[0][1], item[0][2])):
        if key not in retained_periods[key[0]]:
            continue
        concepts = {row["concept"] for row in period_rows}
        contexts = {(row["start"], row["end"]) for row in period_rows}
        if len(concepts) != 1:
            for row in period_rows:
                reject(row["concept"], "ambiguous_concept_mapping", row["row"], key[0])
            continue
        if len(contexts) != 1:
            for row in period_rows:
                reject(row["concept"], "ambiguous_quarterly_context", row["row"], key[0])
            continue
        unique = {}
        for row in period_rows:
            duplicate_key = (row["accession"], row["value"], row["start"], row["end"], row["unit"])
            if duplicate_key in unique:
                reject(row["concept"], "duplicate_source_fact", row["row"], key[0])
            else:
                unique[duplicate_key] = row
        versions = sorted(unique.values(), key=lambda row: (row["filed"], row["accepted"] or
            datetime.combine(row["filed"], datetime.min.time(), tzinfo=timezone.utc), row["accession"]))
        if len(versions) > MAX_VERSIONS_PER_PERIOD:
            for row in versions[:-MAX_VERSIONS_PER_PERIOD]:
                reject(row["concept"], "version_limit_exceeded", row["row"], key[0])
            versions = versions[-MAX_VERSIONS_PER_PERIOD:]
        values = {row["value"] for row in versions}
        amendments = [row for row in versions if row["row"].get("form") in ("10-Q/A", "10-K/A")]
        conflicting_amendments = (len(amendments) > 1 and
            len({(row["filed"], row["value"]) for row in amendments[-2:]}) > 1 and
            amendments[-1]["filed"] == amendments[-2]["filed"])
        latest_is_amendment = bool(amendments) and versions[-1] is amendments[-1]
        if (len(values) > 1 and not latest_is_amendment) or conflicting_amendments:
            statuses = ["conflict"] * len(versions)
            selected = None
        else:
            selected = amendments[-1] if amendments else versions[0]
            statuses = ["current" if row is selected else
                "superseded" if amendments and row["filed"] <= selected["filed"] else "duplicate"
                for row in versions]
        selected_id = None
        if selected:
            selected_id = sha256(f"{symbol}|{key}|{selected['accession']}|{selected['value']}".encode()).hexdigest()[:24]
        for row, status in zip(versions, statuses):
            raw_row = row["row"]
            observation_id = sha256(f"{symbol}|{key}|{row['accession']}|{row['value']}".encode()).hexdigest()[:24]
            reasons = () if status == "current" else (
                "superseded_by_amendment" if status == "superseded" else
                "duplicate_later_filing" if status == "duplicate" else "unresolved_version_conflict",)
            observations.append(HistoricalFinancialObservation(observation_id=observation_id,
                issuer=issuer, ticker=symbol, cik=cik, metric=key[0], fiscal_year=key[1],
                fiscal_quarter=key[2], period_start=row["start"], period_end=row["end"],
                duration_days=row["duration"], original_concept=row["concept"],
                original_value=row["value"], original_unit=row["unit"], normalized_value=row["value"],
                currency="USD", share_basis=row["share_basis"], accession=row["accession"],
                form=raw_row["form"], filing_date=row["filed"], acceptance_time=row["accepted"],
                source_url=row["url"], retrieved_at=retrieved_at, version_status=status,
                superseded_by=selected_id if status == "superseded" else None,
                comparison_eligible=status == "current", comparison_exclusion_reasons=reasons))

    observations.sort(key=lambda row: (row.metric, row.fiscal_year, row.fiscal_quarter,
        row.filing_date, row.accession))
    missing = []
    for metric in SUPPORTED:
        current = [row for row in observations if row.metric == metric and row.version_status == "current"]
        if len(current) < 2:
            continue
        indices = {_quarter_index(row.fiscal_year, row.fiscal_quarter) for row in current}
        for index in range(min(indices), max(indices) + 1):
            if index not in indices:
                year, quarter = _period_from_index(index)
                missing.append(MissingFinancialPeriod(metric=metric, fiscal_year=year, fiscal_quarter=quarter))

    current_count = sum(row.version_status == "current" for row in observations)
    has_conflict = any(row.version_status == "conflict" for row in observations)
    metric_count = len({row.metric for row in observations if row.version_status == "current"})
    status = "available" if metric_count == 2 else "partial" if current_count else "conflict" if has_conflict else "unavailable"
    details = request_diagnostics or {}
    diagnostics = HistoricalFinancialDiagnostics(source_status=status,
        requests=details.get("requests", 0), cache_reads=details.get("cache_reads", 0),
        cache_loads=details.get("cache_loads", 0), cache_hits=details.get("cache_hits", 0),
        source_fact_count=source_count, processed_fact_count=processed,
        accepted_observation_count=len(observations), rejected_fact_count=len(rejected),
        request_budget=details.get("request_budget", 3), cache_ttl_seconds=details.get("cache_ttl_seconds", 21600),
        failure_cache_ttl_seconds=details.get("failure_cache_ttl_seconds", 60),
        timeout_seconds=details.get("timeout_seconds", 5), attempts=details.get("attempts", 1),
        max_source_facts=max_source_facts, max_quarterly_periods=max_quarters,
        max_annual_periods_inspected=max_annual_periods)
    return HistoricalFinancialSnapshot(ticker=symbol, issuer=issuer, cik=cik,
        retrieved_at=retrieved_at, status=status, observations=tuple(observations),
        rejected=tuple(rejected), missing_periods=tuple(missing[:32]), diagnostics=diagnostics)


class SecHistoricalFinancialProvider:
    """Internal-only bounded provider. It is not registered with Analyze."""
    name = "sec_historical_financials"

    def __init__(self, settings, client=None, clock=lambda: datetime.now(timezone.utc), *,
            cache_clock=None, enabled=None):
        self.settings, self.client, self.clock = settings, client or JsonClient(settings), clock
        self.mapping_cache = Cache(settings.outlook_failure_cache_ttl, capacity=1)
        self.history_cache = _PerKeyCache(settings.outlook_failure_cache_ttl,
            clock=cache_clock, capacity=128)
        self.lock = RLock()
        self.cache_reads = self.cache_loads = self.requests = 0
        active = settings.outlook_sec_history_enabled if enabled is None else enabled
        self.unavailable_reason = ("disabled" if not active else
            "missing_configuration" if not re.search(r"\S+@\S+\.\S+", settings.outlook_sec_user_agent) else None)

    def _get(self, url, budget):
        if budget[0] >= self.settings.outlook_sec_history_request_budget:
            raise ProviderUnavailable("sec_history_request_budget_exceeded")
        budget[0] += 1
        with self.lock:
            self.requests += 1
        return self.client.get(url, provider="sec", user_agent=self.settings.outlook_sec_user_agent)

    def _load(self, symbol):
        with self.lock:
            self.cache_loads += 1
        budget = [0]
        mapping = self.mapping_cache.get("sec_ticker_mapping",
            lambda: ticker_mapping(self._get("https://www.sec.gov/files/company_tickers.json", budget)),
            self.settings.outlook_cik_cache_ttl)
        cik = mapping.get(sec_symbol(symbol))
        if not cik:
            raise ProviderUnavailable("sec_ticker_not_found")
        companyfacts = self._get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", budget)
        submissions = self._get(f"https://data.sec.gov/submissions/CIK{cik}.json", budget)
        snapshot = normalize_companyfacts(companyfacts, submissions, symbol, self.clock(),
            max_source_facts=self.settings.outlook_sec_history_max_source_facts,
            max_quarters=self.settings.outlook_sec_history_max_quarters,
            max_annual_periods=self.settings.outlook_sec_history_max_annual_periods,
            request_diagnostics={"requests": budget[0],
                "request_budget": self.settings.outlook_sec_history_request_budget,
                "cache_ttl_seconds": self.settings.outlook_sec_history_cache_ttl,
                "failure_cache_ttl_seconds": self.settings.outlook_failure_cache_ttl,
                "timeout_seconds": self.settings.outlook_http_timeout,
                "attempts": self.settings.outlook_http_attempts})
        typed_submissions = adapt_sec_submissions(submissions, issuer=snapshot.issuer,
            cik=snapshot.cik, source_identity=f"sec-submissions:CIK{snapshot.cik}:recent")
        return RevenueHistoricalAcquisition(snapshot=snapshot, submissions=typed_submissions,
            evidence_fingerprint=_acquisition_fingerprint(snapshot, typed_submissions),
            logical_requests=budget[0], http_attempts=budget[0], cache_state="miss")

    def _bundle(self, symbol):
        with self.lock:
            self.cache_reads += 1
        bundle, cache_state = self.history_cache.get(symbol, lambda: self._load(symbol),
            self.settings.outlook_sec_history_cache_ttl)
        return bundle.model_copy(update={"logical_requests": 0 if cache_state == "success_hit" else bundle.logical_requests,
            "http_attempts": 0 if cache_state == "success_hit" else bundle.http_attempts,
            "cache_state": cache_state})

    def get_acquisition(self, ticker):
        """One-attempt revenue-history acquisition; no filing-document work."""
        symbol = str(ticker).strip().upper()
        if self.settings.outlook_http_attempts != 1:
            raise ProviderUnavailable("revenue_history_single_attempt_required")
        if self.unavailable_reason:
            raise ProviderUnavailable(self.unavailable_reason)
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,15}", symbol):
            raise ValueError("invalid_symbol")
        return self._bundle(symbol)

    def get_history(self, ticker):
        symbol = str(ticker).strip().upper()
        if self.unavailable_reason:
            raise ProviderUnavailable(self.unavailable_reason)
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,15}", symbol):
            raise ValueError("invalid_symbol")
        bundle = self._bundle(symbol)
        result = bundle.snapshot
        with self.lock:
            diagnostics = result.diagnostics.model_copy(update={
                "cache_reads": self.cache_reads, "cache_loads": self.cache_loads,
                "cache_hits": self.cache_reads - self.cache_loads,
                "requests": self.requests})
        return result.model_copy(update={"diagnostics": diagnostics})
