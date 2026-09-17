"""Evidence-only interfaces and integration plans. No network implementations."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models.outlook_evidence import CompanyContext, OutlookEvidence
from app.models.outlook_document import SourceDocument
from app.models.outlook_taxonomy import CategoryKey, SourceType


class OutlookProvider(Protocol):
    name: str
    uses_placeholder_data: bool

    def get_evidence(self, ticker: str) -> list[OutlookEvidence]: ...


class OutlookInterpreter(Protocol):
    def interpret(self, ticker: str, documents: list[SourceDocument],
                  company_context: CompanyContext) -> list[OutlookEvidence]: ...


class NewsSourceProvider(Protocol):
    """Discovery only. No implementation or runtime news dependency in Phase 3B."""
    def get_ticker_news(self, ticker: str, since: datetime) -> list[SourceDocument]: ...
    def get_industry_news(self, industry: str, since: datetime) -> list[SourceDocument]: ...


class PlaceholderOutlookProvider:
    name = "internal_placeholder"
    uses_placeholder_data = True

    def get_evidence(self, ticker: str) -> list[OutlookEvidence]:
        return []


class CompanyContextResolver(Protocol):
    def resolve(self, ticker: str) -> CompanyContext: ...


class EvidenceStore(Protocol):
    """Future persistence boundary; adapters must preserve provenance and support replay."""
    def upsert(self, evidence: list[OutlookEvidence]) -> None: ...
    def for_ticker(self, ticker: str, *, as_of: datetime) -> list[OutlookEvidence]: ...


@dataclass(frozen=True)
class FutureProviderSpec:
    name: str
    categories: tuple[CategoryKey, ...]
    source_type: SourceType
    authority: str
    inputs: tuple[str, ...]


# Planning metadata only. Authority does not set impact, confidence, or materiality.
SEC_SPEC = FutureProviderSpec("sec", ("company", "earnings"), SourceType.REGULATORY_FILING,
    "high", ("8-K material events", "10-Q filing context", "10-K filing context"))
ECONOMIC_SPEC = FutureProviderSpec("economic", ("economic",), SourceType.ECONOMIC_DATA,
    "high", ("policy rate", "inflation", "unemployment", "payrolls", "GDP", "consumer spending", "Treasury curve"))
MARKET_SPEC = FutureProviderSpec("market", ("market",), SourceType.MARKET_DATA,
    "structured", ("broad index history", "technology index history", "volatility regime", "breadth"))
