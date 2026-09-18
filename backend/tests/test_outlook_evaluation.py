"""Offline factual invariants and frozen replay acceptance; never live providers."""
from datetime import datetime, timedelta, timezone
from itertools import permutations
import json
import socket

import pytest

from app.cli.evaluate_outlook import DEFAULT_CORPUS, main
from app.models.outlook_evaluation import EvaluationCorpus
from app.models.outlook_evidence import OutlookEvidence
from app.services.outlook_evaluation import evaluate_package, replay, financial_snapshot, same_snapshot
from app.services.outlook_evidence import assess_evidence, weigh_cluster
from app.services.outlook_policy import DEFAULT_EVIDENCE_POLICY

NOW = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
CORPUS = EvaluationCorpus.model_validate_json(DEFAULT_CORPUS.read_text(encoding="utf-8"))


def factor(identifier, metric="revenue", impact=1, confidence=.9, materiality=.8, **changes):
    data = dict(id=identifier, ticker="TEST", category="earnings",
        event_type="margin_change" if "margin" in metric else "earnings_result",
        title="Financial result", summary=metric, source="Frozen fixture", source_type="company_release",
        published_at=NOW, observed_at=NOW, impact=impact, confidence=confidence, materiality=materiality,
        materiality_reason="Synthetic explicit factor", raw_provider="fixture", raw_provider_id="release",
        source_quality="primary_authoritative",
        source_details={"earnings_release_id": "release", "numeric": {"metric": metric, "comparison": "year_over_year"}})
    data.update(changes)
    return OutlookEvidence(**data)


def assessment(records, now=NOW):
    cats, cs = assess_evidence("TEST", records, now=now)
    return financial_snapshot(cats, cs), cs


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline evaluation attempted network access")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.mark.parametrize("package", CORPUS.packages, ids=lambda p: p.id)
def test_frozen_corpus(package):
    result = evaluate_package(package)
    failures = [(r["name"], c) for r in result["replays"] for c in r["checks"] if not c["passed"]]
    assert failures == []


@pytest.mark.parametrize("metric", ["revenue", "gross_margin"])
def test_below_threshold_opposition_id_and_order_invariant(metric):
    records = [factor("a", metric, -1, materiality=.01), factor("z")]
    baseline, cs = assessment(records)
    assert cs[0].weight == pytest.approx(.72)
    assert cs[0].contribution == pytest.approx(.72)
    for ordering in permutations(records):
        for variant in [ordering, [r.model_copy(update={"id": str(1-i)}) for i,r in enumerate(ordering)]]:
            assert same_snapshot(baseline, assessment(variant)[0])


def test_mixed_event_formula_no_metric_multiplication():
    rows = [factor("revenue"), factor("eps", "diluted_eps"),
            factor("margin", "gross_margin", -1, confidence=.8, materiality=.4)]
    snap, cs = assessment(rows)
    assert snap["earnings"]["events"] == 1
    assert snap["earnings"]["status"] == "insufficient_data"
    assert cs[0].weight == pytest.approx(.72)
    assert cs[0].contribution == pytest.approx(.72 * (.72+.72-.32)/(.72+.72+.32))
    assert len(cs[0].factors) == 3
    assert cs[0].event_confidence == pytest.approx((.9*.72+.9*.72+.8*.32)/1.76)


def test_repeated_same_fact_does_not_change_mixed_balance():
    rows = [factor("revenue"), factor("margin", "gross_margin", -1, materiality=.4)]
    baseline = assessment(rows)[0]
    duplicates = [rows[0].model_copy(update={"id": f"copy{i}", "raw_provider": f"provider{i}"}) for i in range(10)]
    assert same_snapshot(baseline, assessment(rows+duplicates)[0])


def test_financial_assessment_ignores_ids_titles_provider_and_input_order():
    rows = [factor("a"), factor("b", "diluted_eps", materiality=.5), factor("c", "gross_margin", -1, materiality=.3)]
    baseline = assessment(rows)[0]
    for ordering in permutations(rows):
        renamed = [r.model_copy(update={"id": str(100-i), "title": f"Harmless title {i}",
                     "raw_provider": f"renamed{i}"}) for i,r in enumerate(ordering)]
        assert same_snapshot(baseline, assessment(renamed)[0])


def test_primary_precedence_is_per_fact_and_retains_secondary_provenance():
    rows = [factor("primary"), factor("secondary", impact=-1, confidence=1,
            source_quality="secondary_reporting"), factor("margin", "gross_margin", -1, materiality=.4)]
    _, cs = assessment(rows)
    assert cs[0].weight == pytest.approx(.72)
    assert len(cs[0].evidence) == 3
    assert len(cs[0].factors) == 2
    assert cs[0].exclusion is None


def test_conflicting_fact_excluded_without_discarding_other_dimension():
    _, cs = assessment([factor("up"), factor("down", impact=-1), factor("eps", "diluted_eps")])
    assert cs[0].weight == pytest.approx(.72)
    assert {f.exclusion for f in cs[0].factors} == {None, "conflicting_duplicate_interpretations"}


def test_same_sign_different_explicit_values_are_conflicting_assertions():
    rows = [factor("a"), factor("b")]
    rows = [r.model_copy(update={"source_details": {**r.source_details,
            "numeric": {"metric": "revenue", "change_percent": change}}}) for r,change in zip(rows,[20,30])]
    _, cs = assessment(rows)
    assert cs[0].weight == 0
    assert cs[0].exclusion == "conflicting_duplicate_interpretations"


def test_unspecified_basis_cannot_duplicate_a_gaap_factor():
    gaap = factor('gaap', 'gross_margin', -1)
    gaap = gaap.model_copy(update={'source_details': {**gaap.source_details,
        'numeric': {'metric': 'gross_margin', 'comparison':'year_over_year', 'basis':'GAAP'}}})
    rows = [factor('revenue'),gaap,factor('unspecified','gross_margin',-1)]
    _, cs = assessment(rows)
    assert cs[0].contribution == pytest.approx(0)
    assert len(cs[0].evidence) == 3
    assert sum(f.exclusion=='ambiguous_factor_identity' for f in cs[0].factors)==1


def test_secondary_basis_annotation_cannot_override_primary_unspecified_fact():
    primary=factor('primary','gross_margin')
    news=factor('news','gross_margin',-1,source_quality='secondary_reporting')
    news=news.model_copy(update={'source_details':{**news.source_details,
        'numeric':{'metric':'gross_margin','comparison':'year_over_year','basis':'GAAP'}}})
    _, cs=assessment([primary,news])
    assert cs[0].weight == pytest.approx(.72)
    assert cs[0].contribution == pytest.approx(.72)


@pytest.mark.parametrize('field',['published_at','observed_at'])
def test_future_document_is_not_interpreted(field):
    package=next(p for p in CORPUS.packages if p.id=='aapl_style')
    source=package.sources[0]
    changes={field:NOW+timedelta(days=1),'observed_at':NOW+timedelta(days=1)}
    variant=package.model_copy(update={'sources':(source.model_copy(update={
        'document':source.document.model_copy(update=changes)}),)})
    assert replay(variant,NOW)[0] == []


def test_low_confidence_primary_is_not_replaced_by_secondary():
    _, cs = assessment([factor('primary',confidence=.2),
                        factor('news',confidence=1,source_quality='secondary_reporting')])
    assert cs[0].weight == 0
    assert cs[0].exclusion == 'low_confidence'


def test_materiality_and_confidence_resolve_ties_financially():
    # Same fact, same confidence: the supported magnitude cannot be selected by ID.
    rows=[factor('a',materiality=.1),factor('b',materiality=.8)]
    _, cs=assessment(rows)
    assert cs[0].weight == pytest.approx(.72)
    assert assessment(list(reversed(rows)))[1][0].weight == cs[0].weight


def test_harmless_reporting_wording_preserves_extraction_assessment():
    package=next(p for p in CORPUS.packages if p.id=='aapl_style')
    source=package.sources[0]
    changed=source.document.model_copy(update={'extracted_text':source.document.extracted_text.replace('posted','reported')})
    variant=package.model_copy(update={'sources':(source.model_copy(update={'document':changed}),)})
    left=replay(package,NOW)
    right=replay(variant,NOW)
    assert same_snapshot(financial_snapshot(left[2].categories,left[1]),financial_snapshot(right[2].categories,right[1]))


def test_positive_negative_reversal_is_symmetric():
    rows = [factor("a"),factor("b", "gross_margin", -1, materiality=.4)]
    _, before = assessment(rows)
    _, after = assessment([OutlookEvidence.model_validate({**r.model_dump(), "impact": -int(r.impact)}) for r in rows])
    assert before[0].weight == after[0].weight
    assert before[0].contribution == -after[0].contribution


def test_duplicate_impact_magnitude_tie_remains_symmetric():
    rows = [factor('one'),factor('two',impact=2)]
    left=assessment(rows)[1][0]
    right=assessment([OutlookEvidence.model_validate({**r.model_dump(),'impact':-int(r.impact)}) for r in rows])[1][0]
    assert left.contribution == -right.contribution


def test_below_threshold_old_noise_does_not_expire_supported_factor():
    rows=[factor('noise',materiality=.01,published_at=NOW-timedelta(days=130)),factor('supported')]
    assert assessment(rows)[1][0].weight == pytest.approx(.72)


def test_two_quarters_and_factor_provenance_visible_in_existing_contract():
    old = [factor("old-r"), factor("old-m", "gross_margin", -1, materiality=.4)]
    new = [r.model_copy(update={"id": "new"+r.id, "raw_provider_id": "new",
           "source_details": {**r.source_details,"earnings_release_id":"new"},
           "published_at":NOW+timedelta(days=3),"observed_at":NOW+timedelta(days=3)}) for r in old]
    cats, cs = assess_evidence("TEST",old+new,now=NOW+timedelta(days=3))
    assert cats['earnings'].evidence_count == 2
    assert len(cs) == 2
    assert len(cats['earnings'].factors) == 4
    assert {f.description for f in cats['earnings'].factors} == {'revenue','gross_margin'}


def test_future_evidence_cannot_suppress_existing_fact():
    rows = [factor("a"),factor("future",impact=-1,observed_at=NOW+timedelta(days=1))]
    snap, cs = assessment(rows)
    assert snap['earnings']['support'] == pytest.approx(.72)
    assert len(cs[0].evidence) == 1


def test_syndication_does_not_refresh_oldest_factor():
    old = factor("old",published_at=NOW-timedelta(days=119))
    new = factor("new")
    c = weigh_cluster((old,new),NOW)
    assert c.weight == pytest.approx(.72*2**(-119/45))
    assert weigh_cluster((old,new),NOW+timedelta(days=1)).weight == 0


def test_schema_retains_relationships_without_applying_supersession():
    p = next(p for p in CORPUS.packages if p.id=='revision_relationships')
    assert {r.kind for r in p.relationships} == {'amendment','correction','supersession','forecast_update'}
    assert len(replay(p,NOW)[0]) == 2


def test_policy_constants_unchanged():
    p = DEFAULT_EVIDENCE_POLICY
    assert (p.minimum_events,p.minimum_weight,p.minimum_confidence,p.minimum_materiality,
            p.positive_threshold,p.strong_threshold,p.strong_minimum_events)==(2,.75,.4,.1,.35,1.2,3)
    assert (p.category_freshness['earnings'].half_life_days,p.category_freshness['earnings'].max_age_days)==(45,120)


def test_cli_json_and_nonzero_on_mismatch(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr('sys.argv',['evaluate_outlook','--case','mixed_metrics','--json'])
    assert main()==0
    report=json.loads(capsys.readouterr().out)
    assert report['cases']==1 and report['failures']==0
    broken=CORPUS.model_dump(mode='json')
    broken['packages']=broken['packages'][:1]
    broken['packages'][0]['replays'][0]['outcomes'][0]['events']=99
    path=tmp_path/'broken.json'
    path.write_text(json.dumps(broken),encoding='utf-8')
    monkeypatch.setattr('sys.argv',['evaluate_outlook','--corpus',str(path)])
    assert main()==1
    assert 'failed' in capsys.readouterr().out
