"""Offline-first direct Q4 parsers and bounded internal SEC document provider."""
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

from app.models.outlook_q4 import (
    DirectQ4Candidate, DirectQ4Document, DirectQ4Observation, DirectQ4Result,
)
from .transport import Cache, JsonClient, ProviderUnavailable

PARSER_VERSION = "direct-q4-1"
REVENUE_CONCEPTS = {
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    "us-gaap:Revenues", "us-gaap:SalesRevenueNet",
}
EPS_CONCEPT = "us-gaap:EarningsPerShareDiluted"
CONCEPT_CASE = {value.lower(): value for value in REVENUE_CONCEPTS | {EPS_CONCEPT}}
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
QUARTER_MIN_DAYS, QUARTER_MAX_DAYS = 70, 105


def _date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _decimal(value):
    try:
        result = Decimal(str(value).replace(",", "").replace("$", "").strip())
        return result if result.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


class InlineXbrlParser(HTMLParser):
    """Retain exact contexts/units/facts and explicit three-month table identity."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.contexts, self.units, self.facts, self.dei = {}, {}, [], {}
        self.context = self.unit = self.capture = self.fact = None
        self.table_depth, self.table_text, self.table_facts = 0, [], []

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): value for key, value in attrs}
        tag = tag.lower()
        if tag == "table":
            self.table_depth += 1
            if self.table_depth == 1:
                self.table_text, self.table_facts = [], []
        if tag.endswith(":context"):
            self.context = {"id": attrs.get("id"), "start": None, "end": None,
                "identifier": None, "dimensional": False}
        elif self.context and (tag.endswith(":segment") or tag.endswith(":scenario") or
                tag.endswith(":explicitmember") or tag.endswith(":typedmember")):
            self.context["dimensional"] = True
        if tag.endswith(":unit"):
            self.unit = {"id": attrs.get("id"), "measure": ""}
        if tag.endswith((":startdate", ":enddate", ":identifier", ":measure")) or tag in (
                "dei:documentfiscalyearfocus", "dei:documentfiscalperiodfocus",
                "dei:documentperiodenddate", "dei:entityregistrantname"):
            self.capture = [tag, ""]
        if tag in ("ix:nonfraction", "ix:nonnumeric") or tag in CONCEPT_CASE:
            name = attrs.get("name") if tag.startswith("ix:") else CONCEPT_CASE[tag]
            self.fact = {"name": name, "context": attrs.get("contextref"),
                "unit": attrs.get("unitref"), "scale": attrs.get("scale", "0"),
                "decimals": attrs.get("decimals"), "text": "", "locator": f"fact:{len(self.facts)}",
                "end_tag": tag}

    def handle_data(self, data):
        if self.capture:
            self.capture[1] += data
        if self.fact:
            self.fact["text"] += data
        if self.table_depth:
            self.table_text.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.capture and tag == self.capture[0]:
            key, value = self.capture[0], " ".join(self.capture[1].split())
            if self.context and key.endswith(":startdate"):
                self.context["start"] = value
            elif self.context and key.endswith(":enddate"):
                self.context["end"] = value
            elif self.context and key.endswith(":identifier"):
                self.context["identifier"] = value
            elif self.unit and key.endswith(":measure"):
                self.unit["measure"] = value
            elif key.startswith("dei:"):
                self.dei[key.split(":", 1)[1]] = value
            self.capture = None
        if self.fact and tag == self.fact["end_tag"]:
            index = len(self.facts)
            self.facts.append(self.fact)
            if self.table_depth:
                self.table_facts.append(index)
            name = str(self.fact.get("name") or "").lower()
            if name.startswith("dei:"):
                self.dei[name.split(":", 1)[1]] = " ".join(self.fact["text"].split())
            self.fact = None
        if self.context and tag.endswith(":context"):
            if self.context["id"]:
                self.contexts[self.context["id"]] = self.context
            self.context = None
        if self.unit and tag.endswith(":unit"):
            if self.unit["id"]:
                self.units[self.unit["id"]] = self.unit["measure"]
            self.unit = None
        if tag == "table":
            if self.table_depth == 1:
                text = " ".join("".join(self.table_text).split()).lower()
                if "three months ended" in text or "fourth quarter ended" in text:
                    for index in self.table_facts:
                        self.facts[index]["explicit_q4_table"] = True
            self.table_depth = max(0, self.table_depth - 1)


class SimpleTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.table, self.row, self.cell = [], None, None, None
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table" and self.table is None:
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = ""
    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join(self.cell.split())); self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row); self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table); self.table = None


def _base_candidate(document, metric, **changes):
    data = dict(ticker=document.ticker, issuer=document.issuer, cik=document.cik,
        metric=metric, fiscal_year=document.fiscal_year, source_family=document.source_family,
        accession=document.accession, form=document.form, document_url=document.document_url,
        document_id=document.document_id, filing_date=document.filing_date,
        publication_time=document.publication_time, amendment=document.form.endswith("/A"))
    data.update(changes)
    return DirectQ4Candidate(**data)


def parse_filing_xbrl(document):
    if document.source_family != "filing_xbrl":
        return ()
    parser = InlineXbrlParser(); parser.feed(document.content)
    fy = str(parser.dei.get("documentfiscalyearfocus", ""))
    fp = str(parser.dei.get("documentfiscalperiodfocus", "")).upper()
    doc_end = _date(parser.dei.get("documentperiodenddate"))
    issuer = parser.dei.get("entityregistrantname")
    anchors_ok = fy == str(document.fiscal_year) and fp == "FY" and doc_end is not None and (
        not issuer or issuer.casefold() == document.issuer.casefold())
    result = []
    for fact in parser.facts:
        concept = fact.get("name")
        if concept not in REVENUE_CONCEPTS | {EPS_CONCEPT}:
            continue
        metric = "diluted_eps" if concept == EPS_CONCEPT else "revenue"
        context = parser.contexts.get(fact.get("context"), {})
        start, end = _date(context.get("start")), _date(context.get("end"))
        duration = (end - start).days + 1 if start and end and start <= end else None
        measure = parser.units.get(fact.get("unit"), "")
        unit = "USD/shares" if measure.lower() in ("usd/shares", "iso4217:usd/xbrli:shares") else "USD" if measure.lower() in ("usd", "iso4217:usd") else measure
        value = _decimal(fact.get("text")); scale = int(fact.get("scale") or 0) if str(fact.get("scale") or "0").lstrip("-").isdigit() else None
        reasons = []
        if document.form not in ("10-K", "10-K/A"): reasons.append("unsupported_form")
        if not anchors_ok: reasons.append("missing_or_conflicting_fiscal_anchor")
        if not fact.get("explicit_q4_table"): reasons.append("no_explicit_q4_table_identity")
        if not start or not end or duration is None or not QUARTER_MIN_DAYS <= duration <= QUARTER_MAX_DAYS: reasons.append("not_standalone_quarter")
        if end != doc_end: reasons.append("period_end_mismatch")
        if context.get("identifier") not in (document.cik, str(int(document.cik))): reasons.append("issuer_identity_mismatch")
        if context.get("dimensional"): reasons.append("dimensional_context")
        expected = "USD/shares" if metric == "diluted_eps" else "USD"
        if unit != expected: reasons.append("incompatible_unit")
        if value is None or scale is None: reasons.append("invalid_exact_value")
        result.append(_base_candidate(document, metric, period_start=start, period_end=end,
            original_value=value, original_concept=concept, original_unit=unit or None, scale=scale,
            currency="USD" if unit in ("USD", "USD/shares") else None, accounting_basis="gaap",
            share_basis="diluted" if metric == "diluted_eps" else "not_applicable",
            reporting_scope="dimensional" if context.get("dimensional") else "consolidated",
            locator=f"xbrl-context:{fact.get('context')}:{fact.get('locator')}",
            rejection_reasons=tuple(dict.fromkeys(reasons))))
    return tuple(result)


def parse_earnings_release_table(document):
    if document.source_family != "earnings_release_table":
        return ()
    parser = SimpleTables(); parser.feed(document.content)
    result = []
    for table_index, rows in enumerate(parser.tables[:8]):
        flattened = " | ".join(" | ".join(row) for row in rows)
        identity = re.search(r"Fourth Quarter Ended\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", flattened, re.I)
        if not identity:
            continue
        start, end = _date(identity.group(1)), _date(identity.group(2))
        for row_index, row in enumerate(rows):
            text = " | ".join(row)
            metric = "diluted_eps" if re.search(r"GAAP\s+Diluted\s+EPS", text, re.I) else "revenue" if re.search(r"^Revenue\b", text, re.I) else None
            if not metric:
                continue
            approximate = bool(re.search(r"(?:approximately|about|~)", text, re.I))
            adjusted = bool(re.search(r"(?:adjusted|non[- ]GAAP)", text, re.I))
            numeric_text = " | ".join(row[1:])
            number = re.search(r"\$?\(?([0-9][0-9,]*(?:\.\d+)?)\)?", numeric_text)
            scale_match = re.search(r"USD\s+(ones|thousands|millions|billions)|USD/share", text, re.I)
            scale_name = scale_match.group(1).lower() if scale_match and scale_match.group(1) else "per_share" if scale_match else None
            scale = {"ones": 0, "thousands": 3, "millions": 6, "billions": 9, "per_share": 0}.get(scale_name)
            value = _decimal(number.group(1)) if number else None
            if value is not None and scale is not None and re.search(r"\(\s*\$?[0-9][0-9,]*(?:\.\d+)?\s*\)", numeric_text): value = -value
            duration = (end - start).days + 1 if start and end else None
            reasons = []
            if document.form not in ("8-K", "8-K/A"): reasons.append("unsupported_form")
            if adjusted: reasons.append("non_gaap_or_adjusted_metric")
            if approximate: reasons.append("rounded_or_approximate_value")
            if not start or not end or not QUARTER_MIN_DAYS <= duration <= QUARTER_MAX_DAYS: reasons.append("not_standalone_quarter")
            if value is None or scale is None: reasons.append("missing_exact_value_or_scale")
            result.append(_base_candidate(document, metric, period_start=start, period_end=end,
                original_value=value, original_concept="EarningsPerShareDiluted" if metric == "diluted_eps" else "RevenueFromContractWithCustomerExcludingAssessedTax",
                original_unit="USD/shares" if metric == "diluted_eps" else "USD", scale=scale,
                currency="USD", accounting_basis="non_gaap" if adjusted else "gaap",
                share_basis="diluted" if metric == "diluted_eps" else "not_applicable",
                reporting_scope="consolidated", exact=not approximate,
                locator=f"table:{table_index}:row:{row_index}", rejection_reasons=tuple(reasons)))
    return tuple(result)


def qualify_direct_q4(documents):
    candidates = []
    for document in documents:
        candidates.extend(parse_filing_xbrl(document) if document.source_family == "filing_xbrl" else parse_earnings_release_table(document))
    valid = [row for row in candidates if not row.rejection_reasons]
    observations = []
    grouped = defaultdict(list)
    for row in valid:
        grouped[(row.ticker, row.metric, row.fiscal_year)].append(row)
    for key, rows in grouped.items():
        def normalized(row):
            return row.original_value * (Decimal(10) ** row.scale)
        amendments = [row for row in rows if row.form in ("10-K/A", "8-K/A")]
        compatible = {(row.period_start, row.period_end, normalized(row), row.original_unit,
            row.accounting_basis, row.share_basis, row.reporting_scope) for row in rows}
        explicit_amendment = len(amendments) == 1 and len({row.source_family for row in rows}) == 1
        conflict = len(compatible) != 1 and not explicit_amendment
        # Exact agreement permits deterministic filing-XBRL selection because it
        # carries the original context; recency alone never promotes a source family.
        ordered = sorted(rows, key=lambda row: (row.form.endswith("/A"),
            row.source_family == "filing_xbrl", row.filing_date, row.accession), reverse=True)
        selected = amendments[0] if explicit_amendment else ordered[0] if not conflict else None
        for row in ordered:
            status = "conflict" if conflict else "current" if row is selected else "superseded" if explicit_amendment else "corroborating"
            oid = sha256(f"{PARSER_VERSION}|{row.ticker}|{row.metric}|{row.fiscal_year}|{row.accession}|{row.document_id}|{normalized(row)}".encode()).hexdigest()[:24]
            selected_id = None if not selected else sha256(f"{PARSER_VERSION}|{selected.ticker}|{selected.metric}|{selected.fiscal_year}|{selected.accession}|{selected.document_id}|{normalized(selected)}".encode()).hexdigest()[:24]
            observations.append(DirectQ4Observation(observation_id=oid, ticker=row.ticker,
                issuer=row.issuer, cik=row.cik, metric=row.metric, fiscal_year=row.fiscal_year,
                period_start=row.period_start, period_end=row.period_end,
                duration_days=(row.period_end-row.period_start).days+1,
                original_value=row.original_value, normalized_value=normalized(row),
                original_concept=row.original_concept, original_unit=row.original_unit,
                scale=row.scale, currency="USD", share_basis=row.share_basis,
                source_family=row.source_family, accession=row.accession, form=row.form,
                document_url=row.document_url, document_id=row.document_id,
                filing_date=row.filing_date, publication_time=row.publication_time,
                locator=row.locator, version_status=status,
                superseded_by=selected_id if status in ("corroborating", "superseded") else None,
                comparison_eligible=status == "current",
                comparison_exclusion_reasons=() if status == "current" else
                    ("cross_source_conflict",) if status == "conflict" else ("corroborating_source",)))
    current = sum(row.version_status == "current" for row in observations)
    has_conflict = any(row.version_status == "conflict" for row in observations)
    status = "available" if current and not any(row.rejection_reasons for row in candidates) else "partial" if current else "conflict" if has_conflict else "unavailable"
    reasons = tuple(dict.fromkeys(reason for row in candidates for reason in row.rejection_reasons))
    return DirectQ4Result(status=status, candidates=tuple(candidates), observations=tuple(observations), rejection_reasons=reasons)


class DirectQ4Provider:
    """Fetch only preselected SEC documents; disabled and unregistered by default."""
    name = "sec_direct_q4"
    def __init__(self, settings, client=None):
        self.settings, self.client = settings, client or JsonClient(settings)
        self.cache = Cache(settings.outlook_failure_cache_ttl, capacity=32)
        self.requests = self.cache_hits = 0
        self.unavailable_reason = "disabled" if not settings.outlook_sec_q4_enabled else None

    def retrieve_selected(self, documents):
        if self.unavailable_reason:
            raise ProviderUnavailable(self.unavailable_reason)
        selected = tuple(documents)[:self.settings.outlook_sec_q4_max_candidate_filings]
        loaded = []
        for document in selected:
            parts = urlsplit(document.document_url)
            if parts.scheme != "https" or parts.hostname != "www.sec.gov" or not ACCESSION.fullmatch(document.accession):
                continue
            key = (PARSER_VERSION, document.accession, document.document_id)
            before = self.requests
            def load():
                if self.requests >= self.settings.outlook_sec_q4_request_budget:
                    raise ProviderUnavailable("q4_request_budget_exceeded")
                self.requests += 1
                text = self.client.get_text(document.document_url, provider="sec",
                    user_agent=self.settings.outlook_sec_user_agent)
                if len(text.encode("utf-8")) > self.settings.outlook_sec_q4_document_max_bytes:
                    raise ProviderUnavailable("q4_document_too_large")
                return text
            try:
                content = self.cache.get(key, load, self.settings.outlook_sec_q4_cache_ttl)
            except ProviderUnavailable:
                continue
            if self.requests == before: self.cache_hits += 1
            loaded.append(document.model_copy(update={"content": content}))
        result = qualify_direct_q4(loaded)
        return result.model_copy(update={"requests": self.requests, "cache_hits": self.cache_hits})
