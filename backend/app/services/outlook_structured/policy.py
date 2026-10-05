"""Small, provisional structured-input basket and deterministic interpretation policy."""
from dataclasses import dataclass

# Official 8-K item context; accession + canonical event type identifies an event.
SEC_ITEMS = {
    "1.03": ("bankruptcy", -2, 1.0, "Bankruptcy or receivership"),
    "1.05": ("cybersecurity_event", -1, 1.0, "Material cybersecurity incident"),
    "5.02": ("management_change", 0, 0.5, "Principal officer or director change"),
    "2.01": ("acquisition", 0, 0.5, "Acquisition or disposition of assets"),
    "1.01": ("material_agreement", 0, 0.7, "Material definitive agreement"),
    "3.02": ("capital_raise", 0, 0.5, "Unregistered sale of equity securities"),
    "2.05": ("restructuring", 0, 0.5, "Exit or disposal costs"),
    "2.06": ("material_impairment", -1, 0.9, "Material impairment"),
    "3.01": ("regulatory_action", 0, 0.5, "Listing-rule notice or transfer of listing"),
    # Items 3.03 and 5.03 identify a capital-structure filing worth bounded
    # retrieval. They do not, by themselves, establish a split or direction.
    "3.03": ("corporate_other", 0, 0.5, "Material modification to security-holder rights"),
    "5.03": ("corporate_other", 0, 0.5, "Charter or bylaws amendment"),
    "1.02": ("material_agreement_termination", 0, 0.7, "Termination of material agreement"),
    "8.01": ("corporate_other", 0, 0.5, "Other material corporate event"),
}

SEC_DOCUMENT_ITEMS = frozenset(SEC_ITEMS)
SEC_COMPANY_ITEM_FAMILIES = {
    "1.01": "agreement", "1.02": "agreement", "1.03": "bankruptcy",
    "1.05": "cybersecurity", "2.01": "acquisition_disposition",
    "2.05": "restructuring", "2.06": "impairment", "3.01": "listing_status",
    "3.02": "capital_raise", "3.03": "capital_structure", "5.02": "management_change",
    "5.03": "capital_structure", "8.01": "other_company_event",
}
# Metadata-only retrieval priority. This chooses what to inspect; it never
# creates normalized evidence or supplies directionality.
SEC_COMPANY_FAMILY_PRIORITY = {
    "bankruptcy": 100, "cybersecurity": 95, "impairment": 90,
    "listing_status": 85, "capital_structure": 80, "acquisition_disposition": 75,
    "capital_raise": 70, "restructuring": 65, "management_change": 60,
    "agreement": 55, "other_company_event": 10,
}
SEC_LOOKBACK_DAYS = 180
SEC_MAX_FILINGS = 200


@dataclass(frozen=True)
class MacroSeries:
    id: str
    title: str
    event: str
    comparison: int
    threshold: float
    higher_impact: int
    max_age_days: int
    method: str = "change"


MACRO_SERIES = (
    MacroSeries("FEDFUNDS", "Federal Funds Effective Rate", "interest_rates", 3, 0.25, -1, 75),
    MacroSeries("CPIAUCSL", "Consumer Price Index", "inflation", 3, 0.2, -1, 75, "yoy_change"),
    MacroSeries("UNRATE", "Unemployment Rate", "employment", 3, 0.2, -1, 75),
    MacroSeries("A191RL1Q225SBEA", "Real GDP growth (annualized)", "gdp_growth", 1, 0.5, 1, 180),
    MacroSeries("GS10", "10-Year Treasury Yield", "interest_rates", 3, 0.25, -1, 75),
)
MACRO_CONFIDENCE = 0.9
MACRO_MATERIALITY = 0.6
MARKET_SYMBOLS = ("SPY", "QQQ", "^VIX")
MARKET_SMA_WINDOW = 50
MARKET_SLOPE_BARS = 5
MARKET_STALE_DAYS = 5
VIX_HIGH = 25
VIX_LOW = 15
MARKET_CONFIDENCE = 0.95
MARKET_MATERIALITY = 0.8
