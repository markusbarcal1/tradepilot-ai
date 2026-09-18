from datetime import datetime, timedelta, timezone
import json

import pytest

from app.cli.evaluate_outlook import DEFAULT_CORPUS
from app.models.outlook import OutlookCategory, OutlookMetadata
from app.models.outlook_evaluation import EvaluationCorpus
from app.models.outlook_evidence import OutlookEvidence
from app.services.outlook import aggregate_outlook
from app.services.outlook_diagnostics import availability_diagnostics, inspect_snapshot, format_availability
from app.services.outlook_evidence import assess_evidence, availability_failures
from app.services.outlook_evaluation import replay, evaluate_package
from app.services.outlook_policy import EvidencePolicy

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def evidence(id, **changes):
    data = dict(id=id, ticker="TEST", category="earnings", event_type="earnings_result",
        title=id, summary="Frozen diagnostic fixture", source="fixture", source_type="company_release",
        published_at=NOW, observed_at=NOW, impact=1, confidence=.9, materiality=.8,
        materiality_reason="Synthetic supported fact", raw_provider="fixture", raw_provider_id=id,
        source_details={"earnings_release_id":id,"numeric":{"metric":"revenue"}})
    data.update(changes)
    return OutlookEvidence(**data)


def diagnose(records, now=NOW, policy=None):
    policy=policy or EvidencePolicy()
    cats, cs=assess_evidence("TEST",records,now=now,policy=policy)
    return availability_diagnostics(cats,cs,now=now,policy=policy)['earnings']


@pytest.mark.parametrize('count,weight,reasons',[
    (1,.72,('insufficient_independent_events','support_below_threshold')),
    (1,1,('insufficient_independent_events',)),
    (2,.749,('support_below_threshold',)),
    (2,.75,()),
])
def test_shared_gate_reports_all_failures_and_exact_boundary(count,weight,reasons):
    assert availability_failures(count,weight)==reasons


def test_single_event_multiple_failures_raw_effective_and_age():
    row=diagnose([evidence('one')],now=NOW+timedelta(days=45))
    assert row['supported_events']==row['source_observations']==1
    assert row['raw_support']==pytest.approx(.72)
    assert row['effective_support']==pytest.approx(.36)
    assert row['minimum_support']==.75 and row['minimum_events']==2
    assert row['freshest_event_age_days']==row['oldest_event_age_days']==45
    assert row['reasons']==['insufficient_independent_events','support_below_threshold']


def test_stale_and_future_observations():
    stale=diagnose([evidence('one')],now=NOW+timedelta(days=120))
    assert stale['supported_events']==0 and stale['source_observations']==1
    assert stale['effective_support']==stale['raw_support']==0
    assert stale['freshest_event_age_days'] is None
    assert 'all_evidence_stale' in stale['reasons']
    future=diagnose([evidence('future',observed_at=NOW+timedelta(days=1))])
    assert future['source_observations']==0
    assert 'no_source_observations' in future['reasons']
    assert 'all_evidence_stale' not in future['reasons']


def test_available_and_not_material_states():
    available=diagnose([evidence('first'),evidence('different')])
    assert available['availability']=='available' and available['reasons']==[]
    immaterial=diagnose([evidence('one',materiality=0)])
    assert immaterial['availability']=='not_material'
    assert immaterial['reasons']==['not_material']


def test_duplicate_observations_are_not_events_or_extra_support():
    item=evidence('one')
    row=diagnose([item,item.model_copy(update={'id':'copy'})])
    assert row['source_observations']==2 and row['supported_events']==1
    assert row['raw_support']==pytest.approx(.72)


def test_multiple_factors_use_production_event_cap_without_refresh():
    a=evidence('release')
    b=a.model_copy(update={'id':'margin','event_type':a.event_type,
        'source_details':{'earnings_release_id':'release','numeric':{'metric':'gross_margin'}},
        'published_at':NOW-timedelta(days=10)})
    row=diagnose([a,b])
    assert row['supported_events']==1 and row['raw_support']==pytest.approx(.72)
    assert row['effective_support']==pytest.approx(.72)
    assert row['oldest_event_age_days']==10


def test_custom_policy_is_used_without_cli_constants():
    policy=EvidencePolicy(minimum_events=3,minimum_weight=1.5)
    row=diagnose([evidence('first'),evidence('different')],policy=policy)
    assert row['minimum_events']==3 and row['minimum_support']==1.5
    assert row['reasons']==['insufficient_independent_events','support_below_threshold']


@pytest.mark.parametrize('case,count,weight,reasons',[
    ('aapl_style',1,.341538,['insufficient_independent_events','support_below_threshold']),
    ('nvda_style',2,.632027,['support_below_threshold']),
])
def test_frozen_aapl_nvda_inspection_and_evaluation_agree(case,count,weight,reasons):
    corpus=EvaluationCorpus.model_validate_json(DEFAULT_CORPUS.read_text(encoding='utf-8'))
    package=next(p for p in corpus.packages if p.id==case)
    point=package.replays[-1]
    _, _, response, _=replay(package,point.assessment_at)
    before=response.model_dump_json()
    inspected, diagnostics=inspect_snapshot(response,now=point.assessment_at)
    row=diagnostics['earnings']
    assert inspected.model_dump_json()==before==response.model_dump_json()
    assert row['supported_events']==count and row['reasons']==reasons
    assert row['effective_support']==pytest.approx(weight,abs=1e-6)
    assert row['raw_support']==pytest.approx(count*.72)
    assert evaluate_package(package)['replays'][-1]['availability_diagnostics']==diagnostics
    text=format_availability('earnings',row)
    assert 'minimum_support=0.750000' in text and 'support_below_threshold' in text


def test_provider_states_and_snapshot_clock_boundary():
    cats,_=assess_evidence('TEST',[evidence('one')],now=NOW)
    cats['industry']=OutlookCategory(status='unavailable')
    cats['market']=OutlookCategory(status='error')
    result=aggregate_outlook('TEST',cats,OutlookMetadata(provider='fixture',uses_placeholder_data=False))
    _, rows=inspect_snapshot(result,now=NOW+timedelta(days=120))
    assert rows['industry']['reasons']==['provider_not_connected_or_configured']
    assert rows['market']['reasons']==['provider_error']
    assert rows['earnings']['availability']=='insufficient_data'
    assert 'all_evidence_stale' in rows['earnings']['reasons']


def test_cli_json_is_additive_and_has_diagnostics(monkeypatch,capsys):
    from app.cli import inspect_outlook
    cats,_=assess_evidence('TEST',[evidence('one')],now=NOW)
    response=aggregate_outlook('TEST',cats,OutlookMetadata(provider='fixture',uses_placeholder_data=False))
    monkeypatch.setattr(inspect_outlook,'analyze_outlook',lambda ticker:response)
    monkeypatch.setattr('app.services.outlook_structured.configured_providers', lambda: [])
    class Clock:
        @staticmethod
        def now(tz): return NOW
    monkeypatch.setattr(inspect_outlook,'datetime',Clock)
    monkeypatch.setattr('sys.argv',['inspect_outlook','TEST','--json'])
    assert inspect_outlook.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result['categories']==response.model_dump(mode='json')['categories']
    assert result['availability_diagnostics']['earnings']['reasons']==[
        'insufficient_independent_events','support_below_threshold']
