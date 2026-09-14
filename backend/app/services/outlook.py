"""Outlook orchestration and aggregation, independent of external provider details."""
import logging
from datetime import datetime, timezone

from app.models.outlook import (
    CATEGORY_TITLES, CategoryKey, OutlookCategory, OutlookMetadata, OutlookResponse,
)

from app.models.outlook_evidence import OutlookEvidence
from app.services.outlook_evidence import assess_evidence
from app.services.outlook_policy import DEFAULT_EVIDENCE_POLICY
from app.services.outlook_providers import OutlookProvider, PlaceholderOutlookProvider

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


def assess_providers(ticker: str, providers: list[OutlookProvider], *, now: datetime, policy=DEFAULT_EVIDENCE_POLICY) -> OutlookResponse:
    """Fixture/future orchestration: failure of one provider cannot erase another's evidence."""
    ticker = ticker.strip().upper()
    evidence = []
    failed = []
    for provider in providers:
        try:
            supplied = provider.get_evidence(ticker)
            if not isinstance(supplied, list):
                raise ValueError("Providers must return an evidence list")
            validated = [OutlookEvidence.model_validate(item) for item in supplied]
            if any(item.raw_provider != provider.name or item.ticker != ticker for item in validated):
                raise ValueError("Provider identity or ticker does not match requested evidence")
            evidence.extend(validated)
        except Exception:
            logger.warning("Outlook evidence provider failed: %s", provider.name, exc_info=True)
            failed.append(provider.name)
    metadata = OutlookMetadata(provider=",".join(provider.name for provider in providers) or "none",
                               uses_placeholder_data=any(provider.uses_placeholder_data for provider in providers))
    # Placeholder/demo sources must never leak fixture factors into the production card.
    if metadata.uses_placeholder_data:
        categories = {key: OutlookCategory(status="insufficient_data",
            summary="External Outlook intelligence has not been connected. No assessment is available.",
            evidence_count=0) for key in CATEGORY_TITLES}
    else:
        categories, _ = assess_evidence(ticker, evidence, now=now, policy=policy)
        if failed:
            categories = {key: (OutlookCategory(status="error", evidence_count=0,
                summary="Outlook evidence is temporarily unavailable.") if not category.evidence else category)
                for key, category in categories.items()}
    if failed and len(failed) == len(providers):
        return OutlookResponse(ticker=ticker, status="error", categories=categories,
                               summary="Outlook data is temporarily unavailable.", metadata=metadata)
    return aggregate_outlook(ticker, categories, metadata, policy=policy)


def analyze_outlook(ticker: str, provider: OutlookProvider | None = None, *, now: datetime | None = None) -> OutlookResponse:
    # No runtime provider registry or enable flag: HTTP remains wired to the empty placeholder.
    return assess_providers(ticker, [provider if provider is not None else DEFAULT_PROVIDER],
                            now=now if now is not None else datetime.now(timezone.utc))
