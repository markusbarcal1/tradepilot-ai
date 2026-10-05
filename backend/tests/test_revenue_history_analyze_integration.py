from datetime import datetime, timezone
import importlib.util
import inspect
from pathlib import Path
from types import SimpleNamespace

from pydantic import SecretStr

from app.models.outlook_revenue_history_snapshot import RevenueHistorySnapshotResult, RevenueSnapshotRequestAccounting
from app.models.outlook_revenue_research import RevenueResearchProjectionResult

NOW=datetime(2026,10,4,tzinfo=timezone.utc)

def load_test_module(name):
    path=Path(__file__).with_name(name+".py")
    spec=importlib.util.spec_from_file_location(name+"_fixtures",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def route_fixture(monkeypatch, snapshot=None, events=None, generated_available=True, snapshot_service=None):
    import app.main as main
    ai=load_test_module("test_outlook_ai")
    fixture=ai.outlook([ai.evidence()]); packet=ai.build_context_packet(fixture,generated_at=NOW)
    events=events if events is not None else []
    monkeypatch.setattr(main.settings,"outlook_llm_enabled",True)
    monkeypatch.setattr(main.settings,"outlook_llm_provider","openai")
    monkeypatch.setattr(main.settings,"openai_api_key",SecretStr("test-key"))
    monkeypatch.setattr(main,"analyze_outlook",lambda ticker:(events.append("deterministic"),fixture)[1])
    monkeypatch.setattr(main,"build_context_packet",lambda value:(events.append("packet"),packet)[1])
    monkeypatch.setattr(main,"OpenAIOutlookIntelligenceProvider",lambda **kwargs:object())
    generated=(SimpleNamespace(status="available",response=ai.valid_response(packet)) if generated_available
        else SimpleNamespace(status="unavailable",response=None))
    monkeypatch.setattr(main,"generate_intelligence",lambda packet,provider:(events.append("ai"),generated)[1])
    class Service:
        def get_snapshot(self,ticker):events.append("snapshot");return snapshot
    service = snapshot_service or Service()
    monkeypatch.setattr(main,"get_revenue_history_snapshot_service",lambda:service)
    return main,packet,events

def unavailable_snapshot(state="unavailable",projection=None,reasons=("feature_disabled",)):
    return RevenueHistorySnapshotResult(snapshot_policy="revenue-history-snapshot-1",ticker="AAPL",
        state=state,reasons=reasons,projection=projection,
        request_accounting=RevenueSnapshotRequestAccounting(historical_logical_requests=0,
            historical_http_attempts=0,total_sec_http_attempts=0))

def available_projection():
    module=load_test_module("test_revenue_history_research_dto")
    return module.projection("AAPL",2025)

def test_a_b_master_off_runs_after_ai_and_maps_explicit_unavailable(monkeypatch):
    main,packet,events=route_fixture(monkeypatch,unavailable_snapshot())
    result=main.outlook_analysis("AAPL")
    assert events==["deterministic","packet","ai","snapshot"]
    assert result.status=="available" and result.research.revenue_history.availability=="unavailable"
    assert result.analysis is not None and packet.ticker=="AAPL"

def test_c_ai_failure_performs_zero_snapshot_work(monkeypatch, caplog):
    main,_,events=route_fixture(monkeypatch,unavailable_snapshot(),generated_available=False)
    result=main.outlook_analysis("AAPL")
    assert result.status=="unavailable" and "snapshot" not in events
    assert not any(hasattr(row,"revenue_history_event") for row in caplog.records)

def test_d_e_direct_history_projection_reaches_existing_dto_without_q4_route_logic(monkeypatch):
    projection=available_projection()
    snapshot=unavailable_snapshot("available",projection,())
    snapshot=snapshot.model_copy(update={"evidence_fingerprint":"0"*64})
    main,_,_=route_fixture(monkeypatch,snapshot)
    result=main.outlook_analysis("AAPL")
    assert result.research.revenue_history.availability=="available"
    assert len(result.research.revenue_history.points)==len(projection.points)

def test_direct_history_runs_actual_snapshot_composition_through_route_with_three_attempt_ceiling(monkeypatch):
    snapshots=load_test_module("test_revenue_history_snapshot")
    captured=[]
    inner=snapshots.service(snapshots.settings(q4=True),
        lambda ticker:snapshots.acquisition(snapshots.consecutive(5),ticker=ticker))
    class Capture:
        def get_snapshot(self,ticker):
            value=inner.get_snapshot(ticker);captured.append(value);return value
    main,_,_=route_fixture(monkeypatch,snapshot_service=Capture())
    result=main.outlook_analysis("AAPL")
    assert result.research.revenue_history.availability=="available"
    assert captured[0].request_accounting.historical_http_attempts<=3
    assert captured[0].request_accounting.document_accounting is None

def test_f_g_q4_disabled_insufficient_maps_without_route_financial_logic(monkeypatch):
    projection=RevenueResearchProjectionResult(state="unavailable",reasons=("research_eligible_series_required",))
    main,_,_=route_fixture(monkeypatch,unavailable_snapshot("insufficient_data",projection,("q4_derivation_disabled",)))
    result=main.outlook_analysis("AAPL")
    assert result.research.revenue_history.availability=="insufficient_data"

def test_h_j_full_q4_projection_preserves_derived_decimal_and_provenance(monkeypatch):
    projection=available_projection(); assert any(point.derived for point in projection.points)
    snapshot=unavailable_snapshot("available",projection,()).model_copy(update={"evidence_fingerprint":"1"*64})
    main,_,_=route_fixture(monkeypatch,snapshot)
    result=main.outlook_analysis("AAPL")
    actual=result.research.revenue_history
    source=next(point for point in projection.points if point.derived)
    mapped=next(point for point in actual.points if point.derived)
    assert mapped.exact_revenue==source.exact_revenue
    assert mapped.derivation_policy=="revenue-q4-derivation-1"

def test_full_q4_pipeline_runs_through_route_and_stays_within_seven_attempts(monkeypatch):
    from app.services import revenue_history_observability
    logged=[]
    monkeypatch.setattr(revenue_history_observability.LOGGER,"log",
        lambda level,message,**kwargs:logged.append(kwargs["extra"]["revenue_history_event"]))
    snapshots=load_test_module("test_revenue_history_snapshot")
    runtime=load_test_module("test_revenue_q4_runtime_input")
    selected,retrieved=runtime.inputs()
    periods=((2025,"Q1",datetime(2025,1,1).date(),datetime(2025,3,31).date()),
        (2025,"Q2",datetime(2025,4,1).date(),datetime(2025,6,30).date()),
        (2025,"Q3",datetime(2025,7,1).date(),datetime(2025,9,30).date()),
        (2026,"Q1",datetime(2026,1,1).date(),datetime(2026,3,31).date()),
        (2026,"Q2",datetime(2026,4,1).date(),datetime(2026,6,30).date()),
        (2026,"Q3",datetime(2026,7,1).date(),datetime(2026,9,30).date()))
    rows=[snapshots.observation(year,quarter,start,end,100+index,"AAPL")
        for index,(year,quarter,start,end) in enumerate(periods)]
    captured=[];events=[]
    inner=snapshots.service(snapshots.settings(q4=True),
        lambda ticker:snapshots.acquisition(rows,ticker=ticker),
        select_filings=lambda *args:selected,retrieve_documents=lambda value:retrieved)
    class Capture:
        def get_snapshot(self,ticker):
            events.append("snapshot");value=inner.get_snapshot(ticker);captured.append(value);return value
    main,_,events=route_fixture(monkeypatch,events=events,snapshot_service=Capture())
    result=main.outlook_analysis("AAPL")
    assert events==["deterministic","packet","ai","snapshot"]
    assert result.research.revenue_history.availability=="available"
    assert any(point.derived for point in result.research.revenue_history.points)
    assert captured[0].request_accounting.historical_http_attempts<=3
    assert captured[0].request_accounting.document_accounting.http_attempts_charged<=4
    assert captured[0].request_accounting.total_sec_http_attempts<=7
    assert len(logged)==1
    assert logged[0]["snapshot_state"]==logged[0]["projection_state"]=="available"
    assert logged[0]["q4_considered"] is logged[0]["q4_attempted"] is True
    assert logged[0]["document_logical_requests"]==4
    assert logged[0]["total_http_attempts"]<=7

def test_k_m_snapshot_states_degrade_revenue_only_and_analyze_survives(monkeypatch):
    for state in ("unavailable","insufficient_data","conflict"):
        projection=(RevenueResearchProjectionResult(state="conflict",reasons=("series_conflict",))
            if state=="conflict" else RevenueResearchProjectionResult(state="unavailable",reasons=("research_eligible_series_required",)))
        snapshot=unavailable_snapshot(state,projection,(f"{state}_reason",))
        main,_,_=route_fixture(monkeypatch,snapshot)
        result=main.outlook_analysis("AAPL")
        assert result.status=="available" and result.analysis is not None
        assert result.research.industry is not None and result.research.market is not None
        assert result.research.earnings is not None
        assert result.research.revenue_history.availability==(state if state!="unavailable" else "insufficient_data")

def test_r_w_ai_packet_prompt_schema_and_generation_result_are_unchanged(monkeypatch):
    from app.services import outlook_ai
    main,packet,_=route_fixture(monkeypatch,unavailable_snapshot())
    before=packet.model_dump_json();fingerprint=outlook_ai.context_fingerprint(packet)
    result=main.outlook_analysis("AAPL")
    assert packet.model_dump_json()==before
    assert outlook_ai.context_fingerprint(packet)==fingerprint
    assert outlook_ai.PROMPT_VERSION=="outlook-analyst-2.5" and outlook_ai.SCHEMA_VERSION=="2.2"
    assert packet.schema_version=="2.2"
    source=inspect.getsource(outlook_ai.generate_intelligence)
    assert "revenue" not in source.lower()
    assert "(packet.ticker, provider.name, provider.model, PROMPT_VERSION, SCHEMA_VERSION, fingerprint)" in source

def test_y_get_outlook_does_not_invoke_revenue_service(monkeypatch,caplog):
    import app.main as main
    monkeypatch.setattr(main,"analyze_outlook",lambda ticker:"deterministic")
    monkeypatch.setattr(main,"get_revenue_history_snapshot_service",lambda:(_ for _ in ()).throw(AssertionError))
    assert main.outlook("AAPL")=="deterministic"
    assert not any(hasattr(row,"revenue_history_event") for row in caplog.records)

def test_ab_production_owner_is_singleton_and_not_registered(monkeypatch):
    from app.services.revenue_history_runtime import get_revenue_history_snapshot_service
    from app.services.outlook import configured_providers
    get_revenue_history_snapshot_service.cache_clear()
    first=get_revenue_history_snapshot_service();second=get_revenue_history_snapshot_service()
    assert first is second
    assert all(getattr(item,"name",None)!="revenue-history-snapshot-1" for item in configured_providers())

def test_ae_ai_defaults_and_response_schema_remain_frozen():
    from app.config import Settings
    from app.models.outlook_research import ResearchPresentation
    cfg=Settings(_env_file=None,environment="test")
    assert not cfg.outlook_historical_revenue_enabled
    assert not cfg.outlook_historical_revenue_q4_derivation_enabled
    assert ResearchPresentation.model_fields["schema_version"].default=="2"

def test_aa_ag_route_and_owner_have_no_background_direct_q4_or_frontend_path():
    import app.main as main
    route=inspect.getsource(main.outlook_analysis)
    owner=(Path(__file__).parents[1]/"app/services/revenue_history_runtime.py").read_text()
    for forbidden in ("create_task","BackgroundTasks","direct_q4","index.json","exhibit","frontend"):
        assert forbidden not in (route+owner)
