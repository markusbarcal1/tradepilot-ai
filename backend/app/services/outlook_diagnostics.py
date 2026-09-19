"""Operator-only availability explanations; never part of the public Outlook API."""
from collections import Counter
from dataclasses import replace
from math import fsum

from app.services.outlook import aggregate_outlook
from app.services.outlook_evidence import assess_evidence, availability_failures
from app.services.outlook_factors import event_values
from app.services.outlook_policy import DEFAULT_EVIDENCE_POLICY


def _raw_support(event):
    if event.factors:
        # Retain exactly the production-supported factors; remove decay only.
        factors = tuple(replace(f, freshness=1.0, weight=f.weight / f.freshness)
                        for f in event.factors if f.exclusion is None)
        return event_values(factors)[0]
    return event.weight / event.freshness


def _event_age(event, now, policy):
    # Same authoritative, confidence/materiality-qualified publication basis as
    # production factor freshness. Secondary syndication cannot refresh this age.
    if event.factors:
        records = []
        for factor in event.factors:
            if factor.exclusion is not None:
                continue
            primary = [r for r in factor.evidence if r.source_quality == "primary_authoritative"]
            records.extend(r for r in primary or factor.evidence if r.scoring_eligible
                           and r.confidence >= policy.minimum_confidence
                           and r.materiality >= policy.minimum_materiality)
    else:
        primary = [r for r in event.evidence if r.source_quality == "primary_authoritative"]
        records = primary or event.evidence
    return (now - min(r.published_at for r in records)).total_seconds() / 86400


def availability_diagnostics(categories, contributions, *, now, policy=DEFAULT_EVIDENCE_POLICY):
    """Explain an assessment using its actual production contributions and clock."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Assessment time must be timezone-aware")
    result = {}
    for key, category in categories.items():
        events = [c for c in contributions if c.representative.category == key]
        supported = [c for c in events if c.exclusion is None]
        effective = fsum(c.weight for c in supported)
        exclusions = Counter(c.exclusion for c in events if c.exclusion is not None)
        reasons = []
        if category.status == "insufficient_data":
            reasons.extend(availability_failures(len(supported), effective, policy))
            if not events:
                reasons.append("no_source_observations")
            elif not supported:
                # Future observations are filtered before clustering by production.
                if all(c.exclusion == "expired_or_not_yet_observed" for c in events):
                    reasons.append("all_evidence_stale")
                reasons.extend(sorted(exclusions))
        elif category.status == "not_material":
            reasons.append("not_material")
        elif category.status == "unavailable":
            reasons.append("provider_not_connected_or_configured")
        elif category.status == "error":
            reasons.append("provider_error")
        ages = [_event_age(c, now, policy) for c in supported]
        result[key] = {
            "supported_events": len(supported),
            "source_observations": sum(len(c.evidence) for c in events),
            "raw_support": fsum(_raw_support(c) for c in supported),
            "effective_support": effective,
            "minimum_support": policy.minimum_weight,
            "minimum_events": policy.minimum_events,
            "freshest_event_age_days": min(ages) if ages else None,
            "oldest_event_age_days": max(ages) if ages else None,
            "availability": category.status,
            "reasons": reasons,
            "excluded_events": dict(sorted(exclusions.items())),
        }
    return result


def inspect_snapshot(result, *, now, policy=DEFAULT_EVIDENCE_POLICY):
    """Reassess retained observations at one exact clock without refetching sources.

    Production's public response has no assessment timestamp. Reassessment makes
    the displayed result and diagnostic weights agree even at expiry boundaries.
    Provider unavailable/error states and placeholder behavior remain intact.
    """
    records = [e for category in result.categories.values() for e in category.evidence]
    categories, contributions = assess_evidence(result.ticker, records, now=now, policy=policy)
    if not result.metadata.uses_placeholder_data:
        complete = {key: categories[key] if any(e.raw_provider != "fomc" for e in category.evidence) else category
                    for key, category in result.categories.items()}
        result = aggregate_outlook(result.ticker, complete, result.metadata, policy=policy).model_copy(
            update={"event_intelligence": result.event_intelligence})
    diagnostics = availability_diagnostics(result.categories, contributions, now=now, policy=policy)
    if result.metadata.uses_placeholder_data:
        for row in diagnostics.values():
            row["reasons"] = ["placeholder_data"]
    return result, diagnostics


def format_availability(name, row):
    def age(value):
        return f"{value:.3f}" if value is not None else "n/a"
    return (f"{name}: availability={row['availability']}; supported_events={row['supported_events']}; "
            f"source_observations={row['source_observations']}\n"
            f"  raw_support={row['raw_support']:.6f}; effective_support={row['effective_support']:.6f}; "
            f"minimum_support={row['minimum_support']:.6f}; minimum_events={row['minimum_events']}\n"
            f"  freshest_event_age_days={age(row['freshest_event_age_days'])}; "
            f"oldest_event_age_days={age(row['oldest_event_age_days'])}; "
            f"reasons={','.join(row['reasons']) or 'none'}")
