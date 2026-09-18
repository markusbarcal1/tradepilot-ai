"""Narrow, factual export-control interpretation and explicit industry exposure."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from app.models.outlook_document import SourceDocument
from app.models.outlook_evidence import CompanyContext, ExposureLink, OutlookEvidence


VERSION = "geopolitical-export-controls-v1"
# Exact metadata industry relationships, never a sector or ticker heuristic.
EXPOSURES = {
    "advanced_computing": frozenset({"semiconductors"}),
    "semiconductor_manufacturing": frozenset({"semiconductor equipment & materials"}),
}
PRODUCTS = {
    "advanced_computing": "advanced computing",
    "semiconductor_manufacturing": "semiconductor manufacturing",
}
COUNTRIES = ("China", "Macau", "Russia", "Iran", "North Korea", "Belarus")


@dataclass(frozen=True)
class GeopoliticalEvent:
    document: SourceDocument
    family: str
    effective_at: datetime | None
    expires_at: datetime | None
    countries: tuple[str, ...]
    change: str
    reason: str | None
    action_ids: tuple[str, ...]


@dataclass(frozen=True)
class ExposureAssessment:
    matched: bool
    reason: str
    link: ExposureLink | None = None


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc) if value else None


def normalize_event(document, family_hint=None):
    """Only explicit product scope and bounded official abstract constructions qualify."""
    title = document.title.casefold()
    families = [key for key, text in PRODUCTS.items() if text in title]
    if not families and family_hint in PRODUCTS:
        families = [family_hint]
    if len(families) != 1:
        return None
    family = families[0]
    meta = document.metadata
    text = " ".join((document.description or "").split())
    lower = text.casefold()
    countries = tuple(name for name in COUNTRIES
                      if re.search(r"\b" + re.escape(name) + r"\b", text, re.I))
    reason, change = None, "ambiguous"
    # Case-by-case review is conditional licensing relief, not unrestricted exports.
    first_sentence = re.split(r"[.!?]", lower)[0]
    relief = (family == "advanced_computing"
              and re.match(r"^(?:the )?(?:bis|bureau of industry and security \(bis\)) is revising its license review policy for exports of certain semiconductors", first_sentence)
              and "changing it from a presumption of denial to a case-by-case review" in first_sentence
              and not re.search(r"\b(?:not|no|may|might|could|would|proposed|previously|if)\b", first_sentence))
    # Require a present-tense agency assertion and product in the SAME sentence.
    negative_sentences = [sentence.strip() for sentence in re.split(r"[.!?]", lower)
        if re.match(r"^(?:the )?(?:bis|bureau of industry and security \(bis\)) (?:is imposing|imposes|is adding|adds) "
        r"(?:new |additional )?(?:export )?license requirements? (?:on|for) ", sentence)
        and PRODUCTS[family] in sentence
        and not re.search(r"\b(?:not|no|may|might|could|would|proposed|previously|if)\b", sentence)
        ]
    negative = bool(negative_sentences)
    if relief and not negative:
        change = "conditional_licensing_relief"
    elif negative and not relief:
        change = "additional_licensing_requirements"
    else:
        reason = "ambiguous_or_unsupported_policy_change"
    if change != "ambiguous":
        # Destinations must belong to the current action clause, not background history.
        action_text = first_sentence if relief else " ".join(negative_sentences)
        country_pattern = "(?:" + "|".join(re.escape(name.casefold()) for name in COUNTRIES) + ")"
        scopes = re.findall(r"\bto (" + country_pattern + r"(?:\s*(?:,|and|or)\s*" + country_pattern + r")*)", action_text)
        countries = tuple(name for name in COUNTRIES if re.search(r"\b" + re.escape(name.casefold()) + r"\b", " ".join(scopes)))
    try:
        effective = parse_date(meta.get("effective_on"))
    except (ValueError, TypeError):
        effective = None
    # Multiple compliance dates or temporary rules need a dedicated date parser;
    # never pretend the first machine date completely specifies those policies.
    dates = str(meta.get("dates") or "")
    if re.search(r"\b(?:except|until|through|expires|expiration|suspend|suspension)\b", dates, re.I):
        reason = "complex_effective_period"
    if not effective:
        reason = "missing_effective_date"
    if not countries:
        reason = "unresolved_destination_scope"
    if document.source_quality != "primary_authoritative" or document.provider != "geopolitical":
        reason = "unsupported_source"
    if meta.get("type") != "Rule" or not re.fullmatch(r"(?:Interim )?[Ff]inal rule\.?", str(meta.get("action", ""))):
        reason = "not_supported_final_rule"
    if meta.get("correction_of") or "correction" in title:
        reason = "correction_requires_review"
    if re.search(r"\b(?:entity list|listed entities|designated entities|named entities|specific entities|affiliates)\b",
                 title + " " + lower):
        reason = "entity_specific_relationship_not_established"
    return GeopoliticalEvent(document, family, effective,
        document.published_at + timedelta(days=365), countries, change, reason,
        tuple(str(value) for value in (meta.get("regulation_id_numbers") or []) if value))


def resolve_exposure(event, context):
    if not context.industry:
        return ExposureAssessment(False, "missing_industry_classification")
    industry = " ".join(context.industry.casefold().split())
    if industry not in EXPOSURES.get(event.family, ()):
        return ExposureAssessment(False, "no_controlled_product_industry_relationship")
    if context.country != "United States":
        return ExposureAssessment(False, "unsupported_company_jurisdiction")
    reason = (f"{context.ticker} is classified in {context.industry}; this matches the controlled "
              f"{PRODUCTS[event.family]} industry relationship. This establishes industry-level exposure, "
              "not a verified product qualification, customer relationship, or revenue percentage.")
    return ExposureAssessment(True, reason, ExposureLink(kind="industry", description=reason,
        source_url=f"https://finance.yahoo.com/quote/{context.ticker}/profile/"))


def current_events(events, now):
    """One state per overlapping product/destination action family, not per publication."""
    selected, excluded = [], []
    active = []
    for event in events:
        if event.document.published_at > now or event.document.observed_at > now:
            excluded.append((event, "not_yet_observed"))
        elif event.effective_at and event.effective_at > now:
            excluded.append((event, "future_effective"))
        else:
            active.append(event)
    groups = []
    for event in active:
        joined, remaining = [event], []
        for group in groups:
            if any(e.family == event.family and (not e.countries or not event.countries
                    or set(e.countries) & set(event.countries)
                    or set(e.action_ids) & set(event.action_ids)) for e in group):
                joined.extend(group)
            else:
                remaining.append(group)
        groups = [*remaining, joined]
    for group in groups:
        latest_time = max(e.document.published_at for e in group)
        latest = [e for e in group if e.document.published_at == latest_time]
        unique = {e.document.provider_document_id: e for e in latest}
        versions = {e.document.model_dump_json() for e in latest}
        if len(unique) != 1 or len(versions) != 1:
            excluded.extend((e, "ambiguous_same_day_actions") for e in group)
            continue
        chosen = next(iter(unique.values()))
        selected.append(chosen)
        excluded.extend((e, "superseded_or_duplicate_family_observation") for e in group if e is not chosen)
    return selected, excluded


def interpret_exposure(event, context, now):
    assessment = resolve_exposure(event, context)
    reason = (event.reason or ("future_effective" if event.effective_at and event.effective_at > now else None)
              or ("unsupported_policy_change" if event.change not in {"additional_licensing_requirements", "conditional_licensing_relief"} else None)
              or ("expired_review_window" if event.expires_at and now >= event.expires_at else None)
              or (None if assessment.matched else assessment.reason))
    if reason:
        return None, reason
    impact = -1 if event.change == "additional_licensing_requirements" else 1
    action = ("Additional export licensing requirements create potential restrictions on the matched product group."
              if impact < 0 else "A shift from presumption of denial to case-by-case review creates a conditional export licensing opportunity; approval is not guaranteed.")
    document = event.document
    identity = f"bis:{event.family}:{','.join(sorted(event.countries))}"
    return OutlookEvidence(id=f"geopolitical:{context.ticker}:{document.provider_document_id}",
        ticker=context.ticker, category="geopolitical", event_type="export_control",
        title=f"{', '.join(event.countries)}: {PRODUCTS[event.family]} export licensing",
        summary=f"{action} Destinations: {', '.join(event.countries)}. {assessment.reason}",
        source="Federal Register / Bureau of Industry and Security", source_type="government_source",
        source_url=document.source_url, published_at=document.published_at, observed_at=document.observed_at,
        expires_at=event.expires_at, impact=impact, confidence=.8, materiality=.6,
        materiality_reason="Direct product-to-industry match; company-specific transactions are unverified.",
        exposure_links=(assessment.link,), raw_provider="geopolitical", raw_provider_id=identity,
        source_quality="primary_authoritative",
        source_details={"source_document_id": document.id, "document_number": document.provider_document_id,
            "publication_title": document.title, "effective_at": event.effective_at.isoformat(),
            "review_expires_at": event.expires_at.isoformat(), "countries": list(event.countries),
            "product_group": event.family, "policy_change": event.change, "action_ids": list(event.action_ids),
            "sector": context.sector, "industry": context.industry, "exposure_reason": assessment.reason,
            "classification_source": "Yahoo Finance structured metadata", "interpreter": VERSION,
            "effective_date_text": document.metadata.get("dates")}), None
