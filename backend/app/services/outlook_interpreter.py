"""Narrow primary-source event rules. Ambiguity produces no directional evidence."""
import hashlib
import logging
import re
from decimal import Decimal

from app.models.outlook_document import SourceDocument
from app.models.outlook_evidence import CompanyContext, OutlookEvidence
from app.services.outlook_earnings import reporting_comparison, gaap_margin_comparisons
from app.services.outlook_reporting import fact_reporting_identity

LOGGER = logging.getLogger(__name__)
VERSION = "rules-3b-2"
# These reject conditional, negated, historical quotation and segment-only assertions.
AMBIGUOUS = re.compile(r"\b(?:not|no|never|may|might|could|would|if|expects?|expected|anticipates?|"
    r"previously|prior guidance was|last year|segment|division|subsidiary|constant currency|"
    r"excluding|pro forma|analysts?|consensus)\b", re.I)
NUMBER = r"(?:0|[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)(?:\.\d+)?"


def number(value):
    return Decimal(value.replace(",", ""))


def sec_observation_document(observation: OutlookEvidence) -> SourceDocument:
    """Convert existing retained observation identity, without fabricating filing text."""
    return SourceDocument(id=observation.id, ticker=observation.ticker, title=observation.title,
        published_at=observation.published_at, observed_at=observation.observed_at,
        source_name=observation.source, source_type=observation.source_type,
        source_url=observation.source_url, provider=observation.raw_provider,
        provider_document_id=observation.raw_provider_id,
        source_quality="primary_authoritative", metadata=observation.source_details)


class DeterministicOutlookInterpreter:
    version = VERSION

    def interpret(self, ticker: str, documents: list[SourceDocument],
                  company_context: CompanyContext) -> list[OutlookEvidence]:
        result = []
        if company_context.ticker.upper() != ticker.upper():
            return result
        for document in documents:
            try:
                if document.ticker == ticker.upper():
                    result.extend(self._interpret_document(document, company_context))
            except Exception as error:
                LOGGER.warning("outlook_interpretation_failed kind=%s", type(error).__name__)
        return result

    def _evidence(self, document, category, event, title, basis, impact, *, numeric=None, confidence=.9, materiality=.8):
        # Same accession+event is one vote even when both filing and exhibit describe it.
        identity = str(document.metadata.get("accession") or document.provider_document_id)
        digest = hashlib.sha256(f"{document.id}:{event}:{basis}".encode()).hexdigest()[:20]
        return OutlookEvidence(id=f"{document.provider}:{digest}", ticker=document.ticker,
            category=category, event_type=event, title=title, summary=basis,
            source=document.source_name, source_type=document.source_type, source_url=document.source_url,
            published_at=document.published_at, observed_at=document.observed_at,
            impact=impact, confidence=confidence, materiality=materiality,
            materiality_reason="Explicit issuer-level primary-source disclosure.",
            raw_provider=document.provider, raw_provider_id=identity,
            source_quality=document.source_quality,
            source_details={**document.metadata, "source_document_id": document.id,
                "provider_document_id": document.provider_document_id, "interpreter": VERSION,
                **({"earnings_release_id": f"{document.provider}:{identity}"}
                   if category == "earnings" and event in ("earnings_result", "margin_change") else {}),
                "evidence_basis": basis, "numeric": numeric or {},
                **({"reporting_identity": fact_reporting_identity(document, numeric or {}).model_dump(mode="json")}
                   if category == "earnings" and event in ("earnings_result", "margin_change") else {})})

    def _interpret_document(self, document, context):
        from app.services.outlook_structured.policy import SEC_ITEMS
        if document.source_quality != "primary_authoritative":
            return []  # Discovery metadata alone is deliberately not interpreted in this version.
        result = []
        items = document.metadata.get("items", [])
        if (document.source_type == "regulatory_filing" and document.provider == "sec"
                and document.metadata.get("form") == "8-K" and not document.extracted_text):
            for item in items:
                mapping = SEC_ITEMS.get(item)
                if mapping and mapping[1] < 0:
                    event, impact, materiality, title = mapping
                    result.append(self._evidence(document, "company", event, title,
                        f"SEC 8-K Item {item} discloses {title.lower()}.", impact,
                        confidence=.95, materiality=materiality))
            return result
        if (document.provider == "sec" and document.metadata.get("form") == "8-K"
                and "3.01" in items and document.metadata.get("document_kind") == "listing_item"):
            for sentence in document.extracted_text.splitlines():
                if len(sentence) > 700 or re.search(r"\b(?:not|may|could|if|regained|subsidiary|supplier)\b", sentence, re.I):
                    continue
                if re.search(r"^(?:we|the company) (?:has )?received (?:a |written )?notice from "
                    r"(?:the )?(?:Nasdaq|NYSE|New York Stock Exchange).{0,180}"
                    r"(?:noncompliance|non-compliance|failure to (?:meet|satisfy))", sentence, re.I):
                    result.append(self._evidence(document, "company", "regulatory_action",
                        "Listing noncompliance notice", sentence, -1, materiality=.85))
            return result
        earnings_context = (document.metadata.get("form") == "8-K" and "2.02" in items
            and document.metadata.get("document_kind") in ("earnings_exhibit", "earnings_item")) or (
            document.source_type == "company_release" and document.metadata.get("document_kind") == "earnings_release")
        if not earnings_context:
            return []
        for numeric in gaap_margin_comparisons(document.tables):
            change = numeric["percentage_points"]
            metric = numeric["metric"].replace("_", " ")
            basis = (f"GAAP {metric}: {numeric['current_percent']:g}% in {numeric['current_period']} versus "
                     f"{numeric['prior_percent']:g}% in {numeric['prior_period']}; "
                     f"{change:+g} percentage points year over year.")
            result.append(self._evidence(document, "earnings", "margin_change", "Year-over-year margin change",
                basis, 1 if change > 0 else -1, numeric=numeric, materiality=min(.8, abs(change)/2)))
        # Paragraph/sentence scope, bounded by SourceDocument. Never join across table cells.
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])|[\r\n]+", document.extracted_text):
            sentence = re.sub(r"\s+", " ", sentence).strip()
            if not 10 <= len(sentence) <= 500:
                continue
            # Withdrawal explicitly refers to previously issued guidance.
            checked = re.sub(r"previously issued", "issued", sentence, flags=re.I)
            if AMBIGUOUS.search(checked):
                continue
            numeric = reporting_comparison(sentence, context.company_name, document.ticker)
            if numeric:
                change = numeric["change_percent"]
                result.append(self._evidence(document, "earnings", "earnings_result",
                    "Year-over-year earnings result", sentence, 1 if change > 0 else -1,
                    numeric=numeric, materiality=min(.8, abs(change)/10)))
                continue
            subject = r"(?:we|the company|" + re.escape(context.company_name or document.ticker) + r")"
            prior_guidance = re.fullmatch(subject + r" (?:has |have )?(raises?|raised|lowers?|lowered|cuts?|cut|withdraws?|withdrew|withdrawn) "
                r"(?:its |our )?(?:previously issued|prior) (?:financial |revenue |earnings )?guidance[.]?", sentence, re.I)
            if prior_guidance:
                verb = prior_guidance[1].lower()
                event = "guidance_raise" if verb.startswith("rais") else "guidance_withdrawal" if verb.startswith("with") else "guidance_cut"
                result.append(self._evidence(document, "earnings", event,
                    "Company changes previously issued guidance", sentence, 1 if event == "guidance_raise" else -1))
                continue
            guidance = re.fullmatch(subject + r" (?:has |have )?(raises?|raised|lowers?|lowered|cuts?|cut|withdraws?|withdrew|withdrawn) "
                r"(?:its |our )?(?:(?:full[- ]year|fiscal[- ]year|FY\s?\d{4}|annual) )?"
                r"(?:(?:revenue|EPS|earnings) )?(?:guidance|outlook)( from .+)?[.]?", sentence, re.I)
            # Require a fiscal scope or an explicitly issued forecast, not a vague outlook.
            if guidance and re.search(r"full[- ]year|fiscal[- ]year|FY\s?\d{4}|annual|issued", sentence, re.I):
                verb = guidance[1].lower()
                event = "guidance_raise" if verb.startswith("rais") else "guidance_withdrawal" if verb.startswith("with") else "guidance_cut"
                numeric = {}
                materiality = .8
                if guidance[2]:
                    ranges = re.fullmatch(r" from \$(" + NUMBER + r")[–-]\$(" + NUMBER + r") (million|billion) "
                        r"to \$(" + NUMBER + r")[–-]\$(" + NUMBER + r") \3[.]?", guidance[2], re.I)
                    if not ranges or event == "guidance_withdrawal":
                        continue
                    low, high, new_low, new_high = [number(ranges[index]) for index in (1, 2, 4, 5)]
                    sign = 1 if event == "guidance_raise" else -1
                    if not (0 < low <= high <= Decimal('1e12') and 0 < new_low <= new_high <= Decimal('1e12')) or (
                        (new_low-low)*sign <= 0 or (new_high-high)*sign <= 0):
                        continue
                    numeric = {"prior_range": [float(low), float(high)], "current_range": [float(new_low), float(new_high)],
                        "unit": "USD_" + ranges[3].lower()}
                    materiality = min(.8, float(abs((new_low+new_high)-(low+high))/(low+high))*10)
                result.append(self._evidence(document, "earnings", event,
                    {"guidance_raise": "Company raises guidance", "guidance_cut": "Company lowers guidance",
                     "guidance_withdrawal": "Company withdraws guidance"}[event], sentence,
                    1 if event == "guidance_raise" else -1, numeric=numeric, materiality=materiality))
                continue
            withdrawal = re.fullmatch(subject + r" (?:has |have )?(?:withdraws|withdrew|withdrawn) "
                r"(?:its |our )?(?:previously )?issued (?:financial |revenue |earnings )?guidance[.]?", sentence, re.I)
            if withdrawal:
                result.append(self._evidence(document, "earnings", "guidance_withdrawal",
                    "Company withdraws guidance", sentence, -1))
                continue
            prefix = r"(?:(?:our|total|consolidated) )?"
            levels = re.fullmatch(prefix + r"(revenue|revenues) (increased|decreased) from \$(" + NUMBER +
                r") (million|billion) to \$(" + NUMBER + r") \4 year[- ]over[- ]year[.]?", sentence, re.I)
            if levels:
                before, after = number(levels[3]), number(levels[5])
                sign = 1 if levels[2].lower() == "increased" else -1
                if not (0 < before <= Decimal('1e12') and 0 <= after <= Decimal('1e12')) or (after-before)*sign <= 0:
                    continue
                change = (after-before) / before * 100
                if abs(change) > 1000:
                    continue
                result.append(self._evidence(document, "earnings", "earnings_result",
                    "Year-over-year earnings result", sentence, sign,
                    materiality=min(.8, float(abs(change))/10), numeric={"metric": "revenue",
                        "prior_value": float(before), "current_value": float(after), "unit": "USD_" + levels[4].lower(),
                        "change_percent": float(change), "comparison": "year_over_year"}))
                continue
            growth = re.fullmatch(prefix + r"(revenue|revenues|diluted EPS|earnings per share) "
                r"(increased|decreased|grew|declined) (?:by )?(" + NUMBER + r")% "
                r"(?:year[- ]over[- ]year|compared (?:with|to) (?:the )?(?:same|prior)[- ]year period)[.]?", sentence, re.I)
            if growth:
                change = number(growth[3])
                direction = 1 if growth[2].lower() in ("increased", "grew") else -1
                if not 0 < change <= 1000 or (direction < 0 and change > 100):
                    continue
                result.append(self._evidence(document, "earnings", "earnings_result",
                    "Year-over-year earnings result", sentence, direction,
                    materiality=min(.8, float(change) / 10),
                    numeric={"metric": growth[1].lower(), "change_percent": float(change) * direction,
                             "comparison": "year_over_year"}))
                continue
            margin = re.fullmatch(prefix + r"(gross|operating) margin (increased|decreased|expanded|contracted) "
                r"from (" + NUMBER + r")% to (" + NUMBER + r")% "
                r"(?:year[- ]over[- ]year|compared (?:with|to) (?:the )?(?:same|prior)[- ]year period)[.]?", sentence, re.I)
            if margin:
                before, after = number(margin[3]), number(margin[4])
                direction = 1 if margin[2].lower() in ("increased", "expanded") else -1
                if not (0 <= before <= 100 and 0 <= after <= 100) or (after-before)*direction <= 0:
                    continue
                result.append(self._evidence(document, "earnings", "margin_change",
                    "Year-over-year margin change", sentence, direction,
                    materiality=min(.8, float(abs(after-before)) / 2),
                    numeric={"metric": margin[1].lower() + "_margin", "prior_percent": float(before),
                        "current_percent": float(after), "percentage_points": float(after-before),
                        "comparison": "year_over_year"}))
        return result
