from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValuationSnapshot:
    symbol: str
    provider: str = "yfinance"
    instrument_type: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    financial_currency: str | None = None
    as_of: str | None = None
    price_as_of: str | None = None
    price_source: str | None = None
    price_is_fallback: bool = False
    values: dict[str, Any] = field(default_factory=dict)
