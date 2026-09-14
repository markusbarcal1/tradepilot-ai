from datetime import datetime, timedelta, timezone
import math

import pytest
from pydantic import ValidationError

from app.models.outlook_evidence import OutlookEvidence
from app.models.outlook_taxonomy import EVENT_TYPES, EvidenceImpact, SourceType
from app.models.outlook import OutlookMetadata
from app.services.outlook import aggregate_outlook, analyze_outlook, assess_providers
from app.services.outlook_evidence import (assess_evidence, cluster_evidence, freshness,
                                          normalize_url, weigh_cluster)
from app.services.outlook_policy import DEFAULT_EVIDENCE_POLICY, EvidencePolicy, FreshnessRule

NOW = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)


def evidence(identifier="a", **changes):
    data = dict(id=identifier, ticker="AAPL", category="company", event_type="contract_award",
        title=f"Distinct event {identifier}", summary="Fixture evidence, not live intelligence.",
        source="Company", source_type="company_release", source_url=f"https://example.com/{identifier}",
        published_at=NOW, observed_at=NOW, impact=2, confidence=1, materiality=1,
        materiality_reason="Material multi-year contract.", raw_provider="fixture", raw_provider_id=identifier)
    data.update(changes)
    return OutlookEvidence.model_validate(data)


def test_normalization_and_provenance_roundtrip():
    item = evidence(ticker=" aapl ", title="  Raised guidance  ",
                    published_at=NOW.astimezone(timezone(timedelta(hours=-7))))
    assert item.ticker == "AAPL" and item.title == "Raised guidance"
    assert item.published_at.utcoffset() == timedelta(0)
    assert OutlookEvidence.model_validate_json(item.model_dump_json()) == item
    assert item.raw_provider_id == "a" and item.source == "Company"


@pytest.mark.parametrize("changes", [
    {"category": "other"}, {"event_type": "unknown"}, {"event_type": "inflation"},
    {"impact": 3}, {"confidence": -0.1}, {"confidence": 1.1}, {"confidence": math.nan},
    {"materiality": -0.1}, {"materiality": 1.1}, {"materiality": math.inf},
    {"published_at": NOW.replace(tzinfo=None)}, {"observed_at": NOW-timedelta(seconds=1)},
    {"expires_at": NOW}, {"source_type": "sec"}, {"source_url": "not a URL"},
    {"materiality_reason": " "}, {"overall_outlook": "Positive"},
])
def test_validation(changes):
    with pytest.raises(ValidationError):
        evidence(**changes)


@pytest.mark.parametrize("category,event", [(key, event) for key, values in EVENT_TYPES.items() for event in values])
def test_taxonomy(category, event):
    assert evidence(category=category, event_type=event).category == category


def test_impact_is_independent_of_confidence_and_materiality():
    assert [int(item) for item in EvidenceImpact] == [-2, -1, 0, 1, 2]
    item = evidence(impact=-2, confidence=0.9, materiality=0.8)
    result = weigh_cluster((item,), NOW)
    assert result.contribution == pytest.approx(-2 * 0.9 * 0.8)
    assert item.source_type == SourceType.COMPANY_RELEASE


def test_freshness_decay_expiration_and_no_observation_lookahead():
    item = evidence(published_at=NOW-timedelta(days=7))
    assert freshness(item, NOW) == pytest.approx(0.5)
    assert freshness(evidence(published_at=NOW-timedelta(days=30)), NOW) == 0
    assert freshness(evidence(published_at=NOW-timedelta(days=1), expires_at=NOW), NOW) == 0
    assert freshness(evidence(observed_at=NOW+timedelta(seconds=1)), NOW) == 0
    with pytest.raises(ValueError):
        freshness(item, NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        assess_evidence("AAPL", [], now=NOW.replace(tzinfo=None))
    guidance = evidence(category="earnings", event_type="guidance_raise", published_at=NOW-timedelta(days=7))
    assert freshness(guidance, NOW) > freshness(item, NOW)
    fast = EvidencePolicy(event_freshness={item.event_type: FreshnessRule(half_life_days=1, max_age_days=2)})
    assert freshness(item, NOW, fast) == 0


def test_deduplication_and_all_sources_retained():
    first = evidence(title="Company announces major acquisition")
    syndicated = evidence("b", title="Company announces major acquisition!", raw_provider="wire", raw_provider_id="wire-b")
    same_url = evidence("c", title="New article title", source_url="http://EXAMPLE.com/a/?utm_source=wire#top")
    same_provider_id = evidence("d", title="Changed title", raw_provider_id="a", published_at=NOW-timedelta(days=1))
    # Strong identities and normalized URLs independently deduplicate.
    for second in (syndicated, same_url, same_provider_id):
        assert len(cluster_evidence([first, second])) == 1
    clusters = cluster_evidence([first, syndicated, same_url])
    assert len(clusters) == 1
    categories, contributions = assess_evidence("AAPL", [first, syndicated, same_url], now=NOW)
    assert categories["company"].status == "insufficient_data"
    assert categories["company"].evidence_count == 1
    assert len(categories["company"].evidence) == 3
    assert len(contributions[0].evidence) == 3
    assert cluster_evidence(list(reversed([first, syndicated, same_url]))) == clusters
    assert normalize_url("https://example.com/a?x=2&utm_medium=web&b=1") == "https://example.com/a?b=1&x=2"


def test_dedup_scopes_time_hook_and_reprint_age():
    first = evidence()
    assert len(cluster_evidence([first, evidence("b", ticker="MSFT", title=first.title)])) == 2
    assert len(cluster_evidence([first, evidence("b", event_type="partnership", title=first.title)])) == 2
    assert len(cluster_evidence([first, evidence("b", published_at=NOW-timedelta(days=3), title=first.title)])) == 2
    assert len(cluster_evidence([first, evidence("b")], similarity=lambda a, b: 1)) == 1
    assert len(cluster_evidence([first, evidence("b")], similarity=lambda a, b: 0)) == 2
    old = evidence("old", raw_provider_id="a", published_at=NOW-timedelta(days=30))
    cluster = cluster_evidence([first, old])[0]
    assert weigh_cluster(cluster, NOW).weight == 0


def assess(items, **kwargs):
    # The titles below deliberately describe different events, not syndicated stories.
    return assess_evidence("AAPL", items, now=NOW, **kwargs)[0]


def distinct():
    return [evidence("a", title="New government contract"),
            evidence("b", title="Acquisition closes", event_type="acquisition"),
            evidence("c", title="Major product released", event_type="product_launch")]


def test_minimum_support_strength_and_conflicts():
    items = distinct()
    assert assess(items[:1])["company"].status == "insufficient_data"
    assert assess(items[:2])["company"].label == "Positive"
    assert assess(items)["company"].label == "Very Positive"
    negative = evidence("b", title="Contract cancelled", impact=-2, event_type="operational_update")
    category = assess([items[0], negative])["company"]
    assert category.label == "Mixed" and category.value == 0
    assert category.evidence_count == 2
    assert {factor.evidence_ids[0] for factor in category.factors} == {"a", "b"}
    assert all(factor.description in [item.summary for item in category.evidence] for factor in category.factors)
    assert all(c.status == "insufficient_data" for c in assess([]).values())
    weak = [evidence(str(i), title=str(i), confidence=0.1) for i in range(20)]
    assert assess(weak)["company"].status == "insufficient_data"
    duplicate_conflict = evidence("a", impact=-2)
    assert assess([evidence(), duplicate_conflict])["company"].status == "insufficient_data"
    assert assess([evidence("x", ticker="MSFT")])["company"].evidence_count == 0


def test_geopolitical_requires_exposure_and_explicit_nonmaterial_review():
    unknown = evidence(category="geopolitical", event_type="conflict", impact=-2)
    assert assess([unknown])["geopolitical"].status == "insufficient_data"
    immaterial = evidence(category="geopolitical", event_type="conflict", materiality=0,
                          materiality_reason="No company geography or supply-chain exposure identified.")
    category = assess([immaterial])["geopolitical"]
    assert category.status == "not_material" and category.value is None
    exposed = evidence(category="geopolitical", event_type="conflict", impact=-2,
                       exposure_links=[{"kind": "manufacturing", "description": "Fixture plant location."}])
    assert weigh_cluster((exposed,), NOW).contribution == -2
    assert assess([])["geopolitical"].status != "not_material"


def test_overall_quality_weight_and_phase1_compatibility():
    from app.models.outlook import OutlookCategory
    metadata = OutlookMetadata(provider="fixture", uses_placeholder_data=False)
    categories = {"company": OutlookCategory(status="available", value=1, evidence_count=3, confidence=1),
                  "earnings": OutlookCategory(status="available", value=-1, evidence_count=2, confidence=0.5)}
    assert aggregate_outlook("AAPL", categories, metadata).value == pytest.approx(1/3)
    categories["earnings"] = OutlookCategory(status="available", value=-2, evidence_count=1, confidence=1)
    assert aggregate_outlook("AAPL", categories, metadata).value == 1
    assert aggregate_outlook("AAPL", {"company": OutlookCategory(status="available", value=1)}, metadata).value == 1


class FixtureProvider:
    name = "fixture"
    uses_placeholder_data = False
    def get_evidence(self, ticker):
        return distinct()


class BrokenProvider:
    name = "broken"
    uses_placeholder_data = False
    def get_evidence(self, ticker):
        raise RuntimeError("private detail")


def test_provider_isolation_and_placeholder_never_exposes_fixtures():
    result = assess_providers("AAPL", [FixtureProvider(), BrokenProvider()], now=NOW)
    assert result.categories["company"].label == "Very Positive"
    assert result.status == "partial"
    assert "private detail" not in result.model_dump_json()
    class WrongTicker(FixtureProvider):
        def get_evidence(self, ticker):
            return [evidence(ticker="MSFT")]
    assert analyze_outlook("AAPL", WrongTicker(), now=NOW).status == "error"
    class WrongProvider(FixtureProvider):
        def get_evidence(self, ticker):
            return [evidence(raw_provider="someone_else")]
    assert analyze_outlook("AAPL", WrongProvider(), now=NOW).status == "error"
    class Demo(FixtureProvider):
        uses_placeholder_data = True
    for providers in ([Demo()], [Demo(), BrokenProvider()]):
        result = assess_providers("AAPL", providers, now=NOW)
        assert result.status == "placeholder" and result.label is None
        assert all(not category.evidence and not category.factors for category in result.categories.values())
    assert analyze_outlook("AAPL", now=NOW).status == "placeholder"


def test_policy_thresholds_low_weight_and_expired_evidence():
    items = distinct()[:2]
    strict = EvidencePolicy(positive_threshold=1.8, strong_threshold=1.9)
    attenuated = [OutlookEvidence.model_validate({**item.model_dump(), "confidence": 0.7}) for item in items]
    assert assess(attenuated, policy=strict)["company"].label == "Mixed"
    assert assess(attenuated)["company"].label == "Positive"
    trivial = [OutlookEvidence.model_validate({**item.model_dump(), "materiality": 0.11}) for item in items]
    assert assess(trivial)["company"].status == "insufficient_data"
    expired = [OutlookEvidence.model_validate({**item.model_dump(), "published_at": NOW-timedelta(days=31)}) for item in items]
    category = assess(expired)["company"]
    assert category.evidence_count == 0 and category.value is None
    assert len(category.evidence) == 2
    with pytest.raises(ValidationError):
        EvidencePolicy(positive_threshold=1.5, strong_threshold=1)
    with pytest.raises(ValidationError):
        EvidencePolicy(category_freshness={})


def test_no_fixture_network_requests_and_http_keeps_placeholder(monkeypatch):
    import app.services.market_data as market_data
    def forbidden(*args, **kwargs):
        raise AssertionError("Outlook must not request market data in Phase 2")
    monkeypatch.setattr(market_data, "get_price_history", forbidden)
    response = analyze_outlook("AAPL", now=NOW)
    assert response.status == "placeholder"
    assert all(category.evidence_count == 0 for category in response.categories.values())


def test_future_duplicate_cannot_change_historical_assessment():
    items = distinct()
    future_duplicate = evidence("a", observed_at=NOW+timedelta(days=1), confidence=1, impact=-2)
    assert assess([*items, future_duplicate]) == assess(items)


def test_custom_support_policy_is_used_by_overall_aggregation():
    policy = EvidencePolicy(minimum_events=4, strong_minimum_events=4)
    result = assess_providers("AAPL", [FixtureProvider()], now=NOW, policy=policy)
    assert result.value is None and result.status == "unavailable"
