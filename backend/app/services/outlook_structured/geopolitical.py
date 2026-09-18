"""Shared, bounded Federal Register source -> explicit exposure -> OutlookEvidence."""
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlsplit

from app.models.outlook_document import SourceDocument
from app.models.outlook_evidence import CompanyContext
from app.services.market_data import VALID_TICKER_PATTERN
from app.services.outlook_geopolitical import normalize_event, current_events, interpret_exposure
from .industry import classification
from .transport import Cache, JsonClient, ProviderUnavailable

API_URL = "https://www.federalregister.gov/api/v1/documents.json"
FIELDS = ("title", "abstract", "document_number", "publication_date", "effective_on", "type", "html_url",
          "regulation_id_numbers", "correction_of", "action", "dates", "agencies")
MAX_DOCUMENTS = 100
LOOKBACK_DAYS = 400


class FederalRegisterSource:
    """Source-only adapter; no ticker direction or category aggregation."""
    def __init__(self, settings, client=None, clock=lambda: datetime.now(timezone.utc)):
        self.settings, self.clock = settings, clock
        self.client = client or JsonClient(settings)
        self.cache = Cache(settings.outlook_failure_cache_ttl, capacity=1)

    def get_documents(self):
        return self.cache.get("bis-rules", self._load, self.settings.outlook_geopolitical_cache_ttl)

    def _load(self):
        now = self.clock()
        params = [("conditions[agencies][]", "industry-and-security-bureau"), ("conditions[type][]", "RULE"),
                  ("conditions[publication_date][gte]", (now - timedelta(days=LOOKBACK_DAYS)).date().isoformat()),
                  ("conditions[publication_date][lte]", now.date().isoformat()),
                  ("per_page", MAX_DOCUMENTS), ("order", "newest"), *[("fields[]", f) for f in FIELDS]]
        payload = self.client.get(API_URL, provider="geopolitical", params=params)
        if (not isinstance(payload, dict) or not isinstance(payload.get("results"), list)
                or not isinstance(payload.get("count"), int) or payload["count"] > MAX_DOCUMENTS
                or payload["count"] != len(payload["results"])):
            # Never interpret an incomplete snapshot that might omit a repeal/amendment.
            raise ProviderUnavailable("incomplete_bis_snapshot")
        documents, rejected = [], []
        for row in payload["results"]:
            try:
                identity = str(row["document_number"])
                if not re.fullmatch(r"(?:[A-Z]\d?-)?\d{4}-\d{4,6}", identity):
                    raise ValueError("invalid_identity")
                url = urlsplit(row["html_url"])
                if url.scheme != "https" or url.hostname != "www.federalregister.gov" or f"/{identity}/" not in url.path:
                    raise ValueError("non_authoritative_link")
                if not any(a.get("slug") == "industry-and-security-bureau" for a in row["agencies"]):
                    raise ValueError("wrong_agency")
                published = datetime.strptime(row["publication_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if published > now or published < now - timedelta(days=LOOKBACK_DAYS + 1):
                    raise ValueError("outside_window")
                documents.append(SourceDocument(id=f"federal-register:{identity}", ticker="GLOBAL",
                    title=row["title"], description=row.get("abstract"),
                    published_at=published, observed_at=now, source_name="Federal Register / BIS",
                    source_type="government_source", source_url=row["html_url"], provider="geopolitical",
                    provider_document_id=identity, source_quality="primary_authoritative",
                    metadata={key: row.get(key) for key in FIELDS if key not in {"abstract", "title", "html_url", "agencies"}}))
            except Exception:
                rejected.append({"document_number": str(row.get("document_number", "unknown")) if isinstance(row, dict) else "unknown",
                                 "reason": "invalid_source_record"})
        # A malformed rule could be an amendment; retain diagnostics, suppress scoring.
        return {"documents": documents, "rejected": rejected, "complete": not rejected,
                "retrieved_at": now.isoformat(), "source_document_count": len(payload["results"])}


class GeopoliticalEvidenceProvider:
    name = "geopolitical"
    categories = ("geopolitical",)
    uses_placeholder_data = False

    def __init__(self, settings, source=None, metadata=None, classification_cache=None,
                 clock=lambda: datetime.now(timezone.utc)):
        self.settings, self.clock = settings, clock
        self.source = source or FederalRegisterSource(settings, clock=clock)
        self.metadata = metadata or classification
        self.classifications = classification_cache or Cache(settings.outlook_failure_cache_ttl)
        self.unavailable_reason = None if settings.outlook_geopolitical_enabled else "disabled"

    def get_evidence(self, ticker):
        return self.inspect(ticker)["evidence"]

    def _classification(self, ticker):
        value = self.metadata(ticker)
        if not isinstance(value, dict) or not value.get("sector"):
            raise ProviderUnavailable("missing_classification")
        return value

    def inspect(self, ticker):
        ticker = ticker.strip().upper()
        if self.unavailable_reason or not VALID_TICKER_PATTERN.fullmatch(ticker):
            return {"status": self.unavailable_reason or "invalid_symbol", "evidence": []}
        snapshot = self.source.get_documents()
        now = self.clock()
        events, excluded = [], list(snapshot["rejected"])
        # Structured RIN/correction references can link a renamed amendment to a
        # recognized family. They never establish direction on their own.
        seeds = [event for document in snapshot["documents"] if (event := normalize_event(document))]
        for document in snapshot["documents"]:
            event = normalize_event(document)
            if event is None:
                rins = set(document.metadata.get("regulation_id_numbers") or [])
                correction = str(document.metadata.get("correction_of") or "")
                linked = {e.family for e in seeds if rins & set(e.action_ids)
                          or e.document.provider_document_id in correction}
                if len(linked) == 1:
                    event = normalize_event(document, family_hint=next(iter(linked)))
            if event is None:
                excluded.append({"document_number": document.provider_document_id, "reason": "unsupported_product_or_event_class"})
            else:
                events.append(event)
        selected, prior = current_events(events, now)
        excluded.extend({"document_number": e.document.provider_document_id, "reason": reason} for e, reason in prior)
        diagnostic = {"source_document_count": snapshot["source_document_count"], "normalized_event_count": len(events),
                      "current_event_count": len(selected), "source_complete": snapshot["complete"],
                      "source_retrieved_at": snapshot["retrieved_at"], "matched": [], "excluded": excluded,
                      "classification": {}, "evidence": []}
        diagnostic["candidates"] = [{"document_number": e.document.provider_document_id,
            "title": e.document.title, "product_group": e.family, "countries": list(e.countries),
            "change": e.change, "interpretation_exclusion": e.reason,
            "published_at": e.document.published_at.isoformat(),
            "effective_at": e.effective_at.isoformat() if e.effective_at else None,
            "review_expires_at": e.expires_at.isoformat() if e.expires_at else None,
            "source_url": str(e.document.source_url)} for e in events]
        try:
            info = self.classifications.get(ticker, lambda: self._classification(ticker),
                                           self.settings.outlook_classification_cache_ttl)
        except Exception:
            diagnostic["excluded"].extend({"document_number": e.document.provider_document_id,
                "reason": "classification_unavailable"} for e in selected)
            return {**diagnostic, "status": "classification_unavailable"}
        diagnostic["classification"] = info
        context = CompanyContext(ticker=ticker, sector=info.get("sector"), industry=info.get("industry"), country=info.get("country"))
        for event in selected:
            evidence, reason = interpret_exposure(event, context, now)
            if not snapshot["complete"]:
                evidence, reason = None, "incomplete_source_snapshot"
            if info.get("quoteType") != "EQUITY":
                evidence, reason = None, "unsupported_instrument"
            if evidence:
                diagnostic["evidence"].append(evidence)
                diagnostic["matched"].append({"document_number": event.document.provider_document_id,
                    "product_group": event.family, "exposure": context.industry,
                    "reason": evidence.source_details["exposure_reason"], "impact": int(evidence.impact),
                    "source_url": str(evidence.source_url)})
            else:
                diagnostic["excluded"].append({"document_number": event.document.provider_document_id, "reason": reason})
        return {**diagnostic, "status": "incomplete_source_snapshot" if not snapshot["complete"] else
                "available" if diagnostic["evidence"] else "no_supported_exposure"}
