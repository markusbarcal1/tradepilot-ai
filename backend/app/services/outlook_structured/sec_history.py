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
    AnnualEpsComparabilityEvidence, AnnualEpsDiagnostics, AnnualEpsObservation, AnnualEpsYearOutcome,
    AnnualRevenueDiagnostics, AnnualRevenueObservation, AnnualRevenueYearOutcome,
    EpsHistoryDiagnostics, QuarterlyEpsDiagnostics,
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
    annual = [row.model_dump(mode="json", exclude={"retrieved_at", "acceptance_time"})
        for row in snapshot.annual_revenue_observations]
    annual_eps = [row.model_dump(mode="json", exclude={"retrieved_at", "acceptance_time"})
        for row in snapshot.annual_eps_observations]
    annual_eps_sources = [row.model_dump(mode="json", exclude={"retrieved_at", "acceptance_time"})
        for row in snapshot.annual_eps_source_observations]
    content = {"policy": ACQUISITION_POLICY, "ticker": snapshot.ticker,
        "issuer": snapshot.issuer, "cik": snapshot.cik, "observations": observations,
        "annual_revenue_observations": annual,
        "annual_revenue_diagnostics": snapshot.diagnostics.annual_revenue.model_dump(mode="json"),
        "annual_eps_observations": annual_eps,
        "annual_eps_source_observations": annual_eps_sources,
        "eps_diagnostics": snapshot.diagnostics.eps.model_dump(mode="json"),
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
                           max_annual_periods=5, max_annual_source_facts=128,
                           max_annual_eps_periods=5, max_annual_eps_source_facts=128,
                           annual_eps_comparability_evidence=(),
                           request_diagnostics=None):
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

    # Annual revenue has an independent bounded pass. Grouping by fiscal year
    # happens before the budget is applied so a year is never partially examined.
    annual_source_rows = []
    for concept in REVENUE_CONCEPTS:
        for row in rows_for(concept, "USD"):
            start, end = _date(row.get("start")), _date(row.get("end"))
            if row.get("fp") == "FY" and start and end and start <= end and (end - start).days + 1 > QUARTER_MAX_DAYS:
                annual_source_rows.append((concept, row, start, end))
    annual_groups = defaultdict(list)
    invalid_annual_identity = []
    for item in annual_source_rows:
        year = item[1].get("fy")
        if isinstance(year, int): annual_groups[year].append(item)
        else: invalid_annual_identity.append(item)
    ordered_years = sorted(annual_groups, key=lambda year: max(
        (item[3], str(item[1].get("filed") or ""), str(item[1].get("accn") or ""))
        for item in annual_groups[year]), reverse=True)
    admitted, source_limit_excluded = [], []
    annual_year_reasons = defaultdict(set)
    charged = 0
    for index, year in enumerate(ordered_years):
        group = annual_groups[year]
        if charged + len(group) > max_annual_source_facts:
            source_limit_excluded.extend(ordered_years[index:])
            break
        admitted.extend(group); charged += len(group)
    for year in source_limit_excluded:
        annual_year_reasons[year].add("annual_source_limit_exceeded")
        for concept, row, _, _ in annual_groups[year]:
            reject(concept, "annual_source_limit_exceeded", row, "revenue")
    for concept, row, _, _ in invalid_annual_identity:
        reject(concept, "annual_fiscal_identity_invalid", row, "revenue")

    annual_candidates = []
    annual_validation_rejections = len(invalid_annual_identity) + sum(
        len(annual_groups[year]) for year in source_limit_excluded)
    for concept, row, start, end in admitted:
        form = row.get("form"); filed = _date(row.get("filed")); year = row.get("fy")
        duration = (end - start).days + 1
        if not filed:
            reject(concept, "invalid_period_or_filing_date", row, "revenue"); annual_year_reasons[year].add("invalid_period_or_filing_date"); annual_validation_rejections += 1; continue
        if form not in ("10-K", "10-K/A"):
            reject(concept, "annual_filing_context_invalid", row, "revenue"); annual_year_reasons[year].add("annual_filing_context_invalid"); annual_validation_rejections += 1; continue
        if not 300 <= duration <= 380:
            reject(concept, "annual_period_duration_invalid", row, "revenue"); annual_year_reasons[year].add("annual_period_duration_invalid"); annual_validation_rejections += 1; continue
        value = _decimal(row.get("val")); accession = str(row.get("accn") or "")
        if value is None or not ACCESSION.fullmatch(accession):
            reject(concept, "invalid_value_or_accession", row, "revenue"); annual_year_reasons[year].add("invalid_value_or_accession"); annual_validation_rejections += 1; continue
        metadata = submission_rows.get(accession)
        if not metadata or metadata.get("form") != form or _date(metadata.get("report_date")) != end:
            reject(concept, "annual_filing_context_invalid", row, "revenue"); annual_year_reasons[year].add("annual_filing_context_invalid"); annual_validation_rejections += 1; continue
        annual_candidates.append({"concept": concept, "unit": "USD", "row": row,
            "start": start, "end": end, "filed": filed, "duration": duration,
            "value": value, "accession": accession,
            "accepted": _datetime(metadata.get("accepted")),
            "url": _source_url(cik, accession, metadata.get("primary_document")),
            "fiscal_year": year})

    certified_annual_observations = []
    conflicted_annual_years = set()
    by_annual_year = defaultdict(list)
    for candidate in annual_candidates:
        by_annual_year[candidate["fiscal_year"]].append(candidate)
    for year, period_rows in sorted(by_annual_year.items()):
        concepts = {row["concept"] for row in period_rows}
        contexts = {(row["start"], row["end"]) for row in period_rows}
        if len(concepts) != 1 or len(contexts) != 1:
            conflicted_annual_years.add(year)
            reason = "ambiguous_concept_mapping" if len(concepts) != 1 else "ambiguous_annual_context"
            annual_year_reasons[year].add(reason)
            for row in period_rows:
                reject(row["concept"], reason, row["row"], "revenue")
            continue
        unique = {}
        for row in period_rows:
            key = (row["accession"], row["value"], row["start"], row["end"], row["unit"])
            if key in unique:
                reject(row["concept"], "duplicate_source_fact", row["row"], "revenue")
            else:
                unique[key] = row
        versions = sorted(unique.values(), key=lambda row: (row["filed"], row["accepted"] or
            datetime.combine(row["filed"], datetime.min.time(), tzinfo=timezone.utc), row["accession"]))
        if len(versions) > MAX_VERSIONS_PER_PERIOD:
            for row in versions[:-MAX_VERSIONS_PER_PERIOD]:
                reject(row["concept"], "version_limit_exceeded", row["row"], "revenue")
            versions = versions[-MAX_VERSIONS_PER_PERIOD:]
        amendments = [row for row in versions if row["row"].get("form") == "10-K/A"]
        conflicting_amendments = (len(amendments) > 1 and
            amendments[-1]["filed"] == amendments[-2]["filed"] and
            amendments[-1]["value"] != amendments[-2]["value"])
        if (len({row["value"] for row in versions}) > 1 and
                (not amendments or versions[-1] is not amendments[-1])) or conflicting_amendments:
            conflicted_annual_years.add(year)
            annual_year_reasons[year].add("unresolved_annual_version_conflict")
            for row in versions:
                reject(row["concept"], "unresolved_annual_version_conflict", row["row"], "revenue")
            continue
        selected = amendments[-1] if amendments else versions[-1]
        certified_annual_observations.append(AnnualRevenueObservation(
            observation_id=sha256(f"{symbol}|annual|{year}|{selected['accession']}|{selected['value']}".encode()).hexdigest()[:24],
            issuer=issuer, ticker=symbol, cik=cik, fiscal_year=year,
            period_start=selected["start"], period_end=selected["end"],
            duration_days=selected["duration"], exact_revenue=selected["value"],
            original_concept=selected["concept"], accession=selected["accession"],
            form=selected["row"]["form"], filing_date=selected["filed"],
            acceptance_time=selected["accepted"], source_url=selected["url"],
            retrieved_at=retrieved_at, provenance_label=("SEC 10-K/A annual revenue (amended)"
                if selected["row"]["form"] == "10-K/A" else "SEC 10-K annual revenue")))
    certified_annual_observations.sort(key=lambda row: (row.period_end, row.filing_date,
        row.acceptance_time or datetime.combine(row.filing_date, datetime.min.time(), tzinfo=timezone.utc),
        row.fiscal_year))
    annual_observations = (sorted(certified_annual_observations[-max_annual_periods:],
        key=lambda row: row.fiscal_year) if max_annual_periods else [])
    retained_years = {row.fiscal_year for row in annual_observations}
    certified_years = {row.fiscal_year for row in certified_annual_observations}
    excluded_years = tuple(sorted(set(ordered_years) - retained_years))
    annual_rejected_candidate_count = annual_validation_rejections + sum(
        len(by_annual_year[year]) for year in conflicted_annual_years)
    annual_by_year = {row.fiscal_year: row for row in annual_observations}
    annual_observations = [row.model_copy(update={"yoy_growth_pct":
        ((row.exact_revenue - annual_by_year[row.fiscal_year - 1].exact_revenue) /
         annual_by_year[row.fiscal_year - 1].exact_revenue * Decimal("100"))
        if row.fiscal_year - 1 in annual_by_year and
           annual_by_year[row.fiscal_year - 1].exact_revenue != 0 else None})
        for row in annual_observations]

    # Annual diluted EPS is certified in an independent bounded pass. EPS is a
    # signed per-share ratio, so no revenue outcome, positivity rule, growth
    # calculation, or Q4 arithmetic participates in this policy.
    quarterly_eps_validated_candidate_count = sum(
        candidate["metric"] == "diluted_eps" for candidate in resolved_candidates)
    quarterly_eps_rejection_reasons = tuple(sorted({row.reason for row in rejected
        if row.metric == "diluted_eps"}))[:32]
    quarterly_eps_rejected_fact_count = sum(row.metric == "diluted_eps" for row in rejected)
    annual_eps_rejected_start = len(rejected)
    annual_eps_source_rows = []
    eps_node = us_gaap.get(DILUTED_EPS_CONCEPT, {})
    eps_units = eps_node.get("units", {}) if isinstance(eps_node, dict) else {}
    for unit, rows in eps_units.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            start, end = _date(row.get("start")), _date(row.get("end"))
            if row.get("fp") == "FY" and start and end and start <= end and (end - start).days + 1 > QUARTER_MAX_DAYS:
                annual_eps_source_rows.append((row, start, end, unit))
    annual_eps_groups = defaultdict(list)
    invalid_annual_eps_identity = []
    for item in annual_eps_source_rows:
        year = item[0].get("fy")
        if isinstance(year, int):
            annual_eps_groups[year].append(item)
        else:
            invalid_annual_eps_identity.append(item)
    ordered_eps_years = sorted(annual_eps_groups, key=lambda year: max(
        (item[2], str(item[0].get("filed") or ""), str(item[0].get("accn") or ""))
        for item in annual_eps_groups[year]), reverse=True)
    admitted_eps, eps_source_limit_excluded = [], []
    annual_eps_year_reasons = defaultdict(set)
    charged_eps = 0
    for index, year in enumerate(ordered_eps_years):
        group = annual_eps_groups[year]
        if charged_eps + len(group) > max_annual_eps_source_facts:
            eps_source_limit_excluded.extend(ordered_eps_years[index:])
            break
        admitted_eps.extend(group)
        charged_eps += len(group)
    for year in eps_source_limit_excluded:
        annual_eps_year_reasons[year].add("annual_source_limit_exceeded")
        for row, _, _, _ in annual_eps_groups[year]:
            reject(DILUTED_EPS_CONCEPT, "annual_source_limit_exceeded", row, "diluted_eps")
    for row, _, _, _ in invalid_annual_eps_identity:
        reject(DILUTED_EPS_CONCEPT, "annual_fiscal_identity_invalid", row, "diluted_eps")

    evidence_by_accession = {}
    for item in annual_eps_comparability_evidence:
        evidence = (item if isinstance(item, AnnualEpsComparabilityEvidence) else
            AnnualEpsComparabilityEvidence.model_validate(item))
        if evidence.accession in evidence_by_accession:
            raise ValueError("duplicate_annual_eps_comparability_evidence")
        evidence_by_accession[evidence.accession] = evidence

    def has_comparability_evidence(candidate):
        evidence = evidence_by_accession.get(candidate["accession"])
        return bool(evidence and evidence.source_url == candidate["url"])

    annual_eps_candidates = []
    annual_eps_validation_rejections = len(invalid_annual_eps_identity) + sum(
        len(annual_eps_groups[year]) for year in eps_source_limit_excluded)
    for row, start, end, unit in admitted_eps:
        form = row.get("form"); filed = _date(row.get("filed")); year = row.get("fy")
        duration = (end - start).days + 1
        if unit != "USD/shares":
            reject(DILUTED_EPS_CONCEPT, "incompatible_unit", row, "diluted_eps"); annual_eps_year_reasons[year].add("incompatible_unit"); annual_eps_validation_rejections += 1; continue
        if not filed:
            reject(DILUTED_EPS_CONCEPT, "invalid_period_or_filing_date", row, "diluted_eps"); annual_eps_year_reasons[year].add("invalid_period_or_filing_date"); annual_eps_validation_rejections += 1; continue
        if form not in ("10-K", "10-K/A"):
            reject(DILUTED_EPS_CONCEPT, "annual_filing_context_invalid", row, "diluted_eps"); annual_eps_year_reasons[year].add("annual_filing_context_invalid"); annual_eps_validation_rejections += 1; continue
        if not 300 <= duration <= 380:
            reject(DILUTED_EPS_CONCEPT, "annual_period_duration_invalid", row, "diluted_eps"); annual_eps_year_reasons[year].add("annual_period_duration_invalid"); annual_eps_validation_rejections += 1; continue
        value = _decimal(row.get("val")); accession = str(row.get("accn") or "")
        if value is None or not ACCESSION.fullmatch(accession):
            reject(DILUTED_EPS_CONCEPT, "invalid_value_or_accession", row, "diluted_eps"); annual_eps_year_reasons[year].add("invalid_value_or_accession"); annual_eps_validation_rejections += 1; continue
        metadata = submission_rows.get(accession)
        if not metadata or metadata.get("form") != form:
            reject(DILUTED_EPS_CONCEPT, "annual_filing_context_invalid", row, "diluted_eps"); annual_eps_year_reasons[year].add("annual_filing_context_invalid"); annual_eps_validation_rejections += 1; continue
        annual_eps_candidates.append({"unit": unit, "row": row, "start": start,
            "end": end, "filed": filed, "duration": duration, "value": value,
            "accession": accession, "accepted": _datetime(metadata.get("accepted")),
            "report_date": _date(metadata.get("report_date")),
            "url": _source_url(cik, accession, metadata.get("primary_document")),
            "claimed_fiscal_year": year})

    # A full-year context is owned by the one original-period filing whose SEC
    # submissions report date exactly matches the fact period end. Later 10-K
    # comparative disclosures may inherit that identity only when the anchor is
    # unique; the host filing's FY is never assumed to be the represented year.
    by_annual_eps_context = defaultdict(list)
    for candidate in annual_eps_candidates:
        by_annual_eps_context[(candidate["start"], candidate["end"])].append(candidate)
    anchored_contexts_by_year = defaultdict(set)
    for context, context_rows in by_annual_eps_context.items():
        for row in context_rows:
            if row["report_date"] == row["end"]:
                anchored_contexts_by_year[row["claimed_fiscal_year"]].add(context)
    ambiguous_anchor_years = {year for year, contexts in anchored_contexts_by_year.items()
        if len(contexts) > 1}
    preconflicted_annual_eps_years = set(ambiguous_anchor_years)
    resolved_annual_eps_candidates = []
    for context_rows in by_annual_eps_context.values():
        anchors = {row["claimed_fiscal_year"] for row in context_rows
            if row["report_date"] == row["end"]}
        if len(anchors) != 1 or bool(anchors & ambiguous_anchor_years):
            for row in context_rows:
                year = row["claimed_fiscal_year"]
                annual_eps_year_reasons[year].add("ambiguous_annual_context")
                reject(DILUTED_EPS_CONCEPT, "ambiguous_annual_context", row["row"], "diluted_eps")
            continue
        represented_year = next(iter(anchors))
        for row in context_rows:
            row["fiscal_year"] = represented_year
            row["disclosure_type"] = ("original_period" if row["report_date"] == row["end"]
                else "later_comparative")
            resolved_annual_eps_candidates.append(row)

    certified_annual_eps = []
    annual_eps_source_observations = []
    conflicted_annual_eps_years = set(preconflicted_annual_eps_years)
    by_annual_eps_year = defaultdict(list)
    for candidate in resolved_annual_eps_candidates:
        by_annual_eps_year[candidate["fiscal_year"]].append(candidate)
    selected_by_year = {}
    parent = {}

    def find(year):
        parent.setdefault(year, year)
        if parent[year] != year:
            parent[year] = find(parent[year])
        return parent[year]

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for year, period_rows in sorted(by_annual_eps_year.items()):
        unique = {}
        for row in period_rows:
            key = (row["accession"], row["value"], row["start"], row["end"], row["unit"])
            if key in unique:
                reject(DILUTED_EPS_CONCEPT, "duplicate_source_fact", row["row"], "diluted_eps")
            else:
                unique[key] = row
        versions = sorted(unique.values(), key=lambda row: (row["filed"], row["accepted"] or
            datetime.combine(row["filed"], datetime.min.time(), tzinfo=timezone.utc), row["accession"]))
        if len(versions) > MAX_VERSIONS_PER_PERIOD:
            for row in versions[:-MAX_VERSIONS_PER_PERIOD]:
                reject(DILUTED_EPS_CONCEPT, "version_limit_exceeded", row["row"], "diluted_eps")
            versions = versions[-MAX_VERSIONS_PER_PERIOD:]
        original_versions = [row for row in versions if row["disclosure_type"] == "original_period"]
        comparative_versions = [row for row in versions if row["disclosure_type"] == "later_comparative"]
        amendments = [row for row in original_versions if row["row"].get("form") == "10-K/A"]
        conflicting_amendments = (len(amendments) > 1 and
            amendments[-1]["filed"] == amendments[-2]["filed"] and
            amendments[-1]["value"] != amendments[-2]["value"])
        if not original_versions or ((len({row["value"] for row in original_versions}) > 1 and
                (not amendments or original_versions[-1] is not amendments[-1])) or conflicting_amendments):
            conflicted_annual_eps_years.add(year)
            annual_eps_year_reasons[year].add("unresolved_annual_version_conflict")
            for row in versions:
                reject(DILUTED_EPS_CONCEPT, "unresolved_annual_version_conflict", row["row"], "diluted_eps")
            continue
        original = amendments[-1] if amendments else original_versions[-1]
        eligible_adjusted = [row for row in comparative_versions
            if row["value"] != original["value"] and has_comparability_evidence(row)]
        if len({row["value"] for row in eligible_adjusted}) > 1:
            conflicted_annual_eps_years.add(year)
            annual_eps_year_reasons[year].add("conflicting_comparative_adjustments")
            for row in eligible_adjusted:
                reject(DILUTED_EPS_CONCEPT, "conflicting_comparative_adjustments", row["row"], "diluted_eps")
            continue
        selected = eligible_adjusted[-1] if eligible_adjusted else original
        selected_by_year[year] = selected
        find(year)
        for comparative in comparative_versions:
            same_value = comparative["value"] == original["value"]
            has_evidence = has_comparability_evidence(comparative)
            if same_value or has_evidence:
                union(year, comparative["claimed_fiscal_year"])
            elif comparative["value"] != original["value"]:
                reject(DILUTED_EPS_CONCEPT, "comparative_adjustment_evidence_missing",
                    comparative["row"], "diluted_eps")
        # Retain every validated source version internally. Public selection is
        # constructed only after comparison groups and breaks are finalized.
        for version in versions:
            explicit = has_comparability_evidence(version)
            annual_eps_source_observations.append(AnnualEpsObservation(
                observation_id=sha256(f"{symbol}|annual_eps_source|{year}|{version['accession']}|{version['value']}".encode()).hexdigest()[:24],
                issuer=issuer, ticker=symbol, cik=cik, fiscal_year=year,
                period_start=version["start"], period_end=version["end"], duration_days=version["duration"],
                exact_eps=version["value"], accession=version["accession"], form=version["row"]["form"],
                filing_date=version["filed"], acceptance_time=version["accepted"], source_url=version["url"],
                retrieved_at=retrieved_at, disclosure_type=version["disclosure_type"],
                split_adjustment_status="explicit_retrospective" if explicit else "not_established",
                share_basis_comparability="established" if explicit or version["value"] == original["value"] else "unknown",
                comparison_group=f"FY{find(year)}",
                provenance_label=("SEC 10-K/A comparative annual GAAP diluted EPS (amended)"
                    if version["disclosure_type"] == "later_comparative" and version["row"]["form"] == "10-K/A" else
                    "SEC 10-K comparative annual GAAP diluted EPS" if version["disclosure_type"] == "later_comparative" else
                    "SEC 10-K/A annual GAAP diluted EPS (amended)" if version["row"]["form"] == "10-K/A" else
                    "SEC 10-K annual GAAP diluted EPS")))

    annual_eps_source_observations = [row.model_copy(update={
        "comparison_group": f"FY{find(row.fiscal_year)}"}) for row in annual_eps_source_observations]
    prior_root = None
    for year, selected in sorted(selected_by_year.items()):
        root = find(year)
        group_members = {item for item in parent if find(item) == root}
        explicit = has_comparability_evidence(selected)
        break_before = prior_root is not None and root != prior_root
        certified_annual_eps.append(AnnualEpsObservation(
            observation_id=sha256(f"{symbol}|annual_eps|{year}|{selected['accession']}|{selected['value']}".encode()).hexdigest()[:24],
            issuer=issuer, ticker=symbol, cik=cik, fiscal_year=year,
            period_start=selected["start"], period_end=selected["end"],
            duration_days=selected["duration"], exact_eps=selected["value"],
            accession=selected["accession"], form=selected["row"]["form"],
            filing_date=selected["filed"], acceptance_time=selected["accepted"],
            source_url=selected["url"], retrieved_at=retrieved_at,
            disclosure_type=selected["disclosure_type"],
            split_adjustment_status="explicit_retrospective" if explicit else "not_established",
            share_basis_comparability="established" if explicit or len(group_members) > 1 else "unknown",
            comparison_group=f"FY{root}", comparison_break_before=break_before,
            provenance_label=("SEC 10-K/A comparative annual GAAP diluted EPS (amended)"
                if selected["disclosure_type"] == "later_comparative" and selected["row"]["form"] == "10-K/A" else
                "SEC 10-K comparative annual GAAP diluted EPS" if selected["disclosure_type"] == "later_comparative" else
                "SEC 10-K/A annual GAAP diluted EPS (amended)" if selected["row"]["form"] == "10-K/A" else
                "SEC 10-K annual GAAP diluted EPS")))
        prior_root = root
    certified_annual_eps.sort(key=lambda row: (row.period_end, row.filing_date,
        row.acceptance_time or datetime.combine(row.filing_date, datetime.min.time(), tzinfo=timezone.utc),
        row.fiscal_year))
    annual_eps_observations = (sorted(certified_annual_eps[-max_annual_eps_periods:],
        key=lambda row: row.fiscal_year) if max_annual_eps_periods else [])
    retained_eps_years = {row.fiscal_year for row in annual_eps_observations}
    certified_eps_years = {row.fiscal_year for row in certified_annual_eps}
    excluded_eps_years = tuple(sorted(set(ordered_eps_years) - retained_eps_years))
    annual_eps_rejected_candidate_count = annual_eps_validation_rejections + sum(
        len(by_annual_eps_year[year]) for year in conflicted_annual_eps_years)
    diagnostic_eps_years = (list(range(min(ordered_eps_years), max(ordered_eps_years) + 1))[-16:]
        if ordered_eps_years else [])
    annual_eps_outcomes = []
    for year in diagnostic_eps_years:
        discovered_count = len(annual_eps_groups.get(year, ()))
        validated_count = len(by_annual_eps_year.get(year, ()))
        if year in eps_source_limit_excluded:
            state, reasons = "source_limit_excluded", ("annual_source_limit_exceeded",)
        elif year in conflicted_annual_eps_years:
            state, reasons = "conflict", tuple(sorted(annual_eps_year_reasons[year]))
        elif year in retained_eps_years:
            state, reasons = "certified", ()
        elif year in certified_eps_years:
            state, reasons = "retention_excluded", ("annual_retention_limit",)
        elif discovered_count:
            state, reasons = "rejected", tuple(sorted(annual_eps_year_reasons[year]))
        else:
            state, reasons = "no_supported_candidate", ("no_supported_candidate",)
        annual_eps_outcomes.append(AnnualEpsYearOutcome(fiscal_year=year,
            discovered_candidate_count=discovered_count,
            validated_candidate_count=validated_count, state=state, reasons=reasons))
    annual_eps_diagnostics = AnnualEpsDiagnostics(
        state=("partial" if annual_eps_observations and conflicted_annual_eps_years else
            "available" if annual_eps_observations else
            "conflict" if conflicted_annual_eps_years else "unavailable"),
        source_limit_state="limit_exceeded" if eps_source_limit_excluded else "complete",
        source_fact_limit=max_annual_eps_source_facts,
        discovered_source_fact_count=len(annual_eps_source_rows),
        discovered_fiscal_year_count=len(annual_eps_groups),
        validated_candidate_count=len(resolved_annual_eps_candidates),
        rejected_candidate_count=annual_eps_rejected_candidate_count,
        conflicted_fiscal_year_count=len(conflicted_annual_eps_years),
        certified_fiscal_year_count=len(certified_annual_eps),
        retained_fiscal_year_count=len(annual_eps_observations),
        excluded_fiscal_years=excluded_eps_years[:64],
        source_limit_excluded_fiscal_years=tuple(eps_source_limit_excluded[:64]),
        rejection_reasons=tuple(sorted({row.reason for row in rejected[annual_eps_rejected_start:]}))[:32],
        year_outcomes=tuple(annual_eps_outcomes))
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
    if ordered_years:
        diagnostic_years = list(range(min(ordered_years), max(ordered_years) + 1))[-16:]
    else:
        diagnostic_years = []
    year_outcomes = []
    for year in diagnostic_years:
        discovered_count = len(annual_groups.get(year, ()))
        validated_count = len(by_annual_year.get(year, ()))
        if year in source_limit_excluded:
            state, reasons = "source_limit_excluded", ("annual_source_limit_exceeded",)
        elif year in conflicted_annual_years:
            state, reasons = "conflict", tuple(sorted(annual_year_reasons[year]))
        elif year in retained_years:
            state, reasons = "certified", ()
        elif year in certified_years:
            state, reasons = "retention_excluded", ("annual_retention_limit",)
        elif discovered_count:
            state, reasons = "rejected", tuple(sorted(annual_year_reasons[year]))
        else:
            state, reasons = "no_supported_candidate", ("no_supported_candidate",)
        year_outcomes.append(AnnualRevenueYearOutcome(fiscal_year=year,
            discovered_candidate_count=discovered_count,
            validated_candidate_count=validated_count, state=state, reasons=reasons))
    annual_diagnostics = AnnualRevenueDiagnostics(
        source_limit_state="limit_exceeded" if source_limit_excluded else "complete",
        source_fact_limit=max_annual_source_facts,
        discovered_source_fact_count=len(annual_source_rows),
        discovered_fiscal_year_count=len(annual_groups),
        validated_candidate_count=len(annual_candidates),
        rejected_candidate_count=annual_rejected_candidate_count,
        conflicted_fiscal_year_count=len(conflicted_annual_years),
        certified_fiscal_year_count=len(certified_annual_observations),
        retained_fiscal_year_count=len(annual_observations),
        excluded_fiscal_years=excluded_years[:64],
        source_limit_excluded_fiscal_years=tuple(source_limit_excluded[:64]),
        year_outcomes=tuple(year_outcomes))
    quarterly_eps_rows = [row for row in observations if row.metric == "diluted_eps"]
    quarterly_eps_current = [row for row in quarterly_eps_rows if row.version_status == "current"]
    quarterly_eps_conflicts = {(row.fiscal_year, row.fiscal_quarter) for row in quarterly_eps_rows
        if row.version_status == "conflict"}
    eps_missing = tuple(f"FY{row.fiscal_year}:{row.fiscal_quarter}" for row in missing
        if row.metric == "diluted_eps")
    quarterly_eps_source_count = sum(len(rows) for rows in eps_units.values() if isinstance(rows, list))
    eps_diagnostics = EpsHistoryDiagnostics(annual=annual_eps_diagnostics,
        quarterly=QuarterlyEpsDiagnostics(
            state=("partial" if quarterly_eps_current and quarterly_eps_conflicts else
                "available" if quarterly_eps_current else
                "conflict" if quarterly_eps_conflicts else "unavailable"),
            retained_period_limit=max_quarters,
            discovered_source_fact_count=quarterly_eps_source_count,
            validated_candidate_count=quarterly_eps_validated_candidate_count,
            certified_quarter_count=len(quarterly_eps_current),
            conflicted_quarter_count=len(quarterly_eps_conflicts),
            missing_periods=eps_missing[:32], rejected_fact_count=quarterly_eps_rejected_fact_count,
            rejection_reasons=quarterly_eps_rejection_reasons))
    diagnostics = HistoricalFinancialDiagnostics(source_status=status,
        requests=details.get("requests", 0), cache_reads=details.get("cache_reads", 0),
        cache_loads=details.get("cache_loads", 0), cache_hits=details.get("cache_hits", 0),
        source_fact_count=source_count, processed_fact_count=processed,
        accepted_observation_count=len(observations), rejected_fact_count=len(rejected),
        request_budget=details.get("request_budget", 3), cache_ttl_seconds=details.get("cache_ttl_seconds", 21600),
        failure_cache_ttl_seconds=details.get("failure_cache_ttl_seconds", 60),
        timeout_seconds=details.get("timeout_seconds", 5), attempts=details.get("attempts", 1),
        max_source_facts=max_source_facts, max_quarterly_periods=max_quarters,
        max_annual_periods_inspected=max_annual_periods, annual_revenue=annual_diagnostics,
        eps=eps_diagnostics,
        eps_document_evidence_state=details.get("eps_document_evidence_state", "not_requested"),
        eps_document_logical_requests=details.get("eps_document_logical_requests", 0),
        eps_document_http_attempts=details.get("eps_document_http_attempts", 0),
        eps_document_cache_hits=details.get("eps_document_cache_hits", 0),
        eps_document_failures=details.get("eps_document_failures", 0),
        eps_document_failure_reasons=details.get("eps_document_failure_reasons", ()))
    return HistoricalFinancialSnapshot(ticker=symbol, issuer=issuer, cik=cik,
        retrieved_at=retrieved_at, status=status, observations=tuple(observations),
        annual_revenue_observations=tuple(annual_observations),
        annual_eps_observations=tuple(annual_eps_observations),
        annual_eps_source_observations=tuple(annual_eps_source_observations[-64:]),
        rejected=tuple(rejected), missing_periods=tuple(missing[:32]), diagnostics=diagnostics)


class SecHistoricalFinancialProvider:
    """Internal-only bounded provider. It is not registered with Analyze."""
    name = "sec_historical_financials"

    def __init__(self, settings, client=None, clock=lambda: datetime.now(timezone.utc), *,
            cache_clock=None, enabled=None, eps_evidence_enabled=False, eps_evidence_loader=None):
        self.settings, self.client, self.clock = settings, client or JsonClient(settings), clock
        self.mapping_cache = Cache(settings.outlook_failure_cache_ttl, capacity=1)
        self.history_cache = _PerKeyCache(settings.outlook_failure_cache_ttl,
            clock=cache_clock, capacity=128)
        self.lock = RLock()
        self.cache_reads = self.cache_loads = self.requests = 0
        self.eps_evidence_enabled = eps_evidence_enabled
        self.eps_evidence_loader = eps_evidence_loader
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
        request_diagnostics = {"requests": budget[0],
            "request_budget": self.settings.outlook_sec_history_request_budget,
            "cache_ttl_seconds": self.settings.outlook_sec_history_cache_ttl,
            "failure_cache_ttl_seconds": self.settings.outlook_failure_cache_ttl,
            "timeout_seconds": self.settings.outlook_http_timeout,
            "attempts": self.settings.outlook_http_attempts}
        snapshot = normalize_companyfacts(companyfacts, submissions, symbol, self.clock(),
            max_source_facts=self.settings.outlook_sec_history_max_source_facts,
            max_quarters=self.settings.outlook_sec_history_max_quarters,
            max_annual_periods=self.settings.outlook_sec_history_max_annual_periods,
            max_annual_source_facts=self.settings.outlook_sec_history_max_annual_source_facts,
            request_diagnostics=request_diagnostics)
        if self.eps_evidence_enabled and self.eps_evidence_loader is not None:
            try:
                result = self.eps_evidence_loader(snapshot)
                state = ("available" if result.evidence and not result.failures else
                    "partial" if result.evidence else
                    "budget_exhausted" if "request_budget_exhausted" in result.reasons else
                    "rejected" if result.logical_documents else "not_required")
                snapshot = normalize_companyfacts(companyfacts, submissions, symbol, self.clock(),
                    max_source_facts=self.settings.outlook_sec_history_max_source_facts,
                    max_quarters=self.settings.outlook_sec_history_max_quarters,
                    max_annual_periods=self.settings.outlook_sec_history_max_annual_periods,
                    max_annual_source_facts=self.settings.outlook_sec_history_max_annual_source_facts,
                    annual_eps_comparability_evidence=result.evidence,
                    request_diagnostics={**request_diagnostics,
                        "eps_document_evidence_state": state,
                        "eps_document_logical_requests": min(result.logical_documents, 2),
                        "eps_document_http_attempts": result.http_attempts,
                        "eps_document_cache_hits": result.cache_hits,
                        "eps_document_failures": min(result.failures, 2),
                        "eps_document_failure_reasons": result.reasons})
            except Exception:
                snapshot = normalize_companyfacts(companyfacts, submissions, symbol, self.clock(),
                    max_source_facts=self.settings.outlook_sec_history_max_source_facts,
                    max_quarters=self.settings.outlook_sec_history_max_quarters,
                    max_annual_periods=self.settings.outlook_sec_history_max_annual_periods,
                    max_annual_source_facts=self.settings.outlook_sec_history_max_annual_source_facts,
                    request_diagnostics={**request_diagnostics,
                        "eps_document_evidence_state": "loader_error",
                        "eps_document_failures": 1,
                        "eps_document_failure_reasons": ("loader_error",)})
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
