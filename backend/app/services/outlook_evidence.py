"""Pure evidence preparation, event clustering, and category assessment."""
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from math import fsum
import re
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.models.outlook import CLASSIFICATIONS, OutlookCategory, OutlookFactor
from app.models.outlook_evidence import OutlookEvidence
from app.models.outlook_taxonomy import CATEGORY_TITLES
from app.services.outlook_policy import DEFAULT_EVIDENCE_POLICY, EvidencePolicy
from app.services.outlook_factors import (FactorAssessment, release_identity, assess_factors,
                                         event_values, semantic_key, factor_identity)


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(str(url))
    query = sorted((key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
                   if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"})
    host = (parts.hostname or "").lower()
    if parts.port and parts.port not in (80, 443):
        host += f":{parts.port}"
    return urlunsplit(("https", host, parts.path.rstrip("/") or "/", urlencode(query), ""))


def headline_similarity(first: str, second: str) -> float:
    normalize = lambda value: " ".join(re.findall(r"\w+", value.casefold()))
    return SequenceMatcher(None, normalize(first), normalize(second), autojunk=False).ratio()


def same_event(first: OutlookEvidence, second: OutlookEvidence, policy: EvidencePolicy,
               similarity: Callable[[str, str], float]) -> bool:
    if (first.ticker, first.category) != (second.ticker, second.category):
        return False
    # Metric observations in one results release are not independent corporate events.
    release = first.source_details.get("earnings_release_id")
    if (first.category == "earnings" and release and release == second.source_details.get("earnings_release_id")
            and first.event_type in ("earnings_result", "margin_change")
            and second.event_type in ("earnings_result", "margin_change")):
        return True
    if first.event_type != second.event_type:
        return False
    if first.raw_provider == second.raw_provider and (
        first.id == second.id or (first.raw_provider_id and first.raw_provider_id == second.raw_provider_id)
    ):
        return True
    if abs((first.published_at - second.published_at).total_seconds()) > policy.duplicate_window_hours * 3600:
        return False
    first_url, second_url = normalize_url(first.source_url), normalize_url(second.source_url)
    return bool(first_url and first_url == second_url) or similarity(first.title, second.title) >= policy.headline_similarity


def cluster_evidence(evidence: list[OutlookEvidence], policy=DEFAULT_EVIDENCE_POLICY,
                     similarity=headline_similarity) -> list[tuple[OutlookEvidence, ...]]:
    # Stable order; merge linked reports while bounding fuzzy chains by publication span.
    ordered = sorted(evidence, key=lambda item: (item.published_at, item.raw_provider, item.id, item.model_dump_json()))
    clusters: list[list[OutlookEvidence]] = []
    for item in ordered:
        merged = [item]
        remaining = []
        for cluster in clusters:
            linked = any(same_event(item, member, policy, similarity) for member in cluster)
            combined = [*cluster, *merged]
            span = (max(member.published_at for member in combined) -
                    min(member.published_at for member in combined)).total_seconds()
            same_provider_event = all(member.raw_provider == item.raw_provider and
                (member.id == item.id or (item.raw_provider_id and member.raw_provider_id == item.raw_provider_id))
                for member in combined)
            if linked and (span <= policy.duplicate_window_hours * 3600 or same_provider_event):
                merged = combined
            else:
                remaining.append(cluster)
        remaining.append(sorted(merged, key=lambda member: (member.published_at, member.raw_provider, member.id, member.model_dump_json())))
        clusters = remaining
    return sorted((tuple(cluster) for cluster in clusters), key=lambda cluster: (cluster[0].published_at, cluster[0].raw_provider, cluster[0].id))


def freshness(evidence: OutlookEvidence, now: datetime, policy=DEFAULT_EVIDENCE_POLICY) -> float:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Assessment time must be timezone-aware")
    if evidence.published_at > now or evidence.observed_at > now:
        return 0.0
    if evidence.expires_at is not None and now >= evidence.expires_at:
        return 0.0
    age = (now - evidence.published_at).total_seconds() / 86400
    rule = policy.event_freshness.get(evidence.event_type, policy.category_freshness[evidence.category])
    return 0.0 if age >= rule.max_age_days else 2 ** (-age / rule.half_life_days)


@dataclass(frozen=True)
class EvidenceContribution:
    evidence: tuple[OutlookEvidence, ...]
    representative: OutlookEvidence
    freshness: float
    weight: float
    contribution: float
    exclusion: str | None
    factors: tuple[FactorAssessment, ...] = ()
    event_confidence: float | None = None

    @property
    def confidence_mass(self):
        return (self.weight / self.event_confidence if self.event_confidence is not None
                else self.representative.materiality * self.freshness)


def weigh_cluster(cluster: tuple[OutlookEvidence, ...], now: datetime,
                 policy=DEFAULT_EVIDENCE_POLICY) -> EvidenceContribution:
    if any(release_identity(r) for r in cluster) and any(factor_identity(r) for r in cluster):
        factors = assess_factors(cluster, now, policy, freshness)
        weight, contribution, confidence = event_values(factors)
        supported = [f for f in factors if f.exclusion is None]
        chosen = min((f.representative for f in supported or factors), key=semantic_key)
        reasons = {f.exclusion for f in factors}
        reason = None if supported else next(iter(reasons)) if len(reasons) == 1 else "no_eligible_factors"
        return EvidenceContribution(cluster, chosen, min(f.freshness for f in supported or factors),
                                    weight, contribution, reason, factors, confidence)
    # Secondary reports cannot override (or suppress by disagreement) explicit primary evidence.
    primary = tuple(item for item in cluster if item.source_quality == "primary_authoritative")
    authoritative = primary or cluster
    representative = min(authoritative, key=lambda item: (-item.confidence, item.published_at, item.raw_provider, item.id))
    # Syndication cannot refresh an event's age or extend its earliest expiration.
    age_weight = min(freshness(item, now, policy) for item in authoritative)
    reason = None
    signs = {1 if item.impact > 0 else -1 if item.impact < 0 else 0 for item in authoritative}
    if not representative.scoring_eligible:
        reason = "provenance_only"
    elif age_weight == 0:
        reason = "expired_or_not_yet_observed"
    elif len(signs) > 1:
        reason = "conflicting_duplicate_interpretations"
    elif representative.materiality < policy.minimum_materiality:
        reason = "not_material" if representative.materiality == 0 else "low_materiality"
    elif representative.category == "geopolitical" and not representative.exposure_links:
        reason = "unestablished_exposure"
    elif representative.confidence < policy.minimum_confidence:
        reason = "low_confidence"
    weight = representative.confidence * representative.materiality * age_weight if reason is None else 0.0
    return EvidenceContribution(cluster, representative, age_weight, weight,
                                int(representative.impact) * weight, reason)


def availability_failures(count: int, weight: float, policy=DEFAULT_EVIDENCE_POLICY) -> tuple[str, ...]:
    """The existing category support gate, shared with operator diagnostics."""
    return tuple(reason for failed, reason in (
        (count < policy.minimum_events, "insufficient_independent_events"),
        (weight < policy.minimum_weight, "support_below_threshold"),
    ) if failed)


def assess_evidence(ticker: str, evidence: list[OutlookEvidence], *, now: datetime,
                    policy=DEFAULT_EVIDENCE_POLICY, similarity=headline_similarity) -> tuple[dict, list[EvidenceContribution]]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Assessment time must be timezone-aware")
    ticker = ticker.strip().upper()
    # Enforce ticker isolation before clustering or counting any evidence.
    # Future observations are not part of an as-of assessment or its provenance.
    # In particular, a later duplicate must not suppress an earlier valid event.
    matching = [item for item in evidence if item.ticker == ticker
                and item.published_at <= now and item.observed_at <= now]
    contributions = [weigh_cluster(cluster, now, policy)
                     for cluster in cluster_evidence(matching, policy, similarity)]
    categories = {}
    for key in CATEGORY_TITLES:
        items = [item for item in contributions if item.representative.category == key]
        eligible = [item for item in items if item.exclusion is None]
        provenance = [evidence for item in items for evidence in item.evidence]
        count = len(eligible)
        weight = fsum(item.weight for item in eligible)
        confidence = (weight / fsum(item.confidence_mass for item in eligible)) if eligible else None
        common = dict(evidence_count=count, confidence=confidence, evidence=provenance)
        if items and all(item.exclusion == "not_material" for item in items):
            categories[key] = OutlookCategory(status="not_material", summary="Reviewed evidence has no material company exposure.", **common)
            continue
        if availability_failures(count, weight, policy):
            categories[key] = OutlookCategory(status="insufficient_data",
                summary=f"Insufficient independent evidence: {count} qualifying events.", **common)
            continue
        # Mean contributions retain attenuation by confidence, materiality and age.
        value = fsum(item.contribution for item in eligible) / count
        magnitude = (2 if abs(value) >= policy.strong_threshold and count >= policy.strong_minimum_events
                     else 1 if abs(value) >= policy.positive_threshold else 0)
        classification = magnitude if value >= 0 else -magnitude
        factors = []
        for item in eligible:
            for fact in item.factors or (item,):
                if fact.exclusion is None:
                    factors.append(OutlookFactor(title=fact.representative.title,
                        impact=CLASSIFICATIONS[int(fact.representative.impact)], description=fact.representative.summary,
                        evidence_ids=list(dict.fromkeys(source.id for source in fact.evidence))))
        categories[key] = OutlookCategory(status="available", value=classification,
            summary=f"{count} independent events support this assessment; {sum(item.contribution > 0 for item in eligible)} positive and {sum(item.contribution < 0 for item in eligible)} negative contributions.",
            factors=factors, **common)
    return categories, contributions
