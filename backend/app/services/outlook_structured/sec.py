"""SEC submissions metadata only: no filing prose or HTML interpretation."""
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.models.outlook_evidence import OutlookEvidence
from .policy import SEC_ITEMS, SEC_LOOKBACK_DAYS, SEC_MAX_FILINGS
from .transport import Cache, JsonClient


def sec_symbol(symbol):
    return symbol.strip().upper().replace(".", "-")


def ticker_mapping(payload):
    result = {}
    for row in payload.values():
        if isinstance(row, dict) and str(row.get("cik_str", "")).isdigit():
            result[sec_symbol(row.get("ticker", ""))] = str(row["cik_str"]).zfill(10)
    return result


class SecEvidenceProvider:
    name = "sec"
    categories = ("company",)
    uses_placeholder_data = False

    def __init__(self, settings, client=None, clock=lambda: datetime.now(timezone.utc)):
        self.settings, self.clock = settings, clock
        self.client = client or JsonClient(settings)
        self.cache = Cache(settings.outlook_failure_cache_ttl)
        self.unavailable_reason = ("disabled" if not settings.outlook_sec_enabled else
            "missing_configuration" if not re.search(r"\S+@\S+\.\S+", settings.outlook_sec_user_agent) else None)

    def get_evidence(self, ticker):
        ticker = ticker.strip().upper()
        if self.unavailable_reason:
            return []
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,15}", ticker.upper()):
            return []
        def mapping():
            return ticker_mapping(self.client.get("https://www.sec.gov/files/company_tickers.json",
                provider="sec", user_agent=self.settings.outlook_sec_user_agent))
        cik = self.cache.get("mapping", mapping, self.settings.outlook_cik_cache_ttl).get(sec_symbol(ticker))
        if not cik:
            return []
        def submissions():
            payload = self.client.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                provider="sec", user_agent=self.settings.outlook_sec_user_agent)
            return payload, self.clock()
        payload, fetched = self.cache.get(cik, submissions, self.settings.outlook_sec_cache_ttl)
        recent = payload.get("filings", {}).get("recent", {})
        results = []
        for index, form in enumerate(recent.get("form", [])):
            if form not in ("8-K", "10-Q", "10-K"):
                continue
            def field(name):
                values = recent.get(name, [])
                return values[index] if index < len(values) else ""
            accession = field("accessionNumber")
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
                continue
            try:
                published = datetime.fromisoformat(field("acceptanceDateTime").replace("Z", "+00:00"))
                if published.tzinfo is None:
                    published = published.replace(tzinfo=ZoneInfo("America/New_York"))
            except ValueError:
                try:
                    published = datetime.fromisoformat(field("filingDate")).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            if published > fetched or published < self.clock() - timedelta(days=SEC_LOOKBACK_DAYS):
                continue
            items = re.findall(r"\d\.\d{2}", str(field("items")))
            mappings = [SEC_ITEMS[item] for item in items if item in SEC_ITEMS] if form == "8-K" else []
            event, impact, materiality, title = min(mappings, key=lambda item: item[1]) if mappings else (
                "corporate_other", 0, 0.5, f"{form} filing")
            # Metadata-only direction is unknown for acquisitions, appointments, funding and routine filings.
            eligible = impact < 0
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{quote(field('primaryDocument'), safe='')}"
            results.append(OutlookEvidence(id=f"sec:{ticker}:{accession}", ticker=ticker, category="company",
                event_type=event, title=title, summary=f"SEC {form} filed {field('filingDate')}; items {', '.join(items) or 'not specified'}. " +
                    ("Structured disclosure indicates a material adverse event." if eligible else "Direction is not inferred from filing metadata; retained for provenance only."),
                source="SEC EDGAR", source_type="regulatory_filing", source_url=url,
                published_at=published, observed_at=fetched, impact=impact, confidence=0.95,
                materiality=materiality, materiality_reason="Issuer-specific SEC disclosure.",
                scoring_eligible=eligible, raw_provider="sec", raw_provider_id=accession,
                source_details={"cik": cik, "accession": accession, "form": form,
                    "filing_date": field("filingDate"), "event_date": field("reportDate"), "items": items}))
            if len(results) >= SEC_MAX_FILINGS:
                break
        return results
