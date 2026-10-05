"""Pure bounded selected-filing inline-XBRL revenue operand qualification."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import json
import re

from app.models.outlook_inline_revenue import (
    CertifiedConceptEquivalenceUse, ContextIdentity, DeiAnchor, ExpandedQName, NumericIdentity,
    RevenueConceptIdentityDiagnostic, TaxonomyConceptEquivalence,
    FiscalAnchorDiagnostic, FiscalAnchorObservationDiagnostic, FiscalAnchorSetDiagnostic,
    RevenueOperandPartitionResult, SecInlineRevenueOperand,
    SecInlineRevenueOperandResult, SecInlineRevenueSourceFact,
    SelectedFilingDocument, UnitIdentity,
)


POLICY_VERSION = "sec-inline-xbrl-revenue-operand-2"
STRICT_PARTITION_IDENTITY_POLICY_VERSION = "revenue-operand-partition-identity-1"
PARTITION_IDENTITY_POLICY_VERSION = "revenue-operand-partition-identity-2"
EQUIVALENCE_POLICY_VERSION = "us-gaap-2024-2025-revenue-concept-equivalence-1"
_US_GAAP_2024 = "http://fasb.org/us-gaap/2024"
_US_GAAP_2025 = "http://fasb.org/us-gaap/2025"
_US_GAAP_2024_SHA256 = "DECDD417D86FF7BFB5CA166C0CA1001017AEA873673544A8D7F91C34BF5D82DF"
_US_GAAP_2025_SHA256 = "A3B835925AD74030EB5BE865A26D7DFE44013081C4AB7204B6122316A685FFF4"


def _equivalence_record(local_name):
    return TaxonomyConceptEquivalence(taxonomy_family="us-gaap", local_name=local_name,
        from_namespace=_US_GAAP_2024, to_namespace=_US_GAAP_2025,
        source_package_sha256=_US_GAAP_2024_SHA256,
        target_package_sha256=_US_GAAP_2025_SHA256,
        certification_identity="phase6b5c2a5w8-us-gaap-cross-version-equivalence",
        record_identity=f"phase6b5c2a5w8:{local_name}:2024-2025",
        policy_version=EQUIVALENCE_POLICY_VERSION, symmetric_for_identity=True)


CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES = (
    _equivalence_record("RevenueFromContractWithCustomerExcludingAssessedTax"),
    _equivalence_record("Revenues"),
)
STRICT_REVENUE_CONCEPT_EQUIVALENCES = ()
SCHEMA_VERSION = "1"
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_ELEMENTS = 200_000
MAX_CONTEXTS = 4_096
MAX_UNITS = 256
MAX_FACTS = 50_000
MAX_REVENUE_FACTS = 256
MAX_DIMENSIONS = 16
MAX_TYPED_DIMENSIONS = 16
MAX_COMPETING_FACTS = 16
MAX_IDENTITY_CHARS = 256
MAX_NUMERIC_CHARS = 128
MAX_ANCHOR_DIAGNOSTIC_OBSERVATIONS = 32
MAX_ANCHOR_DIAGNOSTIC_DISTINCT = 16
MAX_ANCHOR_DIAGNOSTIC_LEXICAL = 64

REVENUE_LOCAL_NAMES = frozenset({
    "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
})
_KNOWN_LOCAL_CASE = {name.casefold(): name for name in REVENUE_LOCAL_NAMES | {
    "DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus", "DocumentPeriodEndDate", "DocumentType",
}}
US_GAAP_NAMESPACES = frozenset(
    f"http://fasb.org/us-gaap/{year}" for year in range(2018, 2028)
)
DEI_NAMESPACES = frozenset(f"http://xbrl.sec.gov/dei/{year}" for year in range(2018, 2028))
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
IX_NAMESPACES = frozenset({
    "http://www.xbrl.org/2013/inlineXBRL", "http://www.xbrl.org/2008/inlineXBRL",
})
ISO4217 = "http://www.xbrl.org/2003/iso4217"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
IxtNamespaces = frozenset({
    "http://www.xbrl.org/inlineXBRL/transformation/2015-02-26",
    "http://www.xbrl.org/inlineXBRL/transformation/2020-02-12",
    "http://www.xbrl.org/inlineXBRL/transformation/2022-02-16",
})
APPROVED_DEI_DATE_TRANSFORM = (
    "resolved:http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
    "#date-monthname-day-year-en"
)
_ENGLISH_MONTHS = {name: month for month, name in enumerate(("January", "February",
    "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December"), start=1)}
_MONTH_NAME_DATE = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"[ \u00a0]+([1-9]|[12]\d|3[01]),[ \u00a0]+(\d{4})$")
SUPPORTED_ENTITY_SCHEMES = frozenset({"http://www.sec.gov/CIK", "https://www.sec.gov/CIK"})
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")


class ParseFailure(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _local(tag: str) -> str:
    return tag.split(":", 1)[-1].lower()


def _date(value):
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None


def _bounded(value: str | None):
    value = str(value or "")
    if len(value) > MAX_IDENTITY_CHARS:
        raise ParseFailure("parser_cap_exceeded")
    return value


def _resolve_qname(value: str | None, namespaces: dict[str, str], *, default=True):
    raw = _bounded(value).strip()
    if not raw:
        return None
    if ":" in raw:
        prefix, local = raw.split(":", 1)
        uri = namespaces.get(prefix.lower())
    else:
        local, uri = raw, namespaces.get("") if default else None
    if not uri or not local:
        return None
    local = _KNOWN_LOCAL_CASE.get(local.casefold(), local)
    return ExpandedQName(namespace_uri=uri, local_name=local)


def _namespaced_attr(attrs, namespaces, namespace, local):
    for name, value in attrs.items():
        if ":" not in name:
            continue
        resolved = _resolve_qname(name, namespaces, default=False)
        if resolved and resolved.namespace_uri == namespace and resolved.local_name.casefold() == local.casefold():
            return value
    return None


@dataclass
class _Capture:
    kind: str
    end_tag: str
    depth: int
    namespaces: dict[str, str]
    attrs: dict[str, str]
    node_ordinal: int
    fact_ordinal: int | None = None
    qname: ExpandedQName | None = None
    parts: list[str] = field(default_factory=list)


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.namespaces: list[dict[str, str]] = [{}]
        self.tags: list[str] = []
        self.elements = self.fact_starts = self.revenue_fact_starts = 0
        self.contexts: dict[str, list[dict]] = {}
        self.units: dict[str, list[dict]] = {}
        self.revenue_facts: list[dict] = []
        self.dei: dict[str, list[tuple[str, int]]] = {}
        self.continuation_ids: set[str] = set()
        self.context = None
        self.unit = None
        self.capture: _Capture | None = None
        self.segment_depth = self.scenario_depth = None

    def _ns(self, attrs):
        current = dict(self.namespaces[-1])
        for key, value in attrs.items():
            if key == "xmlns":
                current[""] = _bounded(value)
            elif key.startswith("xmlns:"):
                current[key.split(":", 1)[1].lower()] = _bounded(value)
        return current

    def _start_capture(self, kind, tag, attrs, ns, node, *, qname=None, fact_ordinal=None):
        if self.capture is not None:
            raise ParseFailure("xbrl_parse_failure")
        self.capture = _Capture(kind, tag, len(self.tags), ns, attrs, node,
            fact_ordinal=fact_ordinal, qname=qname)

    def handle_starttag(self, tag, attrs):
        self.elements += 1
        if self.elements > MAX_ELEMENTS:
            raise ParseFailure("parser_cap_exceeded")
        tag = tag.lower()
        attrs = {str(k).lower(): _bounded(v) for k, v in attrs}
        ns = self._ns(attrs)
        self.namespaces.append(ns)
        self.tags.append(tag)
        node = self.elements - 1
        local = _local(tag)
        tag_qname = _resolve_qname(tag, ns)

        if (tag_qname and tag_qname.namespace_uri in IX_NAMESPACES
                and local == "continuation" and attrs.get("id")):
            self.continuation_ids.add(attrs["id"])

        if self.context is not None:
            if self.segment_depth is not None and len(self.tags) > self.segment_depth:
                self.context["segment_nonempty"] = True
            if self.scenario_depth is not None and len(self.tags) > self.scenario_depth:
                self.context["scenario_nonempty"] = True

        if tag_qname and tag_qname.namespace_uri == XBRLI and local == "context":
            if self.context is not None:
                raise ParseFailure("xbrl_parse_failure")
            self.context = {"id": _bounded(attrs.get("id")), "entity_scheme": "",
                "entity_value": "", "start": None, "end": None, "instant": None,
                "segment_present": False, "scenario_present": False,
                "segment_nonempty": False, "scenario_nonempty": False,
                "dimensions": {}, "dimension_conflict": False, "typed": 0}
            if not self.context["id"]:
                raise ParseFailure("context_missing")
        elif self.context is not None and tag_qname and tag_qname.namespace_uri == XBRLI:
            if local == "identifier":
                self._start_capture("identifier", tag, attrs, ns, node)
            elif local in {"startdate", "enddate", "instant"}:
                self._start_capture(local, tag, attrs, ns, node)
            elif local == "segment":
                self.context["segment_present"] = True; self.segment_depth = len(self.tags)
            elif local == "scenario":
                self.context["scenario_present"] = True; self.scenario_depth = len(self.tags)
        if self.context is not None and tag_qname and tag_qname.namespace_uri == XBRLDI:
            if local == "explicitmember":
                if len(self.context["dimensions"]) >= MAX_DIMENSIONS:
                    raise ParseFailure("parser_cap_exceeded")
                self._start_capture("explicitmember", tag, attrs, ns, node)
            elif local == "typedmember":
                self.context["typed"] += 1
                if self.context["typed"] > MAX_TYPED_DIMENSIONS:
                    raise ParseFailure("parser_cap_exceeded")

        if tag_qname and tag_qname.namespace_uri == XBRLI and local == "unit":
            if self.unit is not None:
                raise ParseFailure("xbrl_parse_failure")
            self.unit = {"id": _bounded(attrs.get("id")), "numerator": [], "denominator": [],
                "divide": False, "side": "numerator"}
            if not self.unit["id"]:
                raise ParseFailure("unit_unavailable")
        elif self.unit is not None and tag_qname and tag_qname.namespace_uri == XBRLI:
            if local == "divide": self.unit["divide"] = True
            elif local == "unitnumerator": self.unit["side"] = "numerator"
            elif local == "unitdenominator": self.unit["side"] = "denominator"
            elif local == "measure": self._start_capture("measure", tag, attrs, ns, node)

        is_inline = bool(tag_qname and tag_qname.namespace_uri in IX_NAMESPACES
            and local in {"nonfraction", "nonnumeric"})
        is_instance_fact = bool(tag_qname and (tag_qname.namespace_uri in US_GAAP_NAMESPACES
            or tag_qname.namespace_uri in DEI_NAMESPACES) and local not in {
                "context", "unit", "measure", "identifier", "startdate", "enddate", "instant"})
        if is_inline or is_instance_fact:
            self.fact_starts += 1
            if self.fact_starts > MAX_FACTS:
                raise ParseFailure("parser_cap_exceeded")
            qname = _resolve_qname(attrs.get("name"), ns) if is_inline else tag_qname
            if qname is None:
                if is_inline: raise ParseFailure("namespace_unresolved")
                return
            fact_ordinal = self.fact_starts - 1
            if qname.namespace_uri in DEI_NAMESPACES and qname.local_name in {
                    "DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus",
                    "DocumentPeriodEndDate", "DocumentType"}:
                self._start_capture("dei", tag, attrs, ns, node, qname=qname,
                    fact_ordinal=fact_ordinal)
            elif qname.namespace_uri in US_GAAP_NAMESPACES and qname.local_name in REVENUE_LOCAL_NAMES:
                self.revenue_fact_starts += 1
                if self.revenue_fact_starts > MAX_REVENUE_FACTS:
                    raise ParseFailure("parser_cap_exceeded")
                self._start_capture("revenue", tag, attrs, ns, node, qname=qname,
                    fact_ordinal=fact_ordinal)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.capture is not None:
            if self.capture.kind == "revenue" and sum(len(x) for x in self.capture.parts) + len(data) > MAX_NUMERIC_CHARS:
                raise ParseFailure("parser_cap_exceeded")
            self.capture.parts.append(data)
        if self.context is not None and data.strip():
            if self.segment_depth is not None: self.context["segment_nonempty"] = True
            if self.scenario_depth is not None: self.context["scenario_nonempty"] = True

    def _finish_capture(self):
        capture, self.capture = self.capture, None
        text = "".join(capture.parts).strip()
        if capture.kind == "identifier":
            self.context["entity_scheme"] = _bounded(capture.attrs.get("scheme"))
            self.context["entity_value"] = _bounded(text)
        elif capture.kind in {"startdate", "enddate", "instant"}:
            self.context[{"startdate": "start", "enddate": "end", "instant": "instant"}[capture.kind]] = text
        elif capture.kind == "explicitmember":
            dimension = _resolve_qname(capture.attrs.get("dimension"), capture.namespaces)
            member = _resolve_qname(text, capture.namespaces)
            if dimension is None or member is None:
                self.context["dimension_conflict"] = True
            else:
                key = (dimension.namespace_uri, dimension.local_name)
                value = (member.namespace_uri, member.local_name)
                if key in self.context["dimensions"] and self.context["dimensions"][key] != value:
                    self.context["dimension_conflict"] = True
                self.context["dimensions"][key] = value
        elif capture.kind == "measure":
            measure = _resolve_qname(text, capture.namespaces)
            if measure is None:
                self.unit["malformed"] = True
            else:
                self.unit[self.unit["side"]].append(measure)
        elif capture.kind == "dei":
            continued_at = capture.attrs.get("continuedat")
            format_value = capture.attrs.get("format")
            format_qname = _resolve_qname(format_value, capture.namespaces) if format_value else None
            self.dei.setdefault(capture.qname.local_name, []).append({
                "value": text, "ordinal": capture.fact_ordinal,
                "namespace": capture.qname.namespace_uri,
                "source_kind": "inline" if _resolve_qname(capture.end_tag, capture.namespaces).namespace_uri in IX_NAMESPACES else "instance",
                "context_ref_present": bool(capture.attrs.get("contextref")),
                "hidden": any(_local(tag) == "hidden" for tag in self.tags[:-1]),
                "format_category": ("absent" if not format_value else
                    f"resolved:{format_qname.namespace_uri}#{format_qname.local_name}" if format_qname else
                    "present_unresolved"), "continued_at": continued_at})
        elif capture.kind == "revenue":
            self.revenue_facts.append({"qname": capture.qname, "attrs": capture.attrs,
                "namespaces": capture.namespaces, "text": text,
                "fact_ordinal": capture.fact_ordinal, "node_ordinal": capture.node_ordinal})

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.capture is not None and tag == self.capture.end_tag and len(self.tags) == self.capture.depth:
            self._finish_capture()
        local = _local(tag)
        ns = self.namespaces[-1]
        tag_qname = _resolve_qname(tag, ns)
        if self.context is not None and tag_qname and tag_qname.namespace_uri == XBRLI:
            if local == "segment": self.segment_depth = None
            elif local == "scenario": self.scenario_depth = None
            elif local == "context":
                if len(self.contexts) >= MAX_CONTEXTS and self.context["id"] not in self.contexts:
                    raise ParseFailure("parser_cap_exceeded")
                self.contexts.setdefault(self.context["id"], []).append(self.context)
                self.context = None
        if self.unit is not None and tag_qname and tag_qname.namespace_uri == XBRLI:
            if local == "unit":
                if len(self.units) >= MAX_UNITS and self.unit["id"] not in self.units:
                    raise ParseFailure("parser_cap_exceeded")
                self.units.setdefault(self.unit["id"], []).append(self.unit)
                self.unit = None
            elif local in {"unitnumerator", "unitdenominator"}: self.unit["side"] = "numerator"
        if self.tags:
            self.tags.pop(); self.namespaces.pop()

    def close(self):
        super().close()
        if self.context is not None or self.unit is not None or self.capture is not None:
            raise ParseFailure("xbrl_parse_failure")


def _context(raw: dict):
    dimensions = tuple(sorted((
        (ExpandedQName(namespace_uri=key[0], local_name=key[1]),
         ExpandedQName(namespace_uri=value[0], local_name=value[1]))
        for key, value in raw["dimensions"].items()),
        key=lambda item: (item[0].namespace_uri, item[0].local_name)))
    if raw["instant"]:
        end = _date(raw["instant"]); kind, start = "instant", None
    elif raw["start"] or raw["end"]:
        start, end, kind = _date(raw["start"]), _date(raw["end"]), "duration"
    else:
        start = end = None; kind = "unavailable"
    return ContextIdentity(context_id=raw["id"], entity_scheme=raw["entity_scheme"],
        entity_value=raw["entity_value"], period_kind=kind, period_start=start,
        period_end=end, segment_present=raw["segment_present"],
        scenario_present=raw["scenario_present"], explicit_dimensions=dimensions,
        typed_dimension_count=raw["typed"])


def _unit(raw: dict):
    numerator = tuple(sorted(raw["numerator"], key=lambda q: (q.namespace_uri, q.local_name)))
    denominator = tuple(sorted(raw["denominator"], key=lambda q: (q.namespace_uri, q.local_name)))
    malformed = raw.get("malformed") or not numerator
    structural = "malformed" if malformed else "divide" if raw["divide"] or denominator else "measure"
    currency = "USD" if structural == "measure" and len(numerator) == 1 and not denominator and (
        numerator[0].namespace_uri == ISO4217 and numerator[0].local_name.upper() == "USD") else None
    return UnitIdentity(unit_id=raw["id"], numerator_measures=numerator,
        denominator_measures=denominator, structural_form=structural, currency=currency)


_PLAIN = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
_GROUPED = re.compile(r"^(?:0|[1-9]\d{0,2}(?:,\d{3})+)(?:\.\d+)?$")


def _numeric(raw: dict):
    attrs, text, ns = raw["attrs"], raw["text"].strip(), raw["namespaces"]
    nil_value = _namespaced_attr(attrs, ns, XSI, "nil")
    nil = str(nil_value or "").lower() in {"true", "1"}
    decimals = attrs.get("decimals")
    if decimals is None: return None, "precision_unproven"
    if decimals.upper() != "INF":
        try: precision = int(decimals)
        except ValueError: return None, "precision_unproven"
        if not -18 <= precision <= 18: return None, "precision_unproven"
    scale_text = attrs.get("scale", "0") or "0"
    try: scale = int(scale_text)
    except ValueError: return None, "malformed_numeric_value"
    if not -18 <= scale <= 18: return None, "malformed_numeric_value"
    sign_attr = attrs.get("sign")
    if sign_attr not in (None, "", "+", "-"):
        return None, "malformed_numeric_value"
    sign = "negative" if sign_attr == "-" else "positive" if sign_attr == "+" else "absent"
    format_value = attrs.get("format")
    transform = "absent"
    if format_value:
        qname = _resolve_qname(format_value, ns)
        if qname is None or qname.namespace_uri not in IxtNamespaces or qname.local_name != "num-dot-decimal":
            return None, "unsupported_numeric_transform"
        transform = f"{qname.namespace_uri}#{qname.local_name}"
    if nil: return NumericIdentity(nil=True, decimals=decimals, scale=scale, sign=sign,
        transform=transform, lexical_category="invalid"), "nil_fact"
    parenthesized = text.startswith("(") and text.endswith(")")
    if parenthesized: text = text[1:-1].strip()
    lexical_negative = text.startswith("-")
    if lexical_negative: text = text[1:]
    if parenthesized and lexical_negative or sign == "negative" and (parenthesized or lexical_negative):
        return None, "malformed_numeric_value"
    if _PLAIN.fullmatch(text): category = "decimal" if "." in text else "integer"
    elif _GROUPED.fullmatch(text): category = "grouped"
    else: return None, "malformed_numeric_value"
    try: value = Decimal(text.replace(",", ""))
    except InvalidOperation: return None, "malformed_numeric_value"
    if not value.is_finite(): return None, "malformed_numeric_value"
    if parenthesized or lexical_negative or sign == "negative": value = -value
    value *= Decimal(10) ** scale
    return NumericIdentity(nil=False, decimals=decimals, scale=scale, sign=sign,
        transform=transform, lexical_category="parenthesized" if parenthesized else category,
        normalized_value=value), None


def _safe_anchor_lexical(value):
    if len(value) > MAX_ANCHOR_DIAGNOSTIC_LEXICAL:
        return "over_length", None
    if any(ord(char) < 32 and char not in "\t\r\n" for char in value):
        return "control_characters", None
    return "safe", value


def _transformed_period_end(value, rows):
    categories = {row["format_category"] for row in rows}
    if categories == {"absent"}:
        parsed = _date(value)
        return (("parsed", parsed.isoformat(), "not_applicable", None, None) if parsed else
            ("parse_invalid", None, "not_applicable", None, "period_end_parse_invalid"))
    if "present_unresolved" in categories:
        return "parse_invalid", None, "unresolved", None, "period_end_transform_unresolved"
    if categories != {APPROVED_DEI_DATE_TRANSFORM} or any(
            row["source_kind"] != "inline" for row in rows):
        return "parse_invalid", None, "unsupported", None, "period_end_transform_unsupported"
    if len(value) > MAX_ANCHOR_DIAGNOSTIC_LEXICAL or any(
            ord(char) < 32 or (char.isspace() and char not in {" ", "\u00a0"}) for char in value):
        return "parse_invalid", None, "invalid_lexical", None, "period_end_transform_invalid_lexical"
    match = _MONTH_NAME_DATE.fullmatch(value)
    if not match:
        return "parse_invalid", None, "invalid_lexical", None, "period_end_transform_invalid_lexical"
    try:
        transformed = date(int(match.group(3)), _ENGLISH_MONTHS[match.group(1)],
            int(match.group(2))).isoformat()
    except ValueError:
        return "parse_invalid", None, "invalid_lexical", None, "period_end_transform_invalid_lexical"
    return "parsed", transformed, "applied", transformed, None


def _anchor_semantic(name, value, rows=()):
    if name == "DocumentFiscalYearFocus":
        try: return "parsed", str(int(value))
        except ValueError: return "parse_invalid", None
    if name == "DocumentFiscalPeriodFocus":
        normalized = value.upper()
        return ("parsed", normalized) if normalized in {"FY", "Q1", "Q2", "Q3", "Q4"} else ("parse_invalid", None)
    if name == "DocumentPeriodEndDate":
        outcome, normalized, _, _, _ = _transformed_period_end(value, rows)
        return outcome, normalized
    normalized = value.upper()
    return ("parsed", normalized) if normalized in {"10-Q", "10-Q/A", "10-K", "10-K/A"} else ("parse_invalid", None)


def _anchor_diagnostic(parser, document, name):
    rows = parser.dei.get(name, [])
    grouped = {}
    for row in rows:
        grouped.setdefault(row["value"].strip(), []).append(row)
    cap = (len(rows) > MAX_ANCHOR_DIAGNOSTIC_OBSERVATIONS
        or len(grouped) > MAX_ANCHOR_DIAGNOSTIC_DISTINCT)
    observations = []
    for value, occurrences in list(grouped.items())[:MAX_ANCHOR_DIAGNOSTIC_DISTINCT]:
        retained = occurrences[:MAX_ANCHOR_DIAGNOSTIC_OBSERVATIONS]
        lexical_category, lexical_value = _safe_anchor_lexical(value)
        if name == "DocumentPeriodEndDate":
            semantic_outcome, normalized, application, transformed, _ = (
                _transformed_period_end(value, retained))
        else:
            semantic_outcome, normalized = _anchor_semantic(name, value, retained)
            application, transformed = "not_applicable", None
        transforms = []
        continuation_categories = []
        for row in retained:
            transforms.append(row["format_category"][:256])
            continued_at = row["continued_at"]
            continuation_categories.append("not_applicable" if not continued_at else
                "target_present" if continued_at in parser.continuation_ids else "target_absent")
        observations.append(FiscalAnchorObservationDiagnostic(
            raw_lexical_category=lexical_category, raw_lexical_value=lexical_value,
            occurrence_count=len(occurrences), fact_ordinals=tuple(row["ordinal"] for row in retained),
            namespace_identities=tuple(sorted({row["namespace"] for row in retained}))[:16],
            source_kinds=tuple(sorted({row["source_kind"] for row in retained})),
            context_ref_present_count=sum(row["context_ref_present"] for row in occurrences),
            context_ref_absent_count=sum(not row["context_ref_present"] for row in occurrences),
            visibility_categories=tuple(sorted({"hidden" if row["hidden"] else "visible" for row in retained})),
            transform_categories=tuple(sorted(set(transforms)))[:16],
            transform_application_state=application,
            transformed_canonical_value=transformed,
            continued_at_present_count=sum(bool(row["continued_at"]) for row in occurrences),
            continued_at_absent_count=sum(not row["continued_at"] for row in occurrences),
            continuation_target_categories=tuple(sorted(set(continuation_categories))),
            semantic_outcome=semantic_outcome, normalized_semantic_value=normalized))
    if not rows: branch, comparison = "anchor_unavailable", "not_comparable"
    elif len(grouped) != 1: branch, comparison = "duplicate_distinct", "not_comparable"
    else:
        value = next(iter(grouped))
        rows_for_value = grouped[value]
        if name == "DocumentPeriodEndDate":
            outcome, normalized, _, _, transform_branch = _transformed_period_end(
                value, rows_for_value)
        else:
            outcome, normalized = _anchor_semantic(name, value, rows_for_value)
            transform_branch = None
        invalid = {"DocumentFiscalYearFocus": "fiscal_year_parse_invalid",
            "DocumentFiscalPeriodFocus": "fiscal_period_parse_invalid",
            "DocumentPeriodEndDate": "period_end_parse_invalid",
            "DocumentType": "document_type_parse_invalid"}
        expected = {"DocumentFiscalYearFocus": str(document.target_fiscal_year),
            "DocumentFiscalPeriodFocus": document.expected_role,
            "DocumentPeriodEndDate": document.report_period_end.isoformat(),
            "DocumentType": document.form}[name]
        mismatch = {"DocumentFiscalYearFocus": "year_mismatch",
            "DocumentFiscalPeriodFocus": "role_mismatch",
            "DocumentPeriodEndDate": "period_end_mismatch", "DocumentType": "form_mismatch"}
        if outcome == "parse_invalid":
            branch, comparison = transform_branch or invalid[name], "not_comparable"
        elif normalized != expected: branch, comparison = mismatch[name], "mismatch"
        else: branch, comparison = "anchor_valid", "match"
    return FiscalAnchorDiagnostic(required_local_name=name, observation_count=len(rows),
        distinct_stripped_raw_value_count=len(grouped), observations=tuple(observations),
        comparison=comparison, qualification_branch=branch, diagnostic_cap_exceeded=cap)


def _anchors(parser: _Parser, document: SelectedFilingDocument):
    names = ("DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus", "DocumentPeriodEndDate", "DocumentType")
    diagnostics = tuple(_anchor_diagnostic(parser, document, name) for name in names)
    diagnostic = FiscalAnchorSetDiagnostic(anchors=diagnostics,
        diagnostic_cap_exceeded=any(row.diagnostic_cap_exceeded for row in diagnostics))
    if any(name not in parser.dei for name in names): return None, "fiscal_anchor_unavailable", diagnostic
    values = {}
    ordinals = []
    for name in names:
        distinct = {row["value"].strip() for row in parser.dei[name]}
        if len(distinct) != 1: return None, "fiscal_anchor_conflict", diagnostic
        values[name] = next(iter(distinct)); ordinals.extend(row["ordinal"] for row in parser.dei[name])
    try: year = int(values["DocumentFiscalYearFocus"])
    except ValueError: return None, "fiscal_anchor_conflict", diagnostic
    period = values["DocumentFiscalPeriodFocus"].upper()
    end_outcome, end_normalized, _, _, _ = _transformed_period_end(
        values["DocumentPeriodEndDate"], parser.dei["DocumentPeriodEndDate"])
    end = _date(end_normalized) if end_outcome == "parsed" else None
    form = values["DocumentType"].upper()
    if period not in {"FY", "Q1", "Q2", "Q3", "Q4"} or end is None or form not in {"10-Q", "10-Q/A", "10-K", "10-K/A"}:
        return None, "fiscal_anchor_conflict", diagnostic
    if year != document.target_fiscal_year or period != document.expected_role or end != document.report_period_end or form != document.form:
        return None, "fiscal_anchor_conflict", diagnostic
    return DeiAnchor(fiscal_year=year, fiscal_period=period, period_end=end,
        document_type=form, fact_ordinals=tuple(sorted(ordinals))), None, diagnostic


def _entity_matches(context: ContextIdentity, cik: str):
    if context.entity_scheme not in SUPPORTED_ENTITY_SCHEMES: return False
    value = context.entity_value.strip()
    return value.isdigit() and value.zfill(10) == cik


def _period_reason(context: ContextIdentity, document: SelectedFilingDocument, anchor: DeiAnchor):
    if context.period_kind != "duration" or not context.period_start or not context.period_end:
        return "period_unavailable"
    duration = (context.period_end - context.period_start).days + 1
    if context.period_end != anchor.period_end or context.period_end != document.report_period_end:
        return "period_role_mismatch"
    if document.expected_role == "FY":
        if document.form not in {"10-K", "10-K/A"} or duration <= 105 or duration > 380:
            return "period_role_mismatch"
    elif document.form not in {"10-Q", "10-Q/A"} or not 70 <= duration <= 105:
        return "period_role_mismatch"
    return None


def _canonical_context(context: ContextIdentity):
    return json.dumps(context.model_dump(mode="json", exclude={"context_id"}), sort_keys=True)


def _canonical_unit(unit: UnitIdentity):
    return json.dumps(unit.model_dump(mode="json", exclude={"unit_id"}), sort_keys=True)


def _source(document, raw, contexts, units, anchor):
    reasons = []
    context_rows = contexts.get(raw["attrs"].get("contextref", ""), [])
    if not context_rows: context = None; reasons.append("context_missing")
    elif len({_canonical_context(row) for row in context_rows}) != 1:
        context = None; reasons.append("context_ambiguous")
    else:
        context = context_rows[0]
        if not _entity_matches(context, document.cik): reasons.append("entity_mismatch")
        if context.explicit_dimensions: reasons.append("dimensional_context_unsupported")
        if context.typed_dimension_count: reasons.append("typed_dimension_unsupported")
        period_reason = _period_reason(context, document, anchor)
        if period_reason: reasons.append(period_reason)
    unit_rows = units.get(raw["attrs"].get("unitref", ""), [])
    if not unit_rows: unit = None; reasons.append("unit_unavailable")
    elif len({_canonical_unit(row) for row in unit_rows}) != 1:
        unit = None; reasons.append("unit_mismatch")
    else:
        unit = unit_rows[0]
        if unit.currency != "USD":
            reasons.append("unsupported_currency" if unit.structural_form == "measure"
                and len(unit.numerator_measures) == 1 and not unit.denominator_measures else "unit_mismatch")
    numeric, numeric_reason = _numeric(raw)
    if numeric_reason: reasons.append(numeric_reason)
    return SecInlineRevenueSourceFact(expanded_qname=raw["qname"],
        fact_ordinal=raw["fact_ordinal"], node_ordinal=raw["node_ordinal"],
        occurrence_ordinals=(raw["fact_ordinal"],), context=context, unit=unit,
        numeric=numeric, rejection_reasons=tuple(dict.fromkeys(reasons)))


def _result(document, state, *, source_facts=(), operand=None, reasons=(), caps=(), anchor=None,
        anchor_diagnostic=None):
    return SecInlineRevenueOperandResult(state=state, selected_document=document,
        source_facts=tuple(source_facts), operand=operand,
        failure_reasons=tuple(dict.fromkeys(reasons)), cap_states=tuple(caps), dei_anchor=anchor,
        fiscal_anchor_diagnostic=anchor_diagnostic)


def qualify_inline_revenue_operand(document: SelectedFilingDocument, source: bytes):
    """Qualify at most one revenue operand from one caller-supplied selected document."""
    if document.selection_state != "selected":
        state = "ambiguous" if document.selection_state == "ambiguous" else "conflict" if document.selection_state == "conflict" else "unavailable"
        return _result(document, state, reasons=(f"selected_filing_{document.selection_state}",))
    if not isinstance(source, bytes) or not source:
        return _result(document, "unavailable", reasons=("source_document_unavailable",))
    if len(source) > MAX_SOURCE_BYTES:
        return _result(document, "unavailable", reasons=("source_too_large",), caps=("source_bytes",))
    try:
        text = source.decode("utf-8-sig", errors="strict")
        parser = _Parser(); parser.feed(text); parser.close()
    except (UnicodeDecodeError, ParseFailure, Exception) as exc:
        reason = exc.reason if isinstance(exc, ParseFailure) else "xbrl_parse_failure"
        return _result(document, "unavailable", reasons=(reason,),
            caps=(reason,) if reason in {"parser_cap_exceeded", "source_too_large"} else ())
    anchor, anchor_reason, anchor_diagnostic = _anchors(parser, document)
    if anchor_reason: return _result(document, "conflict" if anchor_reason.endswith("conflict") else "unavailable",
        reasons=(anchor_reason,), anchor_diagnostic=anchor_diagnostic)
    contexts = {}
    for identifier, rows in parser.contexts.items():
        converted = []
        for raw in rows:
            if raw["dimension_conflict"]:
                return _result(document, "conflict", reasons=("duplicate_conflict",), anchor=anchor,
                    anchor_diagnostic=anchor_diagnostic)
            converted.append(_context(raw))
        contexts[identifier] = converted
    units = {identifier: [_unit(raw) for raw in rows] for identifier, rows in parser.units.items()}
    if any(len({_canonical_context(row) for row in rows}) > 1 for rows in contexts.values()):
        return _result(document, "conflict", reasons=("context_ambiguous",), anchor=anchor,
            anchor_diagnostic=anchor_diagnostic)
    if any(len({_canonical_unit(row) for row in rows}) > 1 for rows in units.values()):
        return _result(document, "conflict", reasons=("duplicate_conflict", "unit_mismatch"), anchor=anchor,
            anchor_diagnostic=anchor_diagnostic)
    facts = [_source(document, raw, contexts, units, anchor) for raw in parser.revenue_facts]
    valid = [fact for fact in facts if not fact.rejection_reasons]
    if not valid:
        reasons = [reason for fact in facts for reason in fact.rejection_reasons]
        return _result(document, "unavailable", source_facts=facts,
            reasons=tuple(reasons) or ("concept_unavailable",), anchor=anchor,
            anchor_diagnostic=anchor_diagnostic)
    if len(valid) > MAX_COMPETING_FACTS:
        return _result(document, "unavailable", source_facts=facts,
            reasons=("parser_cap_exceeded",), caps=("competing_facts",), anchor=anchor,
            anchor_diagnostic=anchor_diagnostic)
    grouped = {}
    for fact in valid:
        key = (fact.expanded_qname.model_dump_json(), _canonical_context(fact.context),
            _canonical_unit(fact.unit), fact.numeric.model_dump_json())
        grouped.setdefault(key, []).append(fact)
    collapsed = []
    for rows in grouped.values():
        first = rows[0]
        collapsed.append(first.model_copy(update={"occurrence_ordinals": tuple(
            sorted(row.fact_ordinal for row in rows))}))
    if len(collapsed) != 1:
        concepts = {row.expanded_qname.model_dump_json() for row in collapsed}
        base = {(row.expanded_qname.model_dump_json(), _canonical_context(row.context),
            _canonical_unit(row.unit)) for row in collapsed}
        if len(concepts) > 1:
            return _result(document, "ambiguous", source_facts=facts,
                reasons=("ambiguous_concept",), anchor=anchor, anchor_diagnostic=anchor_diagnostic)
        if len(base) == 1:
            return _result(document, "conflict", source_facts=facts,
                reasons=("duplicate_conflict",), anchor=anchor, anchor_diagnostic=anchor_diagnostic)
        return _result(document, "ambiguous", source_facts=facts,
            reasons=("operand_ambiguous",), anchor=anchor, anchor_diagnostic=anchor_diagnostic)
    fact = collapsed[0]
    operand = SecInlineRevenueOperand(role=document.expected_role,
        target_fiscal_year=document.target_fiscal_year, ticker=document.ticker,
        issuer=document.issuer, cik=document.cik, expanded_qname=fact.expanded_qname,
        context=fact.context, unit=fact.unit, numeric=fact.numeric,
        accession=document.accession, form=document.form, filing_date=document.filing_date,
        acceptance_time=document.acceptance_time, report_period_end=document.report_period_end,
        primary_document=document.primary_document, source_url=document.source_url,
        source_kind=document.source_kind, selector_policy=document.selector_policy,
        fact_ordinal=fact.fact_ordinal, node_ordinal=fact.node_ordinal,
        occurrence_ordinals=fact.occurrence_ordinals, unit_id=fact.unit.unit_id,
        context_id=fact.context.context_id, dei_anchor=anchor,
        duplicate_count=len(fact.occurrence_ordinals)-1)
    return _result(document, "qualified", source_facts=facts, operand=operand, anchor=anchor,
        anchor_diagnostic=anchor_diagnostic)


def _matching_equivalence_record(a, b, policy):
    if not isinstance(a, ExpandedQName) or not isinstance(b, ExpandedQName):
        return None
    for record in policy:
        if not isinstance(record, TaxonomyConceptEquivalence):
            continue
        if a.local_name != record.local_name or b.local_name != record.local_name:
            continue
        pair = (a.namespace_uri, b.namespace_uri)
        if pair == (record.from_namespace, record.to_namespace):
            return record
        if record.symmetric_for_identity and pair == (record.to_namespace, record.from_namespace):
            return record
    return None


def revenue_concepts_equivalent(a, b, policy=CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES):
    """Compare exact QNames or one explicitly certified edge; infer nothing else."""
    if not isinstance(a, ExpandedQName) or not isinstance(b, ExpandedQName):
        return False
    if not a.namespace_uri or not a.local_name or not b.namespace_uri or not b.local_name:
        return False
    if a == b:
        return True
    return _matching_equivalence_record(a, b, policy) is not None


def _concept_identity_diagnostic(operands, policy, equivalence_policy_version):
    qnames = tuple(row.expanded_qname for row in operands)
    if all(qname == qnames[0] for qname in qnames[1:]):
        state, records = "exact_qname", ()
    else:
        used = []
        for qname in qnames[1:]:
            if qname == qnames[0]:
                continue
            record = _matching_equivalence_record(qnames[0], qname, policy)
            if record is None:
                return RevenueConceptIdentityDiagnostic(state="mismatch",
                    original_qnames=qnames, equivalence_policy_version=equivalence_policy_version)
            if record.record_identity not in {row.record_identity for row in used}:
                used.append(record)
        state, records = "certified_cross_version_equivalence", tuple(
            CertifiedConceptEquivalenceUse(record_identity=row.record_identity,
                source_package_sha256=row.source_package_sha256,
                target_package_sha256=row.target_package_sha256) for row in used)
    return RevenueConceptIdentityDiagnostic(state=state, original_qnames=qnames,
        equivalence_policy_version=equivalence_policy_version, certified_records=records)


def validate_revenue_operand_partition(*, annual, q1, q2, q3,
        concept_equivalence_policy=CERTIFIED_REVENUE_CONCEPT_EQUIVALENCES,
        partition_policy_version=PARTITION_IDENTITY_POLICY_VERSION,
        equivalence_policy_version=EQUIVALENCE_POLICY_VERSION):
    """Validate only four-operand identity and fiscal geometry; never revenue arithmetic."""
    operands = (annual, q1, q2, q3)
    if any(row is None for row in operands):
        return RevenueOperandPartitionResult(partition_policy_version=partition_policy_version,
            state="unavailable", reasons=("operand_missing",))
    reasons = []
    concept_identity = _concept_identity_diagnostic(
        operands, concept_equivalence_policy, equivalence_policy_version)
    if (annual.role, q1.role, q2.role, q3.role) != ("FY", "Q1", "Q2", "Q3"):
        reasons.append("operand_role_mismatch")
    comparable = lambda row: (_canonical_unit(row.unit), row.context.entity_scheme,
        row.context.entity_value, row.context.explicit_dimensions,
        row.context.typed_dimension_count, row.accounting_basis, row.target_fiscal_year)
    if (concept_identity.state == "mismatch"
            or len({comparable(row) for row in operands}) != 1):
        reasons.append("operand_identity_mismatch")
    if any(row.context.explicit_dimensions or row.context.typed_dimension_count for row in operands):
        reasons.append("scope_mismatch")
    starts = [row.context.period_start for row in operands]
    ends = [row.context.period_end for row in operands]
    if any(value is None for value in starts + ends):
        return RevenueOperandPartitionResult(partition_policy_version=partition_policy_version,
            state="unavailable", reasons=("period_unavailable",), concept_identity=concept_identity)
    for row in (q1, q2, q3):
        duration = (row.context.period_end-row.context.period_start).days+1
        if not 70 <= duration <= 105: reasons.append("quarter_duration_invalid")
    if annual.context.period_start != q1.context.period_start: reasons.append("annual_q1_start_mismatch")
    if q1.context.period_end + timedelta(days=1) != q2.context.period_start: reasons.append("q1_q2_gap_or_overlap")
    if q2.context.period_end + timedelta(days=1) != q3.context.period_start: reasons.append("q2_q3_gap_or_overlap")
    if q3.context.period_end >= annual.context.period_end: reasons.append("residual_period_unavailable")
    residual_start, residual_end = q3.context.period_end + timedelta(days=1), annual.context.period_end
    residual_days = (residual_end-residual_start).days+1
    if not 70 <= residual_days <= 105: reasons.append("residual_duration_invalid")
    if reasons: return RevenueOperandPartitionResult(partition_policy_version=partition_policy_version,
        state="conflict", reasons=tuple(dict.fromkeys(reasons)), concept_identity=concept_identity)
    return RevenueOperandPartitionResult(partition_policy_version=partition_policy_version,
        state="valid", concept_identity=concept_identity, residual_period_start=residual_start,
        residual_period_end=residual_end, residual_duration_days=residual_days)
