"""Narrow SEC filing-index normalizer; never parses financial content."""
from __future__ import annotations

from dataclasses import dataclass
import re


INDEX_POLICY_VERSION = "sec-index-json-ex99-earnings-1"
INDEX_COUNT_LIMIT = 512
SAFE_DOCUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
EX99 = re.compile(r"^EX-99(?:\.(\d+))?$", re.I)
EARNINGS_DESCRIPTION = re.compile(
    r"\b(?:earnings|financial\s+results|quarterly\s+results|press\s+release|results\s+release)\b", re.I)


@dataclass(frozen=True)
class IndexExhibitResult:
    state: str
    reason: str
    documents: tuple[str, ...]
    diagnostics: dict


def normalize_exhibit_type(value):
    match = EX99.fullmatch(str(value or "").strip())
    if not match:
        return None
    suffix = match.group(1)
    return "EX-99" if suffix is None else f"EX-99.{int(suffix)}"


def discover_index_earnings_exhibits(payload):
    items = payload.get("directory", {}).get("item", []) if isinstance(payload, dict) else []
    items = items if isinstance(items, list) else []
    raw = {"document_entries_examined": len(items), "ex99_family_entries_examined": 0,
        "entries_rejected_by_unsafe_identity": 0, "entries_rejected_by_exhibit_type": 0,
        "entries_rejected_by_description_semantics": 0, "distinct_eligible_earnings_exhibits": 0,
        "ambiguous_eligible_exhibits": 0}
    eligible = {}
    for item in items:
        if not isinstance(item, dict):
            raw["entries_rejected_by_exhibit_type"] += 1
            continue
        document = str(item.get("name") or "")
        if not SAFE_DOCUMENT.fullmatch(document):
            raw["entries_rejected_by_unsafe_identity"] += 1
            continue
        normalized_type = normalize_exhibit_type(item.get("type"))
        if normalized_type is None:
            raw["entries_rejected_by_exhibit_type"] += 1
            continue
        raw["ex99_family_entries_examined"] += 1
        description = str(item.get("description") or "")[:512]
        if not EARNINGS_DESCRIPTION.search(description):
            raw["entries_rejected_by_description_semantics"] += 1
            continue
        eligible[(document, normalized_type)] = document
    documents = tuple(sorted(eligible.values()))
    raw["distinct_eligible_earnings_exhibits"] = len(documents)
    raw["ambiguous_eligible_exhibits"] = len(documents) if len(documents) > 1 else 0
    capped = any(value > INDEX_COUNT_LIMIT for value in raw.values())
    diagnostics = {"index_policy_version": INDEX_POLICY_VERSION,
        "count_semantics": "sequential_first_failure", "count_limit": INDEX_COUNT_LIMIT,
        "counts_capped": capped,
        **{key: min(value, INDEX_COUNT_LIMIT) for key, value in raw.items()}}
    if not documents:
        return IndexExhibitResult("unavailable", "no_eligible_index_exhibit", (), diagnostics)
    if len(documents) > 1:
        return IndexExhibitResult("ambiguous", "multiple_eligible_index_exhibits", documents,
            diagnostics)
    return IndexExhibitResult("resolved", "single_eligible_index_exhibit", documents, diagnostics)
