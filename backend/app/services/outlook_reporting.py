"""Reporting metadata extraction and point-in-time diagnostics, independent of scoring."""
from datetime import datetime
from html.parser import HTMLParser
import re

from app.models.outlook_reporting import (
    KnownFiscalCalendar, ReportingIdentity, ReportingPeriodIdentity, ReportingProvenance,
    ReportingRevision, consecutive, quarter_index,
)
from app.services.outlook_earnings import gaap_margin_comparisons

ORDINAL = r"first|second|third|fourth"
QUARTERS = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = rf"(?:{MONTH} \d{{1,2}},? \d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})"


def _date(value):
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _period_labels(text):
    """Explicit labels only. No publication dates, document IDs or ticker heuristics."""
    found = set()
    for match in re.finditer(r"\bfourth[- ]quarter and (?:full[- ]year|fiscal(?: year)?) (\d{4})\b", text, re.I):
        found.update(((int(match[1]), "Q4"), (int(match[1]), "FY")))
    for match in re.finditer(r"\bQ([1-4])\s+FY(\d{4}|\d{2})\b", text, re.I):
        found.add((int(match[2]) + (2000 if len(match[2]) == 2 else 0), "Q" + match[1]))
    for pattern, year_group, quarter_group in (
        (rf"\bfiscal (\d{{4}}) ({ORDINAL})[- ]quarter\b", 1, 2),
        (rf"\b({ORDINAL})[- ]quarter (?:of )?(?:fiscal (?:year )?)?(\d{{4}})\b", 2, 1),
    ):
        for match in re.finditer(pattern, text, re.I):
            found.add((int(match[year_group]), QUARTERS[match[quarter_group].lower()]))
    for match in re.finditer(r"\b(?:full[- ]year|fiscal year) (\d{4})\b", text, re.I):
        found.add((int(match[1]), "FY"))
    return found


def _provenance(doc, method, basis):
    return ReportingProvenance(method=method, source_url=str(doc.source_url), document_id=doc.id,
        accession=doc.metadata.get("accession"), basis=basis)


class _DEI(HTMLParser):
    """Read explicit same-context DEI facts from already retrieved HTML only."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.facts = {}
        self.active = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        name = attrs.get("name", "")
        if tag == "ix:nonnumeric" and name.startswith("dei:") and attrs.get("contextref") and attrs.get("xsi:nil") != "true":
            self.active = (name.split(":")[-1], attrs.get("contextref", ""), [])

    def handle_data(self, data):
        if self.active:
            self.active[2].append(data)

    def handle_endtag(self, tag):
        if tag == "ix:nonnumeric" and self.active:
            name, context, parts = self.active
            self.facts.setdefault(context, {}).setdefault(name, set()).add("".join(parts).strip())
            self.active = None


def inline_reporting_identity(doc, html):
    """8-K DEI dates describe an event, not necessarily the financial reporting period."""
    if doc.source_quality != "primary_authoritative" or doc.metadata.get("form") not in ("10-Q", "10-K", "10-Q/A", "10-K/A"):
        return ReportingIdentity()
    parser = _DEI()
    parser.feed(html)
    candidates = []
    for facts in parser.facts.values():
        names = ("DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus", "DocumentPeriodEndDate")
        if not all(name in facts for name in names):
            continue
        if any(len(facts[name]) != 1 for name in names):
            return ReportingIdentity(status="conflict", reason="conflicting_structured_reporting_facts")
        year, period, end = [next(iter(facts[name])) for name in names]
        if not re.fullmatch(r"\d{4}", year) or period not in ("Q1", "Q2", "Q3", "Q4", "FY") or not _date(end):
            return ReportingIdentity(reason="invalid_structured_reporting_facts")
        if not 1900 <= int(year) <= 2200:
            return ReportingIdentity(reason="invalid_structured_reporting_facts")
        if (doc.metadata["form"].startswith("10-K")) != (period == "FY"):
            return ReportingIdentity(status="conflict", reason="structured_period_form_conflict")
        candidates.append(ReportingPeriodIdentity(ticker=doc.ticker, fiscal_year=int(year),
            fiscal_period=period, period_end=_date(end)))
    unique = {p.model_dump_json(): p for p in candidates}
    if len(unique) > 1:
        return ReportingIdentity(status="conflict", reason="conflicting_structured_reporting_contexts")
    if not unique:
        return ReportingIdentity()
    period = next(iter(unique.values()))
    if period.period_end > doc.published_at.date():
        return ReportingIdentity(reason="reporting_period_ends_after_publication")
    revision = ReportingRevision(kind="amendment", basis="Explicit amended form; original filing not linked") if doc.metadata["form"].endswith("/A") else None
    return ReportingIdentity(status="authoritative", reason="explicit_structured_reporting_facts", periods=(period,),
        provenance=(_provenance(doc, "inline_xbrl_dei", "DocumentFiscalYearFocus; DocumentFiscalPeriodFocus; DocumentPeriodEndDate"),),
        revision=revision)


def resolve_reporting_identity(doc):
    if doc.source_quality != "primary_authoritative":
        return ReportingIdentity(reason="not_primary_authoritative")
    if doc.reporting_identity is not None:
        return doc.reporting_identity
    # Only result headings/reporting introductions qualify. Forecast sentences do not.
    segments = [doc.title] + re.split(r"(?<=[.!?])\s+|[\r\n]+", doc.extracted_text[:4000])
    qualified = [s for s in segments if re.search(r"\b(?:results|reported|announced|reports)\b", s, re.I)
        and not re.search(r"\b(?:outlook|guidance|expects?|will|forecast|anticipates?)\b", s, re.I)]
    labels = set().union(*(_period_labels(s) for s in qualified)) if qualified else set()
    # A validated GAAP summary identifies current vs comparison columns without guessing.
    table_labels = set()
    for numeric in gaap_margin_comparisons(doc.tables):
        table_labels.update(_period_labels(numeric["current_period"]))
    if labels and table_labels and not table_labels <= labels:
        return ReportingIdentity(status="conflict", reason="heading_table_period_conflict")
    method = "explicit_primary_text" if labels else "validated_gaap_header"
    labels = labels or table_labels
    if not labels:
        return ReportingIdentity()
    if any(not 1900 <= year <= 2200 for year, _ in labels):
        return ReportingIdentity(reason="invalid_reporting_year")
    if len({year for year, _ in labels}) > 1 or len([p for _, p in labels if p != "FY"]) > 1:
        return ReportingIdentity(status="conflict", reason="multiple_reported_quarters")
    periods = []
    for year, period in sorted(labels):
        ends = set()
        if period != "FY":
            ordinal = next(word for word, q in QUARTERS.items() if q == period)
            pattern = rf"\b{ordinal}[- ]quarter(?: (?:of )?(?:fiscal (?:year )?)?\d{{4}})? ended ({DATE})"
        else:
            pattern = rf"\b(?:full[- ]year|fiscal year)(?: \d{{4}})? ended ({DATE})"
        for segment in qualified:
            ends.update(_date(m[1]) for m in re.finditer(pattern, segment, re.I)
                if not re.search(r"\b(?:compared|prior|previous|last year)\b", segment[:m.start()], re.I))
        ends.discard(None)
        if len(ends) > 1:
            return ReportingIdentity(status="conflict", reason="conflicting_period_end_dates")
        end = next(iter(ends), None)
        if end and end > doc.published_at.date():
            return ReportingIdentity(reason="reporting_period_ends_after_publication")
        periods.append(ReportingPeriodIdentity(ticker=doc.ticker, fiscal_year=year, fiscal_period=period, period_end=end))
    basis = " | ".join(qualified)[:1200] if method == "explicit_primary_text" else "Validated current fiscal-quarter column in GAAP comparison table"
    return ReportingIdentity(status="authoritative", reason="explicit_reporting_identity", periods=tuple(periods),
        provenance=(_provenance(doc, method, basis),))


def fact_reporting_identity(doc, numeric):
    identity = resolve_reporting_identity(doc)
    if len(identity.periods) <= 1:
        return identity
    labels = _period_labels(numeric.get("current_period", ""))
    matched = tuple(p for p in identity.periods if (p.fiscal_year, p.fiscal_period) in labels)
    if len(matched) == 1:
        return identity.model_copy(update={"periods": matched})
    return ReportingIdentity(reason="annual_and_quarterly_fact_scope_ambiguous", provenance=identity.provenance)


def reporting_diagnostics(documents, *, now, relationships=(), gaps=()):
    """Source-period inventory; distinct period count is NOT an aggregation vote count."""
    documents = sorted((d for d in documents if d.published_at <= now and d.observed_at <= now), key=lambda d: d.id)
    if len({d.ticker for d in documents}) > 1:
        raise ValueError("Reporting diagnostics require one issuer")
    rows, by_key, provenance = [], {}, []
    visible = {d.id for d in documents}
    identities = {d.id: resolve_reporting_identity(d) for d in documents}
    active_relationships = [r.model_dump() for r in relationships if r.original in visible and r.subsequent in visible]
    for doc in documents:
        revision = identities[doc.id].revision
        if revision is None:
            continue
        originals = [d.id for d in documents if d.id != doc.id and (
            d.id == revision.original_document_id or
            (revision.original_accession is not None and d.metadata.get("accession") == revision.original_accession))]
        if len(originals) == 1:
            active_relationships.append({"original": originals[0], "subsequent": doc.id, "kind": revision.kind,
                "reporting_period": ", ".join(p.key for p in identities[doc.id].periods), "note": revision.basis})
    superseded = {r["original"] for r in active_relationships if r["kind"] in ("amendment", "correction", "supersession")}
    for doc in documents:
        identity = identities[doc.id]
        rows.append({"document_id": doc.id, "published_at": doc.published_at.isoformat(),
            "observed_at": doc.observed_at.isoformat(), "filing_date": doc.metadata.get("filing_date"),
            "accession": doc.metadata.get("accession"),
            "superseded_in_period_inventory": doc.id in superseded,
            "identity": identity.model_dump(mode="json"),
            "publication_lag_days": {p.key: (doc.published_at.date()-p.period_end).days if p.period_end else None for p in identity.periods}})
        if identity.status == "authoritative" and doc.id not in superseded:
            for period in identity.periods:
                by_key.setdefault(period.key, []).append(period)
            provenance.extend(identity.provenance)
    periods, conflicts = [], []
    for key, variants in sorted(by_key.items()):
        ends = {p.period_end for p in variants if p.period_end}
        starts = {p.period_start for p in variants if p.period_start}
        if len(ends) > 1 or len(starts) > 1:
            conflicts.append(key)
        else:
            periods.append(variants[0].model_copy(update={"period_end": next(iter(ends), None), "period_start": next(iter(starts), None)}))
    quarters = sorted((p for p in periods if p.fiscal_period != "FY"), key=quarter_index)
    current = quarters[-1] if quarters else None
    prior = quarters[-2] if len(quarters) > 1 else None
    missing = []
    for left, right in zip(quarters, quarters[1:]):
        for index in range(quarter_index(left)+1, quarter_index(right)):
            missing.append(f"{right.ticker}:FY{index//4}:Q{index%4+1}")
    # Annual-only and unresolved sources can hide a newer quarter: expose uncertainty.
    unknown = [r["document_id"] for r in rows if r["identity"]["status"] != "authoritative"]
    def adjacent_key(offset):
        if current is None:
            return None
        index = quarter_index(current) + offset
        return f"{current.ticker}:FY{index//4}:Q{index%4+1}"
    return {"sources": rows, "distinct_periods": len(periods), "current_known_quarter": current.key if current else None,
        "previous_known_quarter": prior.key if prior else None, "consecutive": consecutive(prior, current),
        "immediately_previous_quarter": prior.key if consecutive(prior, current) else None,
        "expected_previous_quarter": adjacent_key(-1), "next_quarter_identity": adjacent_key(1),
        "reporting_gap_quarters": quarter_index(current)-quarter_index(prior)-1 if current and prior else None,
        "missing_periods": [{"period": key, "cause": "undetermined_missing_report_or_retrieval_gap"} for key in missing],
        "declared_gaps": [g.model_dump(mode="json") for g in gaps if g.known_at <= now],
        "unknown_document_ids": unknown, "conflicting_periods": conflicts, "relationships": active_relationships,
        "calendar": KnownFiscalCalendar(ticker=documents[0].ticker if documents else "UNKNOWN",
            known_periods=tuple(periods), provenance=tuple(provenance)).model_dump(mode="json")}


def format_reporting(diagnostics):
    lines = [f"Reporting periods: current={diagnostics['current_known_quarter'] or 'unknown'}; "
        f"previous={diagnostics['previous_known_quarter'] or 'unknown'}; consecutive={diagnostics['consecutive']}; "
        f"distinct={diagnostics['distinct_periods']} (metadata, not scoring votes)"]
    for row in diagnostics["sources"]:
        identity = row["identity"]
        labels = ", ".join(f"FY{p['fiscal_year']} {p['fiscal_period']} end={p['period_end'] or 'unknown'}" for p in identity["periods"])
        lines.append(f"  {row['document_id']}: {labels or 'unknown'}; {identity['status']}: {identity['reason']}; "
            f"published={row['published_at']}; observed={row['observed_at']}")
        if identity["provenance"]:
            lines.append("    identity_source=" + ", ".join(p["method"] for p in identity["provenance"]) +
                f"; publication_lag_days={row['publication_lag_days']}")
    for gap in diagnostics["missing_periods"]:
        lines.append(f"  Missing {gap['period']}: {gap['cause']}")
    return "\n".join(lines)


def evidence_reporting_diagnostics(records, *, now):
    """Read request-local retained document provenance, including uninterpreted documents."""
    from app.models.outlook_document import SourceDocument
    documents = {}
    for record in records:
        rows = record.source_details.get("sec_diagnostics", {}).get("reporting_documents", [])
        if not rows and "reporting_identity" in record.source_details:
            rows = [{"document_id": record.source_details.get("source_document_id", record.id),
                "published_at": record.published_at, "observed_at": record.observed_at,
                "identity": record.source_details["reporting_identity"]}]
        for row in rows:
            documents[row["document_id"]] = SourceDocument(id=row["document_id"], ticker=record.ticker,
                title="Retained reporting provenance", published_at=row["published_at"], observed_at=row["observed_at"],
                source_name=record.source, source_type=record.source_type, source_url=record.source_url,
                source_quality=record.source_quality, provider=record.raw_provider,
                provider_document_id=record.raw_provider_id or row["document_id"],
                reporting_identity=ReportingIdentity.model_validate(row["identity"]),
                metadata={"filing_date": row.get("filing_date"), "accession": row.get("accession")})
    return reporting_diagnostics(documents.values(), now=now)
