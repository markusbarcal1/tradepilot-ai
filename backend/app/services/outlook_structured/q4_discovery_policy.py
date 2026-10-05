"""Versioned, pure metadata policy for future Q4 earnings 8-K diagnostics.

This module performs no I/O and is not registered with production research or
Analyze. The full Q4 certification runner intentionally retains its legacy exact
report-date policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


DISCOVERY_POLICY_VERSION = "bounded-filing-window-item-202-1"
DISCOVERY_COUNT_LIMIT = 4096
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SAFE_DOCUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


@dataclass(frozen=True)
class DiscoveryResult:
    state: str
    reason: str
    candidates: tuple[dict, ...]
    diagnostics: dict


def _iso_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _has_item_202(value):
    return "2.02" in {item.strip() for item in str(value or "").split(",")}


def _bounded(raw, *, boundary_status):
    saturated = any(isinstance(value, int) and value > DISCOVERY_COUNT_LIMIT
        for value in raw.values())
    counts = {key: min(value, DISCOVERY_COUNT_LIMIT) if isinstance(value, int) else value
        for key, value in raw.items()}
    return {"policy_version": DISCOVERY_POLICY_VERSION,
        "count_semantics": "sequential_first_failure", "count_limit": DISCOVERY_COUNT_LIMIT,
        "counts_capped": saturated, "upper_boundary_status": boundary_status, **counts}


def discover_q4_earnings_8k(rows, *, period_end, approved_ten_k_accession):
    """Associate candidates with a verified Q4 identity, failing closed on ambiguity."""
    rows = tuple(rows)
    raw = {"metadata_rows_examined": len(rows), "approved_10k_rows_examined": 0,
        "approved_10k_accession_matches": 0, "invalid_or_missing_10k_filing_dates": 0,
        "distinct_approved_10k_filing_dates": 0, "rows_rejected_by_form": 0,
        "eight_k_rows_examined": 0, "rows_rejected_by_missing_or_invalid_filing_date": 0,
        "rows_rejected_at_or_before_period_end": 0,
        "rows_rejected_after_approved_10k_boundary": 0,
        "rows_inside_valid_filing_window": 0, "rows_rejected_by_item_202": 0,
        "rows_rejected_by_unsafe_or_missing_accession": 0,
        "rows_rejected_by_unsafe_or_missing_primary_document": 0,
        "exact_duplicate_rows_collapsed": 0, "distinct_qualifying_candidates": 0,
        "ambiguous_qualifying_candidates": 0}
    period = _iso_date(period_end)
    if period is None or not ACCESSION.fullmatch(str(approved_ten_k_accession or "")):
        return DiscoveryResult("unavailable", "invalid_verified_period_identity", (),
            _bounded(raw, boundary_status="invalid_verified_period_identity"))

    annual_dates = set()
    for row in rows:
        if row.get("form") not in ("10-K", "10-K/A"):
            continue
        raw["approved_10k_rows_examined"] += 1
        if row.get("accession") != approved_ten_k_accession:
            continue
        raw["approved_10k_accession_matches"] += 1
        filed = _iso_date(row.get("filing_date"))
        if filed is None:
            raw["invalid_or_missing_10k_filing_dates"] += 1
        else:
            annual_dates.add(filed)
    raw["distinct_approved_10k_filing_dates"] = len(annual_dates)
    if len(annual_dates) != 1 or raw["invalid_or_missing_10k_filing_dates"]:
        return DiscoveryResult("unavailable", "approved_10k_filing_date_unresolved", (),
            _bounded(raw, boundary_status="unresolved"))
    ten_k_date = next(iter(annual_dates))
    if ten_k_date <= period:
        return DiscoveryResult("unavailable", "invalid_approved_10k_boundary", (),
            _bounded(raw, boundary_status="invalid"))

    unique = {}
    for row in rows:
        if row.get("form") not in ("8-K", "8-K/A"):
            raw["rows_rejected_by_form"] += 1
            continue
        raw["eight_k_rows_examined"] += 1
        filed = _iso_date(row.get("filing_date"))
        if filed is None:
            raw["rows_rejected_by_missing_or_invalid_filing_date"] += 1
            continue
        if filed <= period:
            raw["rows_rejected_at_or_before_period_end"] += 1
            continue
        if filed > ten_k_date:
            raw["rows_rejected_after_approved_10k_boundary"] += 1
            continue
        raw["rows_inside_valid_filing_window"] += 1
        if not _has_item_202(row.get("items")):
            raw["rows_rejected_by_item_202"] += 1
            continue
        accession = str(row.get("accession") or "")
        if not ACCESSION.fullmatch(accession):
            raw["rows_rejected_by_unsafe_or_missing_accession"] += 1
            continue
        document = str(row.get("primary_document") or "")
        if not SAFE_DOCUMENT.fullmatch(document):
            raw["rows_rejected_by_unsafe_or_missing_primary_document"] += 1
            continue
        identity = (accession, row.get("form"), filed.isoformat(),
            str(row.get("report_date") or ""), str(row.get("items") or ""), document)
        if identity in unique:
            raw["exact_duplicate_rows_collapsed"] += 1
            continue
        unique[identity] = {"accession": accession, "form": row.get("form"),
            "filing_date": filed.isoformat(), "report_date": str(row.get("report_date") or ""),
            "items": str(row.get("items") or ""), "primary_document": document}

    candidates = tuple(sorted(unique.values(), key=lambda row:
        (row["filing_date"], row["accession"], row["form"], row["primary_document"])))
    raw["distinct_qualifying_candidates"] = len(candidates)
    raw["ambiguous_qualifying_candidates"] = len(candidates) if len(candidates) > 1 else 0
    diagnostics = _bounded(raw, boundary_status="resolved")
    if not candidates:
        return DiscoveryResult("unavailable", "no_plausible_candidate", (), diagnostics)
    if len(candidates) > 1:
        return DiscoveryResult("ambiguous", "multiple_plausible_candidates", candidates, diagnostics)
    return DiscoveryResult("resolved", "single_bounded_item_202_candidate", candidates, diagnostics)


# Compatibility name for Phase 5G fixture-only callers. This is the same explicit
# versioned algorithm, not a fallback to the legacy reportDate policy.
discover_q4_earnings_8k_prototype = discover_q4_earnings_8k
