from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import numpy as np
import pandas as pd
import pytest

from app.config import Settings
from app.services.outlook import assess_providers
from app.services.outlook_evidence import assess_evidence, freshness
from app.services.outlook_structured.history import OutlookHistory
from app.services.outlook_structured.industry import (BENCHMARKS, INDUSTRY_ALIASES, INDUSTRY_BENCHMARKS,
    HISTORY_MAX_POINTS, INDUSTRY_TAXONOMY_VERSION, IndustryEvidenceProvider, historical_projection,
    relative_state)
from app.services.outlook_structured.market import MarketEvidenceProvider

NOW = datetime(2026, 9, 18, 22, tzinfo=timezone.utc)
SEMIS = {"sector": "Technology", "industry": "Semiconductors", "quoteType": "EQUITY", "exchange": "NMS"}


def frame(rate=.002, periods=100):
    return pd.DataFrame({"Close": 100 * np.exp(np.arange(periods) * rate)},
        index=pd.bdate_range(end="2026-09-18", periods=periods))


def setup(info=None, rates=None, peers=None):
    settings = Settings(_env_file=None, environment="test")
    rates = rates or {}
    loader = Mock(side_effect=lambda symbol, *a: frame(rates.get(symbol, .002)))
    metadata = Mock(return_value=SEMIS if info is None else info)
    peer_loader = Mock(return_value=peers or
        ["NVDA", "AVGO", "AMD", "QCOM", "TXN", "MU", "INTC", "ADI", "NXPI", "MCHP", "ON"])
    provider = IndustryEvidenceProvider(settings, OutlookHistory(settings, loader=loader),
                                        metadata, peer_loader, lambda: NOW)
    return provider, loader, metadata, peer_loader


def test_versioned_bounded_taxonomy():
    assert INDUSTRY_TAXONOMY_VERSION == "1" and len(BENCHMARKS) == 11
    assert 10 <= len(INDUSTRY_ALIASES) <= 30
    assert set(INDUSTRY_BENCHMARKS) <= {value[0] for value in INDUSTRY_ALIASES.values()}


@pytest.mark.parametrize("raw,key,symbol", [("Semiconductors", "semiconductors", "SOXX"),
    ("Software - Infrastructure", "software_infrastructure", "IGV"),
    ("Banks - Diversified", "banks_diversified", "KBE"),
    ("Drug Manufacturers - General", "pharmaceuticals", "IHE"),
    ("Aerospace & Defense", "aerospace_defense", "ITA")])
def test_precise_mappings(raw, key, symbol):
    result = setup(info={**SEMIS, "industry": raw})[0].inspect("TEST")
    assert (result["normalized_industry"], result["benchmark_symbol"], result["benchmark_type"]) == (key, symbol, "industry_etf")
    assert result["classification_quality"] == "exact_industry"


@pytest.mark.parametrize("ticker,industry,sector,benchmark", [("AAPL", "Consumer Electronics", "Technology", "XLK"),
    ("GOOGL", "Internet Content & Information", "Communication Services", "XLC"),
    ("WMT", "Discount Stores", "Consumer Defensive", "XLP"),
    ("TSLA", "Auto Manufacturers", "Consumer Cyclical", "XLY"),
    ("SMCI", "Computer Hardware", "Technology", "XLK")])
def test_sector_fallback_avoids_broad_peer_sample(ticker, industry, sector, benchmark):
    provider, _, _, peer_loader = setup(info={**SEMIS, "industry": industry, "sector": sector})
    result = provider.inspect(ticker)
    assert result["benchmark_symbol"] == benchmark and result["classification_quality"] == "sector_fallback"
    assert result["fallback_reason"] == "unsupported_industry" and result["peer_sample"] == []
    peer_loader.assert_not_called()


def test_nvda_and_tsla_known_regressions():
    precise = setup()[0].inspect("NVDA")
    assert precise["benchmark_symbol"] == "SOXX" and not {"AAPL", "MSFT"} & set(precise["peer_sample"])
    provider, _, _, peers = setup(info={**SEMIS, "industry": "Auto Manufacturers", "sector": "Consumer Cyclical"})
    fallback = provider.inspect("TSLA")
    assert fallback["benchmark_symbol"] == "XLY" and fallback["classification_quality"] == "sector_fallback"
    assert not {"AMZN", "HD", "MCD"} & set(fallback["peer_sample"])
    peers.assert_not_called()


def test_health_and_relative_strength_remain_separate():
    provider = setup(rates={"SOXX": -.002, "NVDA": .002})[0]
    evidence = provider.get_evidence("NVDA")
    assert [e.event_type.value for e in evidence] == ["sector_performance", "industry_other"]
    assert [int(e.impact) for e in evidence] == [-1, 1]
    result = provider.inspect("NVDA")
    assert result["industry_health_state"] == "negative"
    assert result["relative_performance_state"] == "strongly_outperforming"
    assert assess_providers("NVDA", [provider], now=NOW).categories["industry"].label == "Mixed"


def test_relative_states_and_noise_deadbands():
    assert [relative_state(*pair) for pair in [(.09, .13), (.04, .06), (.02, -.02),
        (-.04, -.06), (-.09, -.13), (.04, -.06)]] == ["strongly_outperforming", "outperforming",
        "roughly_in_line", "underperforming", "strongly_underperforming", "mixed"]


def test_breadth_partial_failures_and_target_exclusion():
    provider, loader, *_ = setup()
    original = loader.side_effect
    loader.side_effect = lambda symbol, *a: (_ for _ in ()).throw(RuntimeError("fixture")) if symbol in {"AMD", "QCOM"} else original(symbol, *a)
    result = provider.inspect("NVDA")
    assert "NVDA" not in result["peer_sample"]
    assert result["configured_peer_count"] == 10 and result["valid_peer_count"] == 8
    assert result["breadth_state"] == "positive"


def test_fewer_than_five_peers_does_not_remove_core_facts():
    provider, loader, *_ = setup(peers=["P1", "P2", "P3", "P4"])
    result = provider.inspect("NVDA")
    assert result["status"] == "available" and len(result["evidence"]) == 2
    assert result["valid_peer_count"] == 4 and result["breadth_state"] == "unavailable"
    assert loader.call_count == 6


def test_missing_and_unsupported_industry_fall_back():
    for industry, reason in [(None, "missing_industry"), ("Conglomerates", "unsupported_industry")]:
        result = setup(info={**SEMIS, "industry": industry})[0].inspect("AAPL")
        assert result["benchmark_symbol"] == "XLK" and result["fallback_reason"] == reason


@pytest.mark.parametrize("info,status", [({}, "error"),
    ({**SEMIS, "sector": "Unknown", "industry": "Unknown"}, "insufficient_data"),
    ({**SEMIS, "quoteType": "ETF"}, "insufficient_data")])
def test_invalid_classification_or_instrument(info, status):
    provider, loader, metadata, _ = setup(info=info)
    for _ in range(2):
        assert assess_providers("AAPL", [provider], now=NOW).categories["industry"].status == status
    assert metadata.call_count == 1 and loader.call_count == 0


def test_industry_benchmark_failure_uses_sector_fallback():
    provider, loader, *_ = setup()
    loader.side_effect = lambda symbol, *a: frame(periods=20) if symbol == "SOXX" else frame()
    result = provider.inspect("NVDA")
    assert result["benchmark_symbol"] == "XLK" and result["benchmark_type"] == "sector_etf"
    assert result["classification_quality"] == "sector_fallback"
    assert result["fallback_reason"] == "industry_benchmark_history_unavailable"


def test_short_company_history_preserves_health_only():
    provider, loader, *_ = setup()
    loader.side_effect = lambda symbol, *a: frame(periods=20) if symbol == "IPO" else frame()
    result = provider.inspect("IPO")
    assert result["status"] == "partial" and len(result["evidence"]) == 1
    assert result["relative_performance_state"] == "unavailable"


def test_bounded_cached_calls_and_defensive_copies():
    provider, loader, metadata, peers = setup()
    first = provider.get_evidence("NVDA")
    assert provider.get_evidence("NVDA") == first and loader.call_count == 12
    assert metadata.call_count == peers.call_count == 1
    snapshot = provider.inspect("NVDA")
    snapshot["evidence"][0].source_details["benchmark_symbol"] = "BAD"
    assert provider.get_evidence("NVDA")[0].source_details["benchmark_symbol"] == "SOXX"
    provider.calculations.entries.clear()
    provider.get_evidence("NVDA")
    assert loader.call_count == 12 and metadata.call_count == peers.call_count == 1


def test_market_boundary_and_shared_history():
    provider, loader, *_ = setup()
    market = MarketEvidenceProvider(provider.settings, provider.history, lambda: NOW)
    result = assess_providers("NVDA", [market, provider], now=NOW)
    assert result.available_categories == 2
    assert {e.event_type.value for e in result.categories["market"].evidence} == {"broad_market_trend", "volatility"}
    assert {e.event_type.value for e in result.categories["industry"].evidence} == {"sector_performance", "industry_other"}
    assert sum(call.args[0] == "SPY" for call in loader.call_args_list) == 1


def test_outlook_history_explicitly_requests_adjusted_prices(monkeypatch):
    calls = []
    monkeypatch.setattr("app.services.outlook_structured.history.get_price_history",
        lambda symbol, period, interval, **kwargs: calls.append((symbol, period, interval, kwargs)) or frame())
    history = OutlookHistory(Settings(_env_file=None, environment="test"))
    history("NVDA", "6mo", "1d")
    assert calls == [("NVDA", "6mo", "1d", {"auto_adjust": True})]


def test_history_windows_rebase_independently_and_use_adjusted_close_only():
    dates = pd.bdate_range(end="2026-09-18", periods=100)
    company = pd.DataFrame({"Close": np.arange(100, 200, dtype=float), "Dividends": [0] * 99 + [2],
                            "Stock Splits": [0] * 50 + [2] + [0] * 49}, index=dates)
    benchmark = pd.DataFrame({"Close": np.arange(200, 300, dtype=float)}, index=dates)
    accepted_company = (company.set_axis([x.date() for x in dates]), NOW)
    accepted_benchmark = (benchmark.set_axis([x.date() for x in dates]), NOW)
    result = historical_projection("NVDA", "SOXX", "ETF", "industry_etf", "exact_industry", None,
        "1", "1", accepted_company, accepted_benchmark, NOW)
    assert result["available_windows"] == ["1M", "3M", "6M"]
    one, three = result["windows"]["1M"], result["windows"]["3M"]
    assert one[0]["company_cumulative_return"] == three[0]["company_cumulative_return"] == 0
    assert one[-1]["company_cumulative_return"] == pytest.approx(100 * (199 / 178 - 1))
    assert three[-1]["company_cumulative_return"] == pytest.approx(100 * (199 / 136 - 1))
    assert one[-1]["relative_performance"] == pytest.approx(
        one[-1]["company_cumulative_return"] - one[-1]["benchmark_cumulative_return"])
    assert "does not independently reconstruct or verify" in result["qualifier"]
    assert result["price_adjustment_basis"] == "yahoo_auto_adjust_true"


def test_history_alignment_gaps_bounds_and_invalid_rows():
    dates = pd.bdate_range(end="2026-09-18", periods=150)
    company = pd.DataFrame({"Close": np.linspace(100, 150, 150)}, index=[x.date() for x in dates])
    benchmark = pd.DataFrame({"Close": np.linspace(200, 260, 150)}, index=[x.date() for x in dates])
    company = company.drop(company.index[-10]).copy()
    company.loc[company.index[-9], "Close"] = np.nan
    result = historical_projection("NVDA", "SOXX", "ETF", "industry_etf", "exact_industry", None,
        "1", "1", (company, NOW), (benchmark, NOW), NOW)
    assert result["coverage"]["has_gaps"] is True
    assert result["coverage"]["company_missing_session_count"] == 2
    assert result["coverage"]["common_session_count"] <= HISTORY_MAX_POINTS
    assert all(np.isfinite(point["company_cumulative_return"])
        for rows in result["windows"].values() for point in rows)


def test_duplicate_dates_and_stale_or_incomplete_history_fail_existing_gate():
    provider = setup()[0]
    duplicate = frame()
    duplicate = pd.concat([duplicate, duplicate.iloc[[-1]]])
    assert provider._history("NVDA", NOW) is not None
    provider.history = lambda *_: duplicate
    assert provider._history("NVDA", NOW) is None
    provider.history = lambda *_: frame().set_axis(pd.bdate_range(end="2026-08-01", periods=100))
    assert provider._history("NVDA", NOW) is None
    intraday = frame().set_axis(pd.bdate_range(end="2026-09-18", periods=100))
    provider.history = lambda *_: intraday
    assert provider._history("NVDA", datetime(2026, 9, 18, 19, tzinfo=timezone.utc))[1].date().isoformat() == "2026-09-17"


def test_final_fallback_benchmark_owns_history_and_no_duplicate_retrieval():
    provider, loader, *_ = setup()
    loader.side_effect = lambda symbol, *a: frame(periods=20) if symbol == "SOXX" else frame(periods=100)
    result = provider.inspect("NVDA")
    assert result["history"]["benchmark"]["symbol"] == "XLK"
    assert result["history"]["benchmark"]["classification_quality"] == "sector_fallback"
    assert sum(call.args[0] == "NVDA" for call in loader.call_args_list) == 1
    assert sum(call.args[0] == "XLK" for call in loader.call_args_list) == 1


def test_freshness_evaluation_and_http_contract(monkeypatch):
    import asyncio
    from unittest.mock import patch
    from app.auth import get_current_user
    from app.main import app
    from tests.test_authenticated_api_isolation import call_asgi
    provider = setup()[0]
    evidence = provider.get_evidence("NVDA")
    assert freshness(evidence[0], NOW + timedelta(days=7)) == 0
    assert assess_evidence("NVDA", evidence * 3, now=NOW)[0]["industry"].evidence_count == 2
    monkeypatch.setattr("app.main.analyze_outlook", lambda ticker: assess_providers(ticker, [provider], now=NOW))
    with patch.dict(app.dependency_overrides, {get_current_user: lambda: object()}):
        status, _, payload = asyncio.run(call_asgi("GET", "/outlook/NVDA"))
    assert status == 200 and payload["available_categories"] == 1
    assert payload["categories"]["industry"]["evidence"][0]["source_url"] == "https://finance.yahoo.com/quote/SOXX/"
