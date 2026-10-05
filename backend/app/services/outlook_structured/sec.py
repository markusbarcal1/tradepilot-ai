"""SEC observations and bounded primary documents through the shared transport."""
from datetime import datetime, timedelta, timezone
import logging
import re
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.models.outlook_evidence import CompanyContext, OutlookEvidence
from app.models.outlook_document import SourceDocument
from app.services.outlook_interpreter import DeterministicOutlookInterpreter, sec_observation_document
from app.services.outlook_reporting import reporting_diagnostics
from .documents import parse_filing, item_text, earnings_exhibit_url, bounded_text
from .policy import (SEC_COMPANY_FAMILY_PRIORITY, SEC_COMPANY_ITEM_FAMILIES,
    SEC_DOCUMENT_ITEMS, SEC_ITEMS, SEC_LOOKBACK_DAYS, SEC_MAX_FILINGS)
from .transport import Cache, JsonClient

LOGGER = logging.getLogger(__name__)


def _is_eight_k(form):
    return form in ("8-K", "8-K/A")


def company_candidate_families(observation):
    """Return controlled candidate families available from SEC item metadata."""
    return tuple(dict.fromkeys(SEC_COMPANY_ITEM_FAMILIES[item]
        for item in observation.source_details.get("items", ())
        if item in SEC_COMPANY_ITEM_FAMILIES))


def _company_rank(observation):
    families = company_candidate_families(observation)
    priority = max((SEC_COMPANY_FAMILY_PRIORITY[family] for family in families), default=0)
    amendment = observation.source_details.get("form") == "8-K/A"
    return (-priority, -observation.published_at.timestamp(), amendment, observation.raw_provider_id)


def select_document_candidates(observations, limit):
    """Bounded, deterministic selection with Company/Earnings fairness."""
    candidates = [item for item in observations if _is_eight_k(item.source_details["form"])
        and set(item.source_details["items"]) & (SEC_DOCUMENT_ITEMS | {"2.02"})]
    company = sorted((item for item in candidates if company_candidate_families(item)), key=_company_rank)
    earnings = sorted((item for item in candidates if "2.02" in item.source_details["items"]),
        key=lambda item: (-item.published_at.timestamp(), item.raw_provider_id))
    selected, reasons = [], {}

    def add(item, reason):
        if item not in selected and len(selected) < limit:
            selected.append(item)
            reasons[item.raw_provider_id] = reason

    if company:
        add(company[0], "company_priority")
    if earnings:
        add(earnings[0], "earnings_priority")

    represented = {family for item in selected for family in company_candidate_families(item)}
    while len(selected) < limit:
        diverse = [item for item in company if item not in selected
                   and set(company_candidate_families(item)) - represented]
        if diverse:
            item = diverse[0]
            add(item, "company_family_diversity")
            represented.update(company_candidate_families(item))
            continue
        remaining = sorted((item for item in candidates if item not in selected),
            key=lambda item: -item.published_at.timestamp())
        if not remaining:
            break
        add(remaining[0], "recency_fill")
    return selected, reasons


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
    categories = ("company", "earnings")
    uses_placeholder_data = False

    def __init__(self, settings, client=None, clock=lambda: datetime.now(timezone.utc), interpreter=None):
        self.settings, self.clock = settings, clock
        self.client = client or JsonClient(settings)
        self.cache = Cache(settings.outlook_failure_cache_ttl)
        self.document_cache = Cache(settings.outlook_failure_cache_ttl)
        self.interpretation_cache = Cache(settings.outlook_failure_cache_ttl)
        self.interpreter = interpreter or DeterministicOutlookInterpreter()
        self.unavailable_reason = ("disabled" if not settings.outlook_sec_enabled else
            "missing_configuration" if not re.search(r"\S+@\S+\.\S+", settings.outlook_sec_user_agent) else None)

    def get_evidence(self, ticker):
        observations = self._observations(ticker)
        documents = [sec_observation_document(item) for item in observations]
        retrieval = {item.raw_provider_id: "metadata_only" if self.settings.outlook_sec_documents_enabled else "disabled"
                     for item in observations}
        diagnostics = {item.raw_provider_id: {"selected": False, "selection_reason": "not_candidate",
                       "company_candidate_families": list(company_candidate_families(item)),
                       "primary_status": "not_attempted", "exhibit_status": "not_attempted",
                       "exhibit_url": None} for item in observations}
        if self.settings.outlook_sec_documents_enabled:
            selected, reasons = select_document_candidates(
                observations, self.settings.outlook_sec_max_document_filings)
            candidate_ids = {item.raw_provider_id for item in observations
                if _is_eight_k(item.source_details["form"]) and
                set(item.source_details["items"]) & (SEC_DOCUMENT_ITEMS | {"2.02"})}
            for accession in candidate_ids:
                diagnostics[accession]["selection_reason"] = "budget_not_selected"
            for observation in selected:
                diagnostics[observation.raw_provider_id].update(selected=True,
                    selection_reason=reasons[observation.raw_provider_id], primary_status="failed")
                try:
                    fetched = self.document_cache.get(str(observation.source_url),
                        lambda observation=observation: self._filing_documents(observation),
                        self.settings.outlook_sec_cache_ttl)
                    supplied_documents = fetched["documents"]
                    documents.extend(supplied_documents)
                    diagnostics[observation.raw_provider_id].update({key: value for key, value in fetched.items() if key != "documents"})
                    retrieval[observation.raw_provider_id] = "retrieved" if supplied_documents else "no_supported_content"
                except Exception as error:
                    # Filing failure must not discard metadata or other filings.
                    retrieval[observation.raw_provider_id] = "error"
                    LOGGER.warning("outlook_sec_document_failed kind=%s", type(error).__name__)
                    continue
        interpreted = []
        for document in documents:
            try:
                key = (getattr(self.interpreter, "version", "custom"), document.model_dump_json())
                context = CompanyContext(ticker=document.ticker,
                    company_name=document.metadata.get("company_name") or None)
                supplied = self.interpretation_cache.get(key,
                    lambda: self.interpreter.interpret(document.ticker, [document], context),
                    self.settings.outlook_sec_cache_ttl)
                validated = [OutlookEvidence.model_validate(item) for item in supplied]
                if any(item.ticker != document.ticker or item.raw_provider != self.name
                       or item.category not in self.categories for item in validated):
                    continue
                interpreted.extend(validated)
            except Exception as error:
                LOGGER.warning("outlook_sec_interpreter_failed kind=%s", type(error).__name__)
                continue
        result = []
        for observation in observations:
            company = [item for item in interpreted if item.category == "company"
                       and item.raw_provider_id == observation.raw_provider_id]
            result.extend(company or [observation])
        result.extend(item for item in interpreted if item.category != "company")
        for accession, details in diagnostics.items():
            source_documents = [doc for doc in documents if doc.metadata.get("accession") == accession]
            details.update(metadata_documents=sum(not doc.metadata.get("document_kind") for doc in source_documents),
                item_documents=sum(doc.metadata.get("document_kind") in ("earnings_item", "listing_item", "company_item") for doc in source_documents),
                exhibit_documents=sum(doc.metadata.get("document_kind") == "earnings_exhibit" for doc in source_documents),
                interpreted_candidates=sum(item.raw_provider_id == accession for item in interpreted))
            details["reporting_documents"] = reporting_diagnostics(source_documents, now=self.clock())["sources"]
        # Request-local diagnostics travel with provenance, avoiding shared mutable counters.
        return [item.model_copy(update={"source_details": {**item.source_details,
            "sec_diagnostics": diagnostics.get(item.raw_provider_id, {}),
            "document_retrieval": retrieval.get(item.raw_provider_id, "unknown"),
            "company_interpretation": ("supported" if item.category == "company" and item.scoring_eligible
                else "provenance_only" if item.category == "company" else "not_company"),
            "interpretation_reason": ("deterministic_rule_matched" if item.category == "company" and item.scoring_eligible
                else "no_conservative_company_rule_matched" if item.category == "company" else "owned_by_earnings"),
            "source_document_ids": [doc.id for doc in documents
                if doc.metadata.get("accession") == item.raw_provider_id]}}) for item in result]

    def _filing_documents(self, observation):
        original = sec_observation_document(observation)
        url = str(original.source_url)
        result = []
        fetched = {"documents": result, "primary_status": "unsupported_document",
                   "exhibit_status": "not_attempted", "exhibit_url": None}
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:htm|html|txt)", url.rsplit("/", 1)[-1], re.I):
            return fetched
        html = self.client.get_text(url, provider="sec", user_agent=self.settings.outlook_sec_user_agent)
        fetched["primary_status"] = "retrieved"
        parsed = parse_filing(html)
        for item in sorted(set(original.metadata["items"]) & (SEC_DOCUMENT_ITEMS | {"2.02"})):
            if item not in original.metadata["items"]:
                continue
            text = item_text(parsed.text, item)
            if text:
                kind = "earnings_item" if item == "2.02" else "listing_item" if item == "3.01" else "company_item"
                result.append(SourceDocument.model_validate({**original.model_dump(), "id": original.id + ":item:" + item,
                    "observed_at": self.clock(), "extracted_text": text,
                    "metadata": {**original.metadata, "document_kind": kind}}))
        if "2.02" in original.metadata["items"]:
            exhibit = earnings_exhibit_url(url, parsed.links)
            fetched.update(exhibit_status="not_selected", exhibit_url=exhibit)
            if exhibit:
                try:
                    exhibit_html = self.document_cache.get(exhibit, lambda: self.client.get_text(exhibit,
                        provider="sec", user_agent=self.settings.outlook_sec_user_agent), self.settings.outlook_sec_cache_ttl)
                    fetched["exhibit_status"] = "retrieved"
                    exhibit_parsed = parse_filing(exhibit_html)
                    text = exhibit_parsed.text
                    # An EX-99 attachment is not necessarily an earnings release.
                    if re.search(r"(?:financial results|quarter.{0,20}results|earnings release)", text[:2000], re.I):
                        result.append(SourceDocument.model_validate({**original.model_dump(), "id": original.id + ":exhibit",
                            "provider_document_id": exhibit.rsplit("/", 1)[-1], "source_url": exhibit,
                            "tables": exhibit_parsed.tables,
                            "observed_at": self.clock(), "extracted_text": bounded_text(text, 60000), "metadata": {**original.metadata,
                                "document_kind": "earnings_exhibit"}}))
                    else:
                        fetched["exhibit_status"] = "unsupported_content"
                except Exception as error:
                    fetched["exhibit_status"] = "failed"
                    LOGGER.warning("outlook_sec_exhibit_failed kind=%s", type(error).__name__)
                    # Keep successfully retrieved primary item content.
        return fetched

    def _observations(self, ticker):
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
            if form not in ("8-K", "8-K/A", "10-Q", "10-K"):
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
            mappings = [SEC_ITEMS[item] for item in items if item in SEC_ITEMS] if _is_eight_k(form) else []
            event, _, materiality, title = min(mappings, key=lambda item: item[1]) if mappings else (
                "corporate_other", 0, 0.5, f"{form} filing")
            # Metadata-only direction is unknown for acquisitions, appointments, funding and routine filings.
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{quote(field('primaryDocument'), safe='')}"
            results.append(OutlookEvidence(id=f"sec:{ticker}:{accession}", ticker=ticker, category="company",
                event_type=event, title=title, summary=f"SEC {form} filed {field('filingDate')}; items {', '.join(items) or 'not specified'}. " +
                    "Direction is not inferred here; retained for provenance only.",
                source="SEC EDGAR", source_type="regulatory_filing", source_url=url,
                published_at=published, observed_at=fetched, impact=0, confidence=0.95,
                materiality=materiality, materiality_reason="Issuer-specific SEC disclosure.",
                scoring_eligible=False, raw_provider="sec", raw_provider_id=accession,
                source_quality="primary_authoritative",
                source_details={"cik": cik, "accession": accession, "form": form, "company_name": payload.get("name", ""),
                    "filing_date": field("filingDate"), "event_date": field("reportDate"), "items": items}))
            if len(results) >= SEC_MAX_FILINGS:
                break
        return results
