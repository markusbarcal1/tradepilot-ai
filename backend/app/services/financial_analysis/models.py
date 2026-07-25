from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FinancialSnapshot:
    ticker: str
    provider: str = "yfinance"
    instrument_type: str | None = None
    sector: str | None = None
    industry: str | None = None
    as_of: str | None = None
    values: dict[str, Any] = field(default_factory=dict)
    annual_free_cash_flow: list[float] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
