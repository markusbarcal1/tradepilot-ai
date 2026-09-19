"""Outlook orchestration and aggregation, independent of external provider details."""
import logging
from datetime import datetime, timezone

from app.models.outlook import (
    CATEGORY_TITLES, CategoryKey, OutlookCategory, OutlookMetadata, OutlookResponse,
)

from app.models.outlook_evidence import OutlookEvidence
from app.models.outlook_event import EventIntelligence
from app.services.outlook_evidence import assess_evidence
from app.services.outlook_policy import DEFAULT_EVIDENCE_POLICY
from app.services.outlook_providers import OutlookProvider, PlaceholderOutlookProvider
from app.services.outlook_structured import configured_providers

logger = logging.getLogger(__name__)


DEFAULT_PROVIDER = PlaceholderOutlookProvider()


def aggregate_outlook(ticker: str, categories: dict[CategoryKey, OutlookCategory],
                      metadata: OutlookMetadata, *, policy=DEFAULT_EVIDENCE_POLICY) -> OutlookResponse:
    complete = {key: categories.get(key, OutlookCategory()) for key in CATEGORY_TITLES}
    supported = [category for category in complete.values()
                 if category.status == "available" and (category.confidence is None
                     or category.confidence >= policy.minimum_confidence)
                 and (category.evidence_count is None
                     or category.evidence_count >= policy.minimum_events)]
    values = [category.value for category in supported]
    relevant = [category for category in complete.values() if category.status != "not_material"]
    if metadata.uses_placeholder_data:
        status, value = "placeholder", None
        summary = "Preview only: external Outlook intelligence is not connected. No company assessment is available."
    elif values:
        status = "available" if len(values) == len(relevant) else "partial"
        weights = [category.confidence if category.confidence is not None else 1.0 for category in supported]
        value = sum(category.value * weight for category, weight in zip(supported, weights)) / sum(weights)
        summary = f"Based on {len(values)} available categories. External context, not a trading recommendation."
    else:
        status = "error" if any(category.status == "error" for category in relevant) else "unavailable"
        value = None
        summary = "Insufficient evidence for an overall Outlook assessment."
    return OutlookResponse(ticker=ticker, status=status, value=value, summary=summary,
                           categories=complete, metadata=metadata)


def assess_providers(ticker: str, providers: list[OutlookProvider], *, now: datetime | None = None, policy=DEFAULT_EVIDENCE_POLICY) -> OutlookResponse:
    """Isolate failures and configuration by each provider's declared category coverage."""
    ticker = ticker.strip().upper()
    evidence, failed, active = [], set(), set()
    statuses = {}
    attempted = []
    intelligence = EventIntelligence()
    event_provenance = []
    event_snapshots = []
    for provider in providers:
        if getattr(provider, "event_intelligence_provider", False):
            try:
                snapshot = provider.inspect(ticker)
                current = EventIntelligence.model_validate(snapshot["intelligence"])
                observations = [OutlookEvidence.model_validate(item) for item in snapshot["evidence"]]
                if any(item.scoring_eligible or item.ticker != ticker or item.raw_provider != provider.name for item in observations):
                    raise ValueError("Event relevance must not introduce directional evidence")
                event_snapshots.append(current)
                event_provenance.extend(observations)
                statuses[provider.name] = current.status
            except Exception as error:
                logger.warning("outlook_event_provider_failed kind=%s", type(error).__name__)
                event_snapshots.append(EventIntelligence(status="temporarily_unavailable"))
                statuses[provider.name] = "error"
            continue
        coverage = set(getattr(provider, "categories", CATEGORY_TITLES))
        reason = getattr(provider, "unavailable_reason", None)
        if reason:
            statuses[provider.name] = reason
            continue
        attempted.append(provider)
        active.update(coverage)
        try:
            supplied = provider.get_evidence(ticker)
            if not isinstance(supplied, list):
                raise ValueError("Providers must return an evidence list")
            validated = [OutlookEvidence.model_validate(item) for item in supplied]
            if any(item.raw_provider != provider.name or item.ticker != ticker or item.category not in coverage for item in validated):
                raise ValueError("Provider identity, category or ticker does not match")
            evidence.extend(validated)
            statuses[provider.name] = "placeholder" if provider.uses_placeholder_data else "available" if validated else "no_evidence"
        except Exception as error:
            # Do not log exception text/tracebacks: HTTP errors may include credential-bearing URLs.
            logger.warning("outlook_provider_failed provider=%s kind=%s", provider.name, type(error).__name__)
            failed.update(coverage)
            statuses[provider.name] = "error"
    from app.services.outlook_events import merge_intelligence
    intelligence = merge_intelligence(event_snapshots)
    placeholder = not attempted or any(provider.uses_placeholder_data for provider in attempted)
    metadata = OutlookMetadata(provider=",".join(provider.name for provider in providers) or "none",
                               uses_placeholder_data=placeholder, provider_status=statuses)
    if placeholder:
        categories = {key: OutlookCategory(status="insufficient_data",
            summary="External Outlook intelligence has not been connected. No assessment is available.",
            evidence_count=0) for key in CATEGORY_TITLES}
    else:
        # Use completion time for live fetches; explicit time retains deterministic fixture/replay behavior.
        categories, _ = assess_evidence(ticker, evidence, now=now or datetime.now(timezone.utc), policy=policy)
        for key, category in list(categories.items()):
            if category.evidence:
                continue
            if key in failed:
                categories[key] = OutlookCategory(status="error", evidence_count=0,
                    summary="Structured evidence is temporarily unavailable.")
            elif key not in active:
                categories[key] = OutlookCategory(status="unavailable", evidence_count=0,
                    summary="This category's evidence provider is not connected or configured.")
    # Append non-scoring observations after assessment: event relevance cannot alter
    # any category's label, availability, support count, confidence, or error state.
    for key, category in list(categories.items()):
        extra = [item for item in event_provenance if item.category == key]
        if extra:
            categories[key] = category.model_copy(update={"evidence": [*category.evidence, *extra]})
    if attempted and all(statuses[provider.name] == "error" for provider in attempted):
        return OutlookResponse(ticker=ticker, status="error", categories=categories,
                               summary="Outlook data is temporarily unavailable.", metadata=metadata, event_intelligence=intelligence)
    return aggregate_outlook(ticker, categories, metadata, policy=policy).model_copy(update={"event_intelligence": intelligence})


def analyze_outlook(ticker: str, provider: OutlookProvider | None = None, *, now: datetime | None = None) -> OutlookResponse:
    return assess_providers(ticker, [provider] if provider is not None else configured_providers(), now=now)
