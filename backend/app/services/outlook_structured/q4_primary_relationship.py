"""Pure adapter for explicit same-accession Exhibit 99 relationships."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .documents import earnings_exhibit_url, parse_filing
from .q4_certification import _document_url


RELATIONSHIP_POLICY_VERSION = "sec-primary-explicit-exhibit99-relationship-1"
SAFE_CIK = re.compile(r"^\d{10}$")
SAFE_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SAFE_DOCUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


@dataclass(frozen=True)
class BoundPrimaryDocument:
    ticker: str
    issuer: str
    cik: str
    accession: str
    form: str
    fiscal_year: int
    period_end: str
    filing_date: str
    primary_url: str
    primary_document: str
    html: str


@dataclass(frozen=True)
class ResolvedExhibitRelationship:
    url: str
    document_id: str
    family: str = "explicit_exhibit99"
    policy_version: str = RELATIONSHIP_POLICY_VERSION


@dataclass(frozen=True)
class RelationshipResult:
    state: str
    reason: str
    relationship_observations: int
    distinct_safe_destinations: int
    duplicate_collapses: int
    ambiguous_destinations: int
    destination: ResolvedExhibitRelationship | None = None


def resolve_primary_exhibit99_relationship(value: BoundPrimaryDocument) -> RelationshipResult:
    if (not isinstance(value, BoundPrimaryDocument) or not SAFE_CIK.fullmatch(value.cik)
            or not SAFE_ACCESSION.fullmatch(value.accession)
            or not SAFE_DOCUMENT.fullmatch(value.primary_document)):
        return RelationshipResult("invalid_input", "unsafe_primary_identity", 0, 0, 0, 0)
    try:
        expected = _document_url(value.cik, value.accession, value.primary_document)
    except Exception:
        return RelationshipResult("invalid_input", "unsafe_primary_identity", 0, 0, 0, 0)
    if value.primary_url != expected:
        return RelationshipResult("invalid_input", "unsafe_primary_identity", 0, 0, 0, 0)
    if not isinstance(value.html, str):
        return RelationshipResult("invalid_input", "unsupported_primary_content", 0, 0, 0, 0)

    parsed = parse_filing(value.html)
    observations = []
    for link in parsed.links:
        destination = earnings_exhibit_url(value.primary_url, (link,))
        if destination:
            observations.append(destination)
    distinct = tuple(dict.fromkeys(observations))
    duplicates = len(observations) - len(distinct)
    if not distinct:
        return RelationshipResult("unavailable", "no_explicit_exhibit_relationship",
            len(observations), 0, duplicates, 0)
    if len(distinct) > 1:
        return RelationshipResult("ambiguous", "multiple_explicit_exhibit_destinations",
            len(observations), len(distinct), duplicates, len(distinct))
    url = distinct[0]
    document = url.rsplit("/", 1)[-1]
    return RelationshipResult("resolved", "explicit_exhibit_relationship_resolved",
        len(observations), 1, duplicates, 0,
        ResolvedExhibitRelationship(url=url, document_id=document))
