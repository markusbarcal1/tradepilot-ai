"""Pure offline replay: no configured providers, IO, wall clock, or network calls."""
from math import fsum, isclose

from app.models.outlook import OutlookMetadata
from app.services.outlook import aggregate_outlook
from app.services.outlook_evidence import assess_evidence
from app.services.outlook_interpreter import DeterministicOutlookInterpreter
from app.services.outlook_diagnostics import availability_diagnostics
from app.services.outlook_structured.documents import parse_filing, earnings_exhibit_url
from app.services.outlook_reporting import inline_reporting_identity, reporting_diagnostics


def assertion_matches(assertion, record):
    numeric = record.source_details.get("numeric", {})
    return (record.category == assertion.category and record.event_type == assertion.event_type
            and (assertion.source_id is None or assertion.source_id in
                 (record.id, record.source_details.get("source_document_id")))
            and (assertion.metric is None or numeric.get("metric") == assertion.metric)
            and (assertion.sign is None or (1 if record.impact > 0 else -1 if record.impact < 0 else 0) == assertion.sign)
            and (assertion.qualifier is None or assertion.qualifier in record.summary)
            and (assertion.accounting_basis is None or numeric.get("basis") == assertion.accounting_basis))


def replay_documents(package, assessment_at):
    """Same source visibility and extraction boundary for scoring and identity diagnostics."""
    documents, retrieval_checks = [], []
    for source in package.sources:
        doc = source.document
        if doc.published_at > assessment_at or doc.observed_at > assessment_at:
            continue
        if source.html is not None:
            parsed = parse_filing(source.html)
            if source.expected_exhibit_url is not None:
                retrieval_checks.append(earnings_exhibit_url(str(doc.source_url), parsed.links) == source.expected_exhibit_url)
            identity = inline_reporting_identity(doc, source.html)
            doc = doc.model_copy(update={"extracted_text": parsed.text, "tables": parsed.tables,
                "reporting_identity": identity if identity.reason != "source_lacks_authoritative_reporting_identity" else None})
        documents.append(doc)
    return documents, retrieval_checks


def replay(package, assessment_at):
    records = [e for e in package.evidence if e.published_at <= assessment_at and e.observed_at <= assessment_at]
    interpreter = DeterministicOutlookInterpreter()
    documents, retrieval_checks = replay_documents(package, assessment_at)
    for doc in documents:
        records.extend(interpreter.interpret(package.context.ticker, [doc], package.context))
    categories, contributions = assess_evidence(package.context.ticker, records, now=assessment_at)
    response = aggregate_outlook(package.context.ticker, categories,
        OutlookMetadata(provider="offline_corpus", uses_placeholder_data=False))
    return records, contributions, response, retrieval_checks


def financial_snapshot(categories, contributions):
    return {key: {"events": cat.evidence_count, "status": cat.status,
                  "label": cat.label.value if cat.label else None, "confidence": cat.confidence,
                  "support": fsum(c.weight for c in contributions if c.representative.category == key),
                  "direction": (fsum(c.contribution for c in contributions if c.representative.category == key)
                                / cat.evidence_count if cat.evidence_count else None)}
            for key, cat in categories.items()}


def same_snapshot(a, b):
    return all(isclose(a[k][field], b[k][field], rel_tol=1e-12, abs_tol=1e-12)
               if isinstance(a[k][field], float) and isinstance(b[k][field], (int, float))
               else a[k][field] == b[k][field] for k in a for field in a[k])


def evaluate_package(package):
    rows = []
    for point in package.replays:
        records, contributions, response, retrieval = replay(package, point.assessment_at)
        snapshot = financial_snapshot(response.categories, contributions)
        checks = []
        def check(kind, name, passed):
            checks.append({"kind": kind, "name": name, "passed": bool(passed)})
        reporting = reporting_diagnostics(replay_documents(package, point.assessment_at)[0], now=point.assessment_at,
            relationships=package.relationships, gaps=package.reporting_gaps)
        if point.expected_reporting_periods is not None:
            actual = {f"{p['ticker']}:FY{p['fiscal_year']}:{p['fiscal_period']}" for p in reporting['calendar']['known_periods']}
            check("reporting_identity", "period_inventory", actual == set(point.expected_reporting_periods))
        if point.expected_missing_periods is not None:
            check("reporting_identity", "missing_periods", {p['period'] for p in reporting['missing_periods']} == set(point.expected_missing_periods))
        for i, ok in enumerate(retrieval):
            check("extraction", f"exhibit_destination:{i}", ok)
        # Assertions are checked only for sources observable at this replay point.
        visible = {e.id for e in records} | {e.source_details.get("source_document_id") for e in records}
        for i, assertion in enumerate(package.supported_assertions):
            source = next((s.document for s in package.sources if s.document.id == assertion.source_id), None)
            if source and (source.published_at > point.assessment_at or source.observed_at > point.assessment_at):
                continue
            check("extraction", f"supported:{i}", any(assertion_matches(assertion, e) for e in records))
        for i, assertion in enumerate(package.unsupported_assertions):
            check("extraction", f"unsupported:{i}", not any(assertion_matches(assertion, e) for e in records))
        for i, group in enumerate(package.expected_duplicate_groups):
            if not set(group) <= visible:
                continue
            clusters = [{r.id for r in c.evidence} | {r.source_details.get("source_document_id") for r in c.evidence}
                        for c in contributions]
            check("clustering", f"duplicate_group:{i}", sum(set(group) <= c for c in clusters) == 1)
        for outcome in point.outcomes:
            actual = snapshot[outcome.category]
            check("clustering", f"{outcome.category}:events", actual["events"] == outcome.events)
            check("availability", f"{outcome.category}:status", actual["status"] == outcome.status)
            if outcome.label is not None:
                check("availability", f"{outcome.category}:label", actual["label"] == outcome.label)
            for key in ("support", "direction"):
                bounds = getattr(outcome, key)
                if bounds is not None:
                    check("arithmetic", f"{outcome.category}:{key}", actual[key] is not None and
                          bounds[0]-1e-12 <= actual[key] <= bounds[1]+1e-12)
        check("coverage", "available_categories", response.available_categories == point.available_categories)
        check("coverage", "overall_status", response.status == point.overall_status)
        if point.overall_label:
            check("coverage", "overall_label", response.label.value == point.overall_label if response.label else False)
        # Metamorphic checks use actual extracted records, never a second scoring implementation.
        for name, variant in (
            ("input_order", list(reversed(records))),
            ("evidence_ids", [e.model_copy(update={"id": f"renamed-{len(records)-i}"}) for i, e in enumerate(records)]),
        ):
            cats, cs = assess_evidence(package.context.ticker, variant, now=point.assessment_at)
            check("invariant", name, same_snapshot(snapshot, financial_snapshot(cats, cs)))
        rows.append({"name": point.name, "assessment_at": point.assessment_at.isoformat(),
            "reporting_diagnostics": reporting,
            "availability_diagnostics": availability_diagnostics(response.categories, contributions, now=point.assessment_at),
            "checks": checks, "categories": snapshot, "overall_status": response.status,
            "overall_label": response.label.value if response.label else None,
            "events": [{"weight": c.weight, "contribution": c.contribution, "exclusion": c.exclusion,
                        "effective_impact": c.contribution / c.weight if c.weight else None,
                        "event_confidence": c.event_confidence,
                        "evidence_ids": [e.id for e in c.evidence],
                        "factors": [{"identity": f.identity, "weight": f.weight, "freshness": f.freshness,
                                     "impact": int(f.representative.impact), "confidence": f.representative.confidence,
                                     "materiality": f.representative.materiality,
                                     "basis": f.representative.summary,
                                     "exclusion": f.exclusion, "evidence_ids": [e.id for e in f.evidence]}
                                    for f in c.factors]} for c in contributions]})
    return {"id": package.id, "tags": package.semantic_tags, "replays": rows,
            "relationships": [r.model_dump() for r in package.relationships]}
