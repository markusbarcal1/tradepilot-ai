from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest

from app.models.outlook_financial_history import HistoricalFinancialDiagnostics, HistoricalFinancialObservation, HistoricalFinancialSnapshot
from app.models.outlook_revenue_filing_selection import SecSubmissionsSelectionInput
from app.models.outlook_revenue_history_snapshot import RevenueHistoricalAcquisition
from app.services.outlook_research import _revenue_history
from app.services.outlook_structured.revenue_history_snapshot import RevenueHistorySnapshotService, identify_useful_q4_target

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
CIK = "0001045810"

def settings(master=True, q4=False, attempts=1, user_agent="TradePilot test@example.com"):
    return SimpleNamespace(outlook_historical_revenue_enabled=master,
        outlook_historical_revenue_q4_derivation_enabled=q4,
        outlook_sec_user_agent=user_agent, outlook_http_attempts=attempts)

def observation(year, quarter, start, end, value=100, ticker="TEST", cik=CIK):
    return HistoricalFinancialObservation(observation_id=f"{ticker}:{year}:{quarter}", issuer="Issuer",
        ticker=ticker, cik=cik, metric="revenue", fiscal_year=year, fiscal_quarter=quarter,
        period_start=start, period_end=end, duration_days=(end-start).days+1,
        original_concept="Revenues", original_value=Decimal(value), original_unit="USD",
        normalized_value=Decimal(value), currency="USD", share_basis="not_applicable",
        accession=f"{cik}-25-{year % 100:02d}{int(quarter[1]):04d}", form="10-Q",
        filing_date=end+timedelta(days=30), source_url="https://www.sec.gov/a",
        retrieved_at=NOW, version_status="current", comparison_eligible=True)

def diagnostics(requests=3):
    return HistoricalFinancialDiagnostics(source_status="partial", requests=requests,
        cache_reads=1, cache_loads=1, cache_hits=0, source_fact_count=8,
        processed_fact_count=8, accepted_observation_count=8, rejected_fact_count=0,
        request_budget=3, cache_ttl_seconds=21600, failure_cache_ttl_seconds=60,
        timeout_seconds=5, attempts=1, max_source_facts=256,
        max_quarterly_periods=8, max_annual_periods_inspected=5)

def acquisition(rows, ticker="TEST", submissions=True, requests=3):
    snapshot = HistoricalFinancialSnapshot(ticker=ticker, issuer="Issuer", cik=CIK,
        retrieved_at=NOW, status="partial", observations=tuple(rows), diagnostics=diagnostics(requests))
    metadata = SecSubmissionsSelectionInput(issuer="Issuer", cik=CIK,
        source_identity="fixture", rows=()) if submissions else None
    digest = hashlib.sha256("|".join(row.observation_id for row in rows).encode()).hexdigest()
    return RevenueHistoricalAcquisition(snapshot=snapshot, submissions=metadata,
        evidence_fingerprint=digest, logical_requests=requests,
        http_attempts=requests, cache_state="miss")

def consecutive(count=5, ticker="TEST"):
    start = datetime(2024, 1, 1).date(); rows=[]
    for index in range(count):
        year, quarter = 2024 + index // 4, f"Q{index % 4 + 1}"
        end = start + timedelta(days=89)
        rows.append(observation(year, quarter, start, end, 100+index, ticker))
        start = end + timedelta(days=1)
    return rows

def service(config, acquire, **deps):
    return RevenueHistorySnapshotService(config, acquire_history=acquire,
        retrieve_documents=deps.pop("retrieve_documents", lambda value: (_ for _ in ()).throw(AssertionError("document retrieval called"))), **deps)

def adapter_acquirer(rows,ticker,selected):
    from app.config import Settings
    from app.services.outlook_structured.sec_history import SecHistoricalFinancialProvider
    selected_by_role={item.role:item.document for item in selected.selected_filings}
    facts=[]; metadata=[]
    for row in rows:
        document=selected_by_role.get(row.fiscal_quarter) if row.fiscal_year==selected.target_fiscal_year else None
        accession=document.accession if document else row.accession
        filed=document.filing_date.isoformat() if document else row.filing_date.isoformat()
        facts.append({"start":row.period_start.isoformat(),"end":row.period_end.isoformat(),
            "val":str(row.normalized_value),"accn":accession,"fy":row.fiscal_year,
            "fp":row.fiscal_quarter,"form":"10-Q","filed":filed})
        if document is None:
            metadata.append((accession,"10-Q",filed,row.period_end.isoformat(),"history.htm"))
    for item in selected.selected_filings:
        doc=item.document
        metadata.append((doc.accession,doc.form,doc.filing_date.isoformat(),
            doc.report_period_end.isoformat(),doc.primary_document))
    issuer=selected.issuer; cik=selected.cik
    company={"cik":int(cik),"entityName":issuer,"facts":{"us-gaap":{
        "RevenueFromContractWithCustomerExcludingAssessedTax":{"units":{"USD":facts}},
        "EarningsPerShareDiluted":{"units":{"USD/shares":[]}}}}}
    submissions={"cik":int(cik),"name":issuer,"filings":{"recent":{
        "accessionNumber":[row[0] for row in metadata],"form":[row[1] for row in metadata],
        "filingDate":[row[2] for row in metadata],"acceptanceDateTime":[row[2]+"T20:00:00Z" for row in metadata],
        "reportDate":[row[3] for row in metadata],"primaryDocument":[row[4] for row in metadata]}}}
    class Client:
        def get(self,url,**kwargs):
            if "company_tickers" in url:return {"0":{"ticker":ticker,"cik_str":int(cik)}}
            return company if "companyfacts" in url else submissions
    cfg=Settings(_env_file=None,environment="test",outlook_sec_history_enabled=True,
        outlook_sec_user_agent="TradePilot test@example.com",outlook_http_attempts=1)
    provider=SecHistoricalFinancialProvider(cfg,Client(),lambda:NOW)
    return provider.get_acquisition

def test_a_master_off_is_unavailable_with_zero_acquisition():
    calls=[]; result=service(settings(master=False), lambda ticker: calls.append(ticker)).get_snapshot("aapl")
    assert result.state == "unavailable" and result.reasons == ("feature_disabled",) and calls == []

def test_b_f_direct_history_available_skips_all_q4_work_even_when_enabled():
    calls=[]; acq=acquisition(consecutive(5))
    result=service(settings(q4=True), lambda ticker: acq,
        select_filings=lambda *args: calls.append("selection")).get_snapshot("test")
    assert result.state == "available" and result.projection.summary.observation_count == 5
    assert not result.q4_considered and calls == [] and result.request_accounting.total_sec_http_attempts == 3

def test_c_q4_disabled_insufficient_is_typed_and_does_no_document_work():
    result=service(settings(q4=False), lambda ticker: acquisition(consecutive(4))).get_snapshot("TEST")
    assert result.state == "insufficient_data" and "q4_derivation_disabled" in result.reasons
    assert not result.q4_attempted

@pytest.mark.parametrize("config", [settings(user_agent=""), settings(attempts=2)])
def test_d_invalid_sec_configuration(config):
    assert service(config, lambda ticker: None).get_snapshot("TEST").reasons == ("sec_configuration_invalid",)

def test_e_acquisition_failure_is_unavailable():
    def fail(ticker): raise RuntimeError("offline")
    assert service(settings(), fail).get_snapshot("TEST").reasons == ("historical_acquisition_unavailable",)

def test_g_no_useful_gap_is_insufficient():
    result=service(settings(q4=True), lambda ticker: acquisition(consecutive(3))).get_snapshot("TEST")
    assert result.state == "insufficient_data" and result.reasons == ("no_useful_q4_gap",)

def gap_rows(ticker="TEST"):
    # FY2025 Q1-Q3, missing Q4, then FY2026 Q1-Q3: repair creates seven consecutive identities.
    start=datetime(2025,1,1).date(); rows=[]
    for year, role in ((2025,"Q1"),(2025,"Q2"),(2025,"Q3")):
        end=start+timedelta(days=89); rows.append(observation(year,role,start,end,100,ticker)); start=end+timedelta(days=1)
    start += timedelta(days=90)  # missing Q4
    for role in ("Q1","Q2","Q3"):
        end=start+timedelta(days=89); rows.append(observation(2026,role,start,end,100,ticker)); start=end+timedelta(days=1)
    return rows

def test_h_target_helper_selects_exact_useful_gap():
    state, request=identify_useful_q4_target(acquisition(gap_rows()).snapshot)
    assert state == "selected" and request.target_fiscal_year == 2025
    assert [row.role for row in request.quarter_anchors] == ["Q1","Q2","Q3"]

def test_missing_submissions_is_unavailable_without_selection():
    result=service(settings(q4=True), lambda ticker: acquisition(gap_rows(), submissions=False)).get_snapshot("TEST")
    assert result.state == "unavailable" and result.reasons == ("submissions_metadata_unavailable",)

@pytest.mark.parametrize(("selection_state","expected"), [("unavailable","insufficient_data"),("ambiguous","conflict"),("conflict","conflict")])
def test_j_k_selection_failure_mapping(selection_state, expected):
    from app.models.outlook_revenue_filing_selection import RevenueFilingSelectionResult
    selected=RevenueFilingSelectionResult(policy_version="revenue-operand-filing-selection-1", issuer="Issuer", cik=CIK,
        target_fiscal_year=2025, state=selection_state,
        reason="quarter_filing_missing" if selection_state=="unavailable" else "multiple_quarter_candidates")
    result=service(settings(q4=True), lambda ticker: acquisition(gap_rows()),
        select_filings=lambda *args:selected).get_snapshot("TEST")
    assert result.state == expected and result.reasons == ("filing_selection_failed",)

def test_direct_projection_maps_through_existing_dto_mapper():
    result=service(settings(), lambda ticker: acquisition(consecutive(5))).get_snapshot("TEST")
    dto=_revenue_history(result.projection)
    assert dto.availability == "available" and len(dto.points) == 5
    insufficient=service(settings(q4=False), lambda ticker: acquisition(consecutive(4))).get_snapshot("TEST")
    assert _revenue_history(insufficient.projection).availability == "insufficient_data"

def test_same_ticker_concurrent_calls_single_flight_and_different_keys_are_independent():
    barrier=Barrier(2); lock=Lock(); calls=[]
    def acquire(ticker):
        with lock: calls.append(ticker)
        if ticker in {"AAA","BBB"}: barrier.wait()
        return acquisition(consecutive(5,ticker), ticker=ticker)
    svc=service(settings(), acquire)
    with ThreadPoolExecutor(max_workers=2) as pool:
        different=list(pool.map(svc.get_snapshot,["AAA","BBB"]))
    assert all(row.state=="available" for row in different)
    calls.clear()
    gate=Barrier(2)
    def same_acquire(ticker): calls.append(ticker); gate.wait(timeout=.1); return acquisition(consecutive(5))
    # A deterministic blocking acquisition proves the second caller joins the first future.
    event=Lock(); event.acquire()
    def blocked(ticker): calls.append(ticker); event.acquire(); event.release(); return acquisition(consecutive(5))
    svc=service(settings(), blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(svc.get_snapshot,"TEST") for _ in range(2)]
        import time; time.sleep(.05); event.release(); results=[future.result() for future in futures]
    assert len(calls)==1 and all(row.state=="available" for row in results)

def test_repeated_deterministic_composition_preserves_fingerprint():
    acq=acquisition(consecutive(5)); svc=service(settings(), lambda ticker: acq)
    assert svc.get_snapshot("TEST").evidence_fingerprint == svc.get_snapshot("TEST").evidence_fingerprint

def test_request_ceiling_direct_is_three():
    result=service(settings(), lambda ticker: acquisition(consecutive(5), requests=3)).get_snapshot("TEST")
    assert result.request_accounting.total_sec_http_attempts == 3

def test_q4_repair_runs_reviewed_generic_pipeline_and_respects_seven_attempt_ceiling():
    import importlib.util
    path=Path(__file__).with_name("test_revenue_q4_runtime_input.py")
    spec=importlib.util.spec_from_file_location("runtime_input_fixtures", path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    runtime_inputs=module.inputs
    selected, retrieved = runtime_inputs()
    periods=((2025,"Q1",datetime(2025,1,1).date(),datetime(2025,3,31).date()),
        (2025,"Q2",datetime(2025,4,1).date(),datetime(2025,6,30).date()),
        (2025,"Q3",datetime(2025,7,1).date(),datetime(2025,9,30).date()),
        (2026,"Q1",datetime(2026,1,1).date(),datetime(2026,3,31).date()),
        (2026,"Q2",datetime(2026,4,1).date(),datetime(2026,6,30).date()),
        (2026,"Q3",datetime(2026,7,1).date(),datetime(2026,9,30).date()))
    rows=[observation(year,quarter,start,end,100+index) for index,(year,quarter,start,end) in enumerate(periods)]
    result=service(settings(q4=True), lambda ticker: acquisition(rows),
        select_filings=lambda *args:selected, retrieve_documents=lambda value:retrieved).get_snapshot("TEST")
    assert result.state == "available" and result.q4_attempted
    assert result.derivation.observation.exact_decimal_value == Decimal("340")
    assert result.reconciliation.authoritative_source_kind == "derived"
    assert len(result.projection.points) == 7
    assert result.projection.summary.available_qoq_comparisons == 6
    assert result.projection.summary.available_yoy_comparisons == 3
    assert sum(point.derived for point in result.projection.points) == 1
    assert result.request_accounting.total_sec_http_attempts == 7

@pytest.mark.parametrize(("ticker","year","expected","next_count","points","qoq","yoy"), [
    ("AAPL",2025,Decimal("102466000000"),3,7,6,3),
    ("NVDA",2026,Decimal("68127000000"),2,6,5,2),
])
def test_t_u_retained_aapl_nvda_offline_end_to_end(ticker,year,expected,next_count,points,qoq,yoy):
    import importlib.util
    path=Path(__file__).with_name("test_revenue_q4_runtime_input.py")
    spec=importlib.util.spec_from_file_location(f"runtime_fixture_{ticker}", path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    selected,retrieved,_,_=module.retained_fixture_inputs(ticker,year)
    qualified=[]
    for item in retrieved.documents:
        from app.services.outlook_structured.inline_revenue_operand import qualify_inline_revenue_operand
        qualified.append(qualify_inline_revenue_operand(item.selected_document,item.body).operand)
    by_role={row.role:row for row in qualified}; rows=[]
    for role in ("Q1","Q2","Q3"):
        operand=by_role[role]
        rows.append(observation(year,role,operand.context.period_start,operand.context.period_end,100,ticker,selected.selected_filings[0].document.cik))
    start=by_role["FY"].context.period_end+timedelta(days=1)
    for index in range(next_count):
        end=start+timedelta(days=89)
        rows.append(observation(year+1,f"Q{index+1}",start,end,200+index,ticker,selected.selected_filings[0].document.cik))
        start=end+timedelta(days=1)
    result=service(settings(q4=True),adapter_acquirer(rows,ticker,selected),
        select_filings=lambda *args:selected,retrieve_documents=lambda value:retrieved).get_snapshot(ticker)
    assert result.state=="available" and result.derivation.observation.exact_decimal_value==expected
    assert result.reconciliation.authoritative_source_kind=="derived"
    assert (len(result.projection.points),result.projection.summary.available_qoq_comparisons,
        result.projection.summary.available_yoy_comparisons)==(points,qoq,yoy)

def test_source_has_no_direct_q4_index_provider_ai_frontend_or_new_arithmetic():
    source=(Path(__file__).parents[1]/"app/services/outlook_structured/revenue_history_snapshot.py").read_text()
    for forbidden in ("direct_q4", "index.json", "exhibit", "configured_providers",
            "outlook_ai", "frontend", "FY - Q1", "normalized_value -"):
        assert forbidden not in source
