from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from app.config import Settings
from app.services.outlook import assess_providers
from app.services.outlook_evidence import assess_evidence, freshness
from app.services.outlook_structured.history import OutlookHistory
from app.services.outlook_structured.industry import IndustryEvidenceProvider, BENCHMARKS
from app.services.outlook_structured.market import MarketEvidenceProvider
from app.services.outlook_structured.transport import ProviderUnavailable

NOW = datetime(2026, 9, 18, 22, tzinfo=timezone.utc)
INFO = {"sector": "Technology", "industry": "Consumer Electronics", "quoteType": "EQUITY", "exchange": "NMS"}


def frame(rate=.002):
    return pd.DataFrame({"Close": 100 * np.exp(np.arange(100) * rate)},
                        index=pd.bdate_range(end="2026-09-18", periods=100))


def setup(rate=.002, peer_rate=None, info=None):
    settings = Settings(_env_file=None, environment="test")
    history = Mock(side_effect=lambda s, *a: frame(0 if s == "SPY" else rate if s == "XLK" or peer_rate is None else peer_rate))
    metadata = Mock(return_value=INFO if info is None else info)
    peers = Mock(return_value=["AAPL", "NVDA", "P1", "P2", "P3", "P4", "P5", "P6"])
    shared = OutlookHistory(settings, loader=history)
    provider = IndustryEvidenceProvider(settings, shared, metadata, peers, lambda: NOW)
    return provider, history, metadata, peers


@pytest.mark.parametrize("rate,label,impact", [(.002, "Positive", 1), (-.002, "Negative", -1), (0, "Mixed", 0)])
def test_direction_and_horizons_are_one_event(rate, label, impact):
    provider, *_ = setup(rate)
    evidence = provider.get_evidence("AAPL")
    assert len(evidence) == 2
    assert [int(e.impact) for e in evidence] == [impact, impact]
    result = assess_providers("AAPL", [provider], now=NOW)
    assert result.categories["industry"].label == label
    assert result.available_categories == 1
    categories, _ = assess_evidence("AAPL", evidence * 3, now=NOW)
    assert categories["industry"].evidence_count == 2
    assert "relative_21" in evidence[0].source_details
    assert "relative_63" in evidence[0].source_details
    assert freshness(evidence[0], NOW + timedelta(days=7)) == 0


def test_bounded_cached_calls_and_target_exclusion():
    provider, history, metadata, peers = setup()
    first = provider.get_evidence("aapl")
    assert provider.get_evidence("AAPL") == first
    assert history.call_count == 8  # sector + SPY + six peers
    assert metadata.call_count == peers.call_count == 1
    assert "AAPL" not in first[1].source_details["peer_sample"]
    provider.calculations.entries.clear()
    provider.get_evidence("AAPL")
    assert metadata.call_count == peers.call_count == 1
    assert history.call_count == 8
    provider.get_evidence("NVDA")
    assert peers.call_count == 1
    assert metadata.call_count == 2
    assert history.call_count == 9  # target changes, one additional peer


def test_partial_peer_coverage_and_unrelated_failures():
    provider, history, *_ = setup()
    original = history.side_effect
    def load(symbol, *args):
        if symbol in {"P1", "P2"}:
            raise RuntimeError("offline fixture")
        return original(symbol, *args)
    history.side_effect = load
    items = provider.get_evidence("AAPL")
    assert len(items) == 2
    assert items[1].confidence == .65
    assert items[1].source_details["peer_coverage"] == 4
    assert assess_providers("AAPL", [provider], now=NOW).categories["industry"].status == "available"
    provider.get_evidence("NVDA")
    assert sum(c.args[0] == "P1" for c in history.call_args_list) == 1


@pytest.mark.parametrize("info,status", [({}, "error"), ({**INFO, "sector": "Unknown"}, "insufficient_data"),
                                          ({**INFO, "quoteType": "ETF"}, "insufficient_data")])
def test_missing_or_unsupported_classification(info, status):
    provider, history, metadata, _ = setup(info=info)
    for _ in range(2):
        result = assess_providers("AAPL", [provider], now=NOW)
        assert result.categories["industry"].status == status
    assert history.call_count == 0
    assert metadata.call_count == 1


def test_insufficient_history_failure_backoff_and_isolation():
    provider, history, metadata, _ = setup()
    history.side_effect = lambda *a: frame().iloc[-20:]
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):
            provider.get_evidence("AAPL")
    assert history.call_count == 1
    metadata.return_value = {**INFO, "sector": "Energy"}
    history.side_effect = lambda *a: frame()
    assert len(provider.get_evidence("XOM")) == 2


def test_no_peers_does_not_invent_second_event():
    provider, _, _, peers = setup()
    peers.side_effect = RuntimeError("no holdings")
    result = assess_providers("AAPL", [provider], now=NOW)
    assert result.categories["industry"].status == "insufficient_data"
    assert result.categories["industry"].evidence_count == 1


def test_market_boundary_and_shared_history():
    provider, history, *_ = setup()
    market = MarketEvidenceProvider(provider.settings, provider.history, lambda: NOW)
    result = assess_providers("AAPL", [market, provider], now=NOW)
    assert result.available_categories == 2
    assert {e.event_type.value for e in result.categories["market"].evidence} == {"broad_market_trend", "volatility"}
    assert {e.event_type.value for e in result.categories["industry"].evidence} == {"sector_performance", "industry_peer_breadth"}
    assert sum(c.args[0] == "SPY" for c in history.call_args_list) == 1
    before = assess_providers("AAPL", [market], now=NOW)
    assert before.available_categories == 1
    assert before.categories["market"] == result.categories["market"]


def test_mixed_peers_and_opposed_absolute_relative_signals():
    provider, history, *_ = setup()
    history.side_effect = lambda s, *a: frame(.004 if s == "SPY" else -.002 if s in {"P1", "P2", "P3"} else .002)
    items = provider.get_evidence("AAPL")
    assert items[0].source_details["trend_direction"] == 1
    assert items[0].source_details["relative_direction"] == -1
    assert all(e.impact == 0 for e in items)


def test_fresh_complete_sessions_only_and_mapping():
    assert len(BENCHMARKS) == 11
    provider, history, *_ = setup()
    history.side_effect = lambda *a: frame().set_axis(pd.bdate_range(end="2026-08-01", periods=100))
    with pytest.raises(ProviderUnavailable):
        provider.get_evidence("AAPL")


def test_cache_returns_defensive_copies():
    provider, *_ = setup()
    snapshot = provider.inspect("AAPL")
    snapshot["evidence"][0].source_details["benchmark"] = "BAD"
    assert provider.get_evidence("AAPL")[0].source_details["benchmark"] == "XLK"


def test_concurrent_requests_single_flight_and_ttl_expiration():
    from concurrent.futures import ThreadPoolExecutor
    provider, history, metadata, _ = setup()
    ticks = [0.0]
    for cache in (provider.calculations, provider.classifications, provider.memberships, provider.history.cache):
        cache.clock = lambda: ticks[0]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(provider.get_evidence, ["AAPL"] * 4))
    assert all(items == results[0] for items in results)
    assert history.call_count == 8 and metadata.call_count == 1
    ticks[0] = 1801
    provider.get_evidence("AAPL")
    assert history.call_count == 16 and metadata.call_count == 1
    ticks[0] = 604801
    provider.get_evidence("AAPL")
    assert metadata.call_count == 2


def test_failure_backoff_expires():
    provider, history, metadata, _ = setup()
    ticks = [0.0]
    provider.calculations.clock = provider.classifications.clock = lambda: ticks[0]
    metadata.side_effect = RuntimeError("fixture")
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):
            provider.get_evidence("AAPL")
    assert metadata.call_count == 1 and history.call_count == 0
    ticks[0] = 61
    metadata.side_effect = None
    assert len(provider.get_evidence("AAPL")) == 2
    assert metadata.call_count == 2


def test_partial_missing_spy_or_peer_history_does_not_fabricate_evidence():
    provider, history, *_ = setup()
    history.side_effect = lambda s, *a: frame().iloc[-20:] if s == "SPY" else frame()
    assert [e.event_type.value for e in provider.get_evidence("AAPL")] == ["industry_peer_breadth"]
    provider, history, *_ = setup()
    history.side_effect = lambda s, *a: frame() if s in {"XLK", "SPY"} else frame().iloc[-20:]
    assert [e.event_type.value for e in provider.get_evidence("AAPL")] == ["sector_performance"]


def test_http_existing_card_contract(monkeypatch):
    import asyncio
    from unittest.mock import patch
    from app.main import app
    from app.auth import get_current_user
    from tests.test_authenticated_api_isolation import call_asgi
    provider, *_ = setup()
    monkeypatch.setattr("app.main.analyze_outlook", lambda ticker: assess_providers(ticker, [provider], now=NOW))
    with patch.dict(app.dependency_overrides, {get_current_user: lambda: object()}):
        status, _, payload = asyncio.run(call_asgi("GET", "/outlook/AAPL"))
    assert status == 200 and payload["available_categories"] == 1
    industry = payload["categories"]["industry"]
    assert industry["label"] == "Positive" and industry["summary"]
    assert len(industry["factors"]) == 2 and len(industry["evidence"]) == 2
    assert industry["evidence"][0]["source_url"] == "https://finance.yahoo.com/quote/XLK/"
