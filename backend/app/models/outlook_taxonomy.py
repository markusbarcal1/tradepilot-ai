"""Vendor-independent Outlook vocabulary."""
from enum import Enum, IntEnum
from typing import Literal

CategoryKey = Literal["company", "earnings", "industry", "economic", "market", "geopolitical"]
CATEGORY_TITLES = {
    "company": "Company Outlook", "earnings": "Earnings Outlook",
    "industry": "Industry Outlook", "economic": "Economic Outlook",
    "market": "Market Outlook", "geopolitical": "Geopolitical Outlook",
}
EVENT_TYPES = {
    "company": ("management_change", "acquisition", "divestiture", "partnership", "product_launch",
                "contract_award", "legal_action", "regulatory_action", "cybersecurity_event",
                "restructuring", "buyback", "capital_raise", "operational_update", "corporate_other",
                "material_impairment"),
    "earnings": ("earnings_result", "earnings_upcoming", "guidance_raise", "guidance_cut",
                 "estimate_revision_up", "estimate_revision_down", "revenue_surprise",
                 "earnings_surprise", "margin_change", "earnings_other", "guidance_withdrawal"),
    "industry": ("industry_demand", "supply_change", "competitor_event", "regulatory_industry_change",
                 "commodity_input_change", "structural_trend", "industry_other"),
    "economic": ("interest_rates", "inflation", "employment", "gdp_growth", "consumer_spending",
                 "monetary_policy", "fiscal_policy", "economic_other"),
    "market": ("broad_market_trend", "volatility", "market_breadth", "liquidity", "risk_sentiment", "market_other"),
    "geopolitical": ("conflict", "sanctions", "trade_restriction", "tariff", "political_instability",
                     "supply_chain_disruption", "geopolitical_other"),
}
EventType = Enum("EventType", {name.upper(): name for names in EVENT_TYPES.values() for name in names}, type=str)


class EvidenceImpact(IntEnum):
    STRONGLY_NEGATIVE = -2
    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1
    STRONGLY_POSITIVE = 2


class SourceType(str, Enum):
    REGULATORY_FILING = "regulatory_filing"
    COMPANY_RELEASE = "company_release"
    EARNINGS_DATA = "earnings_data"
    ANALYST_ESTIMATE = "analyst_estimate"
    ECONOMIC_DATA = "economic_data"
    MARKET_DATA = "market_data"
    FINANCIAL_NEWS = "financial_news"
    GOVERNMENT_SOURCE = "government_source"
    GEOPOLITICAL_NEWS = "geopolitical_news"
