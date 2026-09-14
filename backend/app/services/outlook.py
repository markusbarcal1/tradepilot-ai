"""Outlook orchestration and aggregation, independent of external provider details."""
import logging
from typing import Protocol

from app.models.outlook import (
    CATEGORY_TITLES, CategoryKey, OutlookCategory, OutlookMetadata, OutlookResponse,
)

logger = logging.getLogger(__name__)


class OutlookProvider(Protocol):
    name: str
    uses_placeholder_data: bool

    def get_categories(self, ticker: str) -> dict[CategoryKey, OutlookCategory]: ...


class PlaceholderOutlookProvider:
    name = "internal_placeholder"
    uses_placeholder_data = True

    def get_categories(self, ticker: str) -> dict[CategoryKey, OutlookCategory]:
        return {key: OutlookCategory(
            status="insufficient_data",
            summary="External Outlook intelligence has not been connected. No assessment is available.",
        ) for key in CATEGORY_TITLES}


DEFAULT_PROVIDER = PlaceholderOutlookProvider()


def aggregate_outlook(ticker: str, categories: dict[CategoryKey, OutlookCategory],
                      metadata: OutlookMetadata) -> OutlookResponse:
    complete = {key: categories.get(key, OutlookCategory()) for key in CATEGORY_TITLES}
    values = [category.value for category in complete.values() if category.status == "available"]
    relevant = [category for category in complete.values() if category.status != "not_material"]
    if metadata.uses_placeholder_data:
        status, value = "placeholder", None
        summary = "Preview only: external Outlook intelligence is not connected. No company assessment is available."
    elif values:
        status = "available" if len(values) == len(relevant) else "partial"
        value = sum(values) / len(values)
        summary = f"Based on {len(values)} available categories. External context, not a trading recommendation."
    else:
        status = "error" if any(category.status == "error" for category in relevant) else "unavailable"
        value = None
        summary = "Insufficient evidence for an overall Outlook assessment."
    return OutlookResponse(ticker=ticker, status=status, value=value, summary=summary,
                           categories=complete, metadata=metadata)


def analyze_outlook(ticker: str, provider: OutlookProvider | None = None) -> OutlookResponse:
    provider = provider if provider is not None else DEFAULT_PROVIDER
    metadata = OutlookMetadata(provider=provider.name, uses_placeholder_data=provider.uses_placeholder_data)
    try:
        supplied = provider.get_categories(ticker.strip().upper())
        # Validate provider output at the boundary; never leak provider errors to clients.
        categories = {key: OutlookCategory.model_validate(value) for key, value in supplied.items()
                      if key in CATEGORY_TITLES}
    except Exception:
        logger.warning("Outlook provider failed", exc_info=True)
        categories = {key: OutlookCategory(status="error", summary="Outlook data is temporarily unavailable.")
                      for key in CATEGORY_TITLES}
        return OutlookResponse(ticker=ticker.strip().upper(), status="error",
                               summary="Outlook data is temporarily unavailable.",
                               categories=categories, metadata=metadata)
    return aggregate_outlook(ticker.strip().upper(), categories, metadata)
