"""Factual dimensions of one identified earnings release; no category policy."""
from dataclasses import dataclass
from math import fsum

from app.models.outlook_evidence import OutlookEvidence


METRICS = {
    "revenue": "revenue", "revenues": "revenue", "eps": "eps",
    "earnings per share": "eps", "diluted eps": "diluted_eps",
    "diluted_eps": "diluted_eps", "diluted earnings per share": "diluted_eps",
    "gross_margin": "gross_margin", "operating_margin": "operating_margin",
}


def release_identity(item):
    identity = item.source_details.get("earnings_release_id")
    if (item.category == "earnings" and isinstance(identity, str) and identity
            and item.event_type in ("earnings_result", "margin_change")):
        return item.ticker, item.category, identity
    return None


def factor_identity(item):
    numeric = item.source_details.get("numeric", {})
    if not isinstance(numeric, dict):
        return None
    metric = METRICS.get(str(numeric.get("metric", "")).lower())
    if not metric:
        return None
    # Missing period means the identified release's period, never an inferred year.
    period = item.source_details.get("reporting_period") or numeric.get("current_period") or "release_period"
    return (metric, str(numeric.get("comparison", "unspecified")), str(period),
            str(numeric.get("basis", "unspecified")).casefold())


@dataclass(frozen=True)
class FactorAssessment:
    identity: tuple[str, ...]
    evidence: tuple[OutlookEvidence, ...]
    representative: OutlookEvidence
    freshness: float
    weight: float
    exclusion: str | None


def semantic_key(item):
    """Financial selection only. Display/provenance ties have identical math."""
    return (-item.confidence * item.materiality, -item.confidence,
            -item.materiality, abs(int(item.impact)), item.published_at)


def assess_factors(cluster, now, policy, freshness):
    groups = {}
    for item in cluster:
        # Unidentified assertions must not be invented as new factual dimensions.
        identity = factor_identity(item) or ("unidentified", str(item.event_type))
        groups.setdefault(identity, []).append(item)
    results = []
    for identity, records in sorted(groups.items()):
        # An unspecified period/basis cannot become an extra vote alongside a
        # potentially identical, more precisely identified fact. Keep provenance
        # rather than guessing that unspecified means GAAP or a particular quarter.
        primary = [r for r in records if r.source_quality == "primary_authoritative"]
        ambiguous_identity = False
        for other, reports in groups.items():
            if len(identity) != 4 or len(other) != 4 or identity == other or identity[:2] != other[:2]:
                continue
            compatible = (identity[2] == other[2] or "release_period" in (identity[2], other[2])) and (
                identity[3] == other[3] or "unspecified" in (identity[3], other[3]))
            other_primary = any(r.source_quality == "primary_authoritative" for r in reports)
            more_precise = ((identity[2] == other[2] or identity[2] == "release_period") and
                            (identity[3] == other[3] or identity[3] == "unspecified"))
            other_supported = any(r.scoring_eligible and r.materiality >= policy.minimum_materiality
                and r.confidence >= policy.minimum_confidence and freshness(r, now, policy) > 0 for r in reports)
            if compatible and ((other_primary and not primary) or
                    (other_primary == bool(primary) and more_precise and other_supported)):
                ambiguous_identity = True
        authoritative = primary or records
        eligible, exclusions = [], []
        for r in authoritative:
            reason = ("provenance_only" if not r.scoring_eligible else
                      "expired_or_not_yet_observed" if freshness(r, now, policy) == 0 else
                      "not_material" if r.materiality == 0 else
                      "low_materiality" if r.materiality < policy.minimum_materiality else
                      "low_confidence" if r.confidence < policy.minimum_confidence else None)
            exclusions.append(reason)
            if reason is None:
                eligible.append(r)
        chosen = min(eligible or authoritative, key=semantic_key)
        qualified = [r for r in authoritative if r.scoring_eligible
                     and r.materiality >= policy.minimum_materiality
                     and r.confidence >= policy.minimum_confidence]
        age = min(freshness(r, now, policy) for r in qualified or authoritative)
        reason = None
        if identity[0] == "unidentified":
            reason = "unidentified_factor"
        elif ambiguous_identity:
            reason = "ambiguous_factor_identity"
        elif not eligible:
            reason = exclusions[0] if len(set(exclusions)) == 1 else "no_eligible_factors"
        elif age == 0:
            reason = "expired_or_not_yet_observed"
        else:
            signs = {1 if r.impact > 0 else -1 if r.impact < 0 else 0 for r in eligible}
            # Compare explicit like-unit assertions, never invent a missing baseline.
            values = {}
            for r in eligible:
                numeric = r.source_details.get("numeric", {})
                for field in ("change_percent", "percentage_points", "current_value", "prior_value",
                              "current_percent", "prior_percent"):
                    value = numeric.get(field)
                    if isinstance(value, (int, float)):
                        unit = numeric.get("unit", "") if field.endswith("value") else ""
                        values.setdefault((field, str(unit)), set()).add(value)
            if len(signs) > 1 or any(len(v) > 1 for v in values.values()):
                reason = "conflicting_duplicate_interpretations"
        weight = chosen.confidence * chosen.materiality * age if reason is None else 0.0
        results.append(FactorAssessment(identity, tuple(records), chosen, age, weight, reason))
    return tuple(results)


def event_values(factors):
    supported = [f for f in factors if f.exclusion is None]
    if not supported:
        return 0.0, 0.0, None
    total = fsum(f.weight for f in supported)
    weight = max(f.weight for f in supported)
    impact = fsum(int(f.representative.impact) * f.weight for f in supported) / total
    confidence = fsum(f.representative.confidence * f.weight for f in supported) / total
    return weight, weight * impact, confidence
