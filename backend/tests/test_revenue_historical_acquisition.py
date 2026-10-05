from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier, Lock

import pytest

from app.config import Settings
from app.services.outlook_structured.revenue_filing_selection import select_revenue_operand_filings
from app.services.outlook_structured.sec_history import (
    SecHistoricalFinancialProvider, adapt_sec_submissions,
)
from app.services.outlook_structured.transport import ProviderUnavailable

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
CIK = "0001045810"

def config(**changes):
    values=dict(environment="test",outlook_sec_history_enabled=True,
        outlook_sec_user_agent="TradePilot test@example.com",outlook_http_attempts=1)
    values.update(changes)
    return Settings(_env_file=None,**values)

def companyfacts(cik=1045810, issuer="Synthetic Issuer"):
    fact={"start":"2025-01-27","end":"2025-04-27","val":100,"accn":"0001045810-25-000116",
        "fy":2026,"fp":"Q1","form":"10-Q","filed":"2025-05-28"}
    return {"cik":cik,"entityName":issuer,"facts":{"us-gaap":{
        "RevenueFromContractWithCustomerExcludingAssessedTax":{"units":{"USD":[fact]}},
        "EarningsPerShareDiluted":{"units":{"USD/shares":[]}}}}}

def submissions(*, cik=1045810, issuer="Synthetic Issuer", primary="nvda.htm"):
    return {"cik":cik,"name":issuer,"filings":{"recent":{
        "accessionNumber":["0001045810-25-000116"],"form":["10-Q"],
        "filingDate":["2025-05-28"],"acceptanceDateTime":["2025-05-28T20:32:57Z"],
        "reportDate":["2025-04-27"],"primaryDocument":[primary]}}}

class Client:
    def __init__(self, facts=None, metadata=None, failure=None):
        self.facts=facts or companyfacts(); self.metadata=metadata or submissions()
        self.failure=failure; self.calls=[]; self.lock=Lock()
    def get(self,url,**kwargs):
        with self.lock: self.calls.append(url)
        if self.failure and self.failure in url: raise TimeoutError("synthetic")
        if "company_tickers" in url: return {"0":{"ticker":"NVDA","cik_str":1045810}}
        return self.facts if "companyfacts" in url else self.metadata

def test_a_d_cold_and_warm_bundle_request_bounds_and_atomic_evidence():
    client=Client(); provider=SecHistoricalFinancialProvider(config(),client,lambda:NOW)
    cold=provider.get_acquisition("nvda"); warm=provider.get_acquisition("NVDA")
    assert cold.snapshot.observations and cold.submissions.rows
    assert (cold.logical_requests,cold.http_attempts,cold.cache_state)==(3,3,"miss")
    assert (warm.logical_requests,warm.http_attempts,warm.cache_state)==(0,0,"success_hit")
    assert len(client.calls)==3 and cold.evidence_fingerprint==warm.evidence_fingerprint

def test_b_mapping_warm_second_ticker_costs_two_requests():
    class Multi(Client):
        def get(self,url,**kwargs):
            with self.lock: self.calls.append(url)
            if "company_tickers" in url: return {"0":{"ticker":"AAA","cik_str":1045810},"1":{"ticker":"BBB","cik_str":1045810}}
            return self.facts if "companyfacts" in url else self.metadata
    client=Multi(); provider=SecHistoricalFinancialProvider(config(),client,lambda:NOW)
    assert provider.get_acquisition("AAA").logical_requests==3
    assert provider.get_acquisition("BBB").logical_requests==2
    assert len(client.calls)==5

def test_e_f_exactly_one_attempt_and_each_resource_once():
    client=Client(); result=SecHistoricalFinancialProvider(config(),client,lambda:NOW).get_acquisition("NVDA")
    assert result.http_attempts==3
    assert sum("companyfacts" in url for url in client.calls)==1
    assert sum("submissions" in url for url in client.calls)==1

def test_h_same_submissions_rows_preserve_exact_source_values():
    payload=submissions(primary="source.htm")
    result=adapt_sec_submissions(payload,issuer="Synthetic Issuer",cik=CIK,source_identity="same-payload")
    row=result.rows[0]
    assert row.primary_document=="source.htm" and row.source_ordinal==0
    assert result.source_identity=="same-payload"

def test_i_k_fingerprint_ignores_cache_and_request_metadata():
    provider=SecHistoricalFinancialProvider(config(),Client(),lambda:NOW)
    cold=provider.get_acquisition("NVDA"); warm=provider.get_acquisition("NVDA")
    assert cold.evidence_fingerprint==warm.evidence_fingerprint
    assert cold.logical_requests!=warm.logical_requests and cold.cache_state!=warm.cache_state

@pytest.mark.parametrize("payload", [{}, {"filings":{"recent":{"accessionNumber":[]}}}])
def test_l_malformed_submissions_fails_closed(payload):
    with pytest.raises(ProviderUnavailable,match="submissions_schema_invalid"):
        adapt_sec_submissions(payload,issuer="Synthetic Issuer",cik=CIK,source_identity="fixture")

def test_m_missing_primary_document_is_preserved_not_invented():
    result=adapt_sec_submissions(submissions(primary=""),issuer="Synthetic Issuer",cik=CIK,source_identity="fixture")
    assert result.rows[0].primary_document is None

@pytest.mark.parametrize("changes", [{"issuer":"Other"},{"cik":"0000000001"}])
def test_n_o_submissions_identity_mismatch_fails_closed(changes):
    identity={"issuer":"Synthetic Issuer","cik":CIK}; identity.update(changes)
    with pytest.raises(ProviderUnavailable,match="submissions_issuer_mismatch"):
        adapt_sec_submissions(submissions(),source_identity="fixture",**identity)

@pytest.mark.parametrize("failure", ["company_tickers","companyfacts","submissions"])
def test_p_r_dependency_failures_are_isolated_and_not_retried(failure):
    client=Client(failure=failure); provider=SecHistoricalFinancialProvider(config(),client,lambda:NOW)
    with pytest.raises(ProviderUnavailable): provider.get_acquisition("NVDA")
    matching=sum(failure in url for url in client.calls)
    assert matching==1

def test_one_attempt_configuration_is_enforced_only_on_acquisition_adapter():
    provider=SecHistoricalFinancialProvider(config(outlook_http_attempts=2),Client(),lambda:NOW)
    with pytest.raises(ProviderUnavailable,match="single_attempt_required"):
        provider.get_acquisition("NVDA")
    assert provider.get_history("NVDA").observations

def test_u_same_ticker_concurrent_cold_acquisition_single_flights():
    client=Client(); provider=SecHistoricalFinancialProvider(config(),client,lambda:NOW)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(provider.get_acquisition,["NVDA"]*4))
    assert len(client.calls)==3 and sum(row.cache_state=="miss" for row in rows)==1
    assert len({row.evidence_fingerprint for row in rows})==1

def test_v_different_ticker_cache_coordination_does_not_serialize_loaders():
    barrier=Barrier(2)
    class Multi(Client):
        def get(self,url,**kwargs):
            with self.lock: self.calls.append(url)
            if "company_tickers" in url: return {"0":{"ticker":"AAA","cik_str":1045810},"1":{"ticker":"BBB","cik_str":1045810}}
            if "companyfacts" in url: barrier.wait(timeout=2); return self.facts
            return self.metadata
    client=Multi(); provider=SecHistoricalFinancialProvider(config(),client,lambda:NOW)
    # Warm the one shared ticker mapping, then prove both per-ticker loaders reach Company Facts together.
    provider.mapping_cache.get("sec_ticker_mapping",lambda:{"AAA":CIK,"BBB":CIK},86400)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(provider.get_acquisition,["AAA","BBB"]))
    assert all(row.snapshot.observations for row in results)

def test_y_success_ttl_refreshes_once_after_expiry():
    now=[0.0]; client=Client(); provider=SecHistoricalFinancialProvider(
        config(outlook_sec_history_cache_ttl=300),client,lambda:NOW,cache_clock=lambda:now[0])
    provider.get_acquisition("NVDA"); provider.get_acquisition("NVDA"); assert len(client.calls)==3
    now[0]=301; refreshed=provider.get_acquisition("NVDA")
    assert refreshed.logical_requests==2 and len(client.calls)==5

def test_z_failure_cache_expires_after_sixty_seconds():
    now=[0.0]
    class Flaky(Client):
        def __init__(self): super().__init__(); self.fail_once=True
        def get(self,url,**kwargs):
            with self.lock:self.calls.append(url)
            if "company_tickers" in url:return {"0":{"ticker":"NVDA","cik_str":1045810}}
            if "companyfacts" in url and self.fail_once:
                self.fail_once=False; raise TimeoutError("synthetic")
            return self.facts if "companyfacts" in url else self.metadata
    client=Flaky(); provider=SecHistoricalFinancialProvider(config(),client,lambda:NOW,cache_clock=lambda:now[0])
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):provider.get_acquisition("NVDA")
    assert len(client.calls)==2
    now[0]=61
    assert provider.get_acquisition("NVDA").snapshot.observations
    assert len(client.calls)==4

def test_w_x_every_actual_call_is_sec_scoped_and_warm_hits_dispatch_nothing():
    class Scoped(Client):
        def __init__(self):super().__init__();self.providers=[]
        def get(self,url,**kwargs):self.providers.append(kwargs.get("provider"));return super().get(url,**kwargs)
    client=Scoped();provider=SecHistoricalFinancialProvider(config(),client,lambda:NOW)
    provider.get_acquisition("NVDA");provider.get_acquisition("NVDA")
    assert client.providers==["sec","sec","sec"]

def test_aa_ab_retained_identity_rows_are_suitable_for_generic_selector():
    import json
    artifact=json.loads((Path(__file__).parents[2]/"docs/diagnostics/phase6b5c2a5w2-inline-revenue-metadata-20261001.json").read_text())
    for ticker,year in (("AAPL",2025),("NVDA",2026)):
        roles=[row for row in artifact["manifest"]["roles"] if row["ticker"]==ticker]
        payload={"cik":int(roles[0]["cik"]),"name":roles[0]["issuer"],"filings":{"recent":{
            "accessionNumber":[row["accession"] for row in roles],"form":[row["form"] for row in roles],
            "filingDate":[row["filing_date"] for row in roles],"acceptanceDateTime":[row["acceptance_time"] for row in roles],
            "reportDate":[row["report_period_end"] for row in roles],"primaryDocument":[row["primary_document"] for row in roles]}}}
        typed=adapt_sec_submissions(payload,issuer=roles[0]["issuer"],cik=roles[0]["cik"],source_identity="retained")
        from app.models.outlook_revenue_filing_selection import RevenueFilingQuarterAnchor,RevenueFilingSelectionRequest
        by_role={row["expected_role"]:row for row in roles}
        request=RevenueFilingSelectionRequest(ticker=ticker,issuer=roles[0]["issuer"],cik=roles[0]["cik"],target_fiscal_year=year,
            quarter_anchors=tuple(RevenueFilingQuarterAnchor(role=role,report_period_end=by_role[role]["report_period_end"]) for role in ("Q1","Q2","Q3")))
        assert select_revenue_operand_filings(request,typed).state=="selected"

def test_ac_ag_adapter_source_has_no_downstream_network_or_registration_work():
    source=(Path(__file__).parents[1]/"app/services/outlook_structured/sec_history.py").read_text()
    section=source[source.index("def adapt_sec_submissions"):source.index("def comparison_compatibility")]
    for forbidden in ("select_revenue_operand_filings","retrieve_documents","derive_revenue_q4",
            "reconcile_revenue_q4","configured_providers","outlook_analysis"):
        assert forbidden not in section
