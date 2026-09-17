from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch
from urllib.error import HTTPError

import pandas as pd
import pytest

from app.config import Settings
from app.services.outlook import assess_providers, analyze_outlook
from app.services.outlook_evidence import assess_evidence
from app.services.outlook_structured.sec import SecEvidenceProvider, ticker_mapping
from app.services.outlook_structured.fred import FredEvidenceProvider, macro_change, observations
from app.services.outlook_structured.market import MarketEvidenceProvider
from app.services.outlook_structured.policy import MACRO_SERIES
from app.services.outlook_structured.transport import Cache, JsonClient, ProviderUnavailable

NOW = datetime(2026, 9, 14, 22, tzinfo=timezone.utc)


def settings(**kwargs):
    return Settings(_env_file=None, environment="test", outlook_sec_user_agent="TradePilot testing operator@example.com",
                    fred_api_key="test-secret-not-real", **kwargs)


class SecClient:
    def __init__(self, items=None):
        self.calls = []
        self.items = items or ["1.05", "1.03", "5.02", "", ""]
    def get(self, url, **kwargs):
        self.calls.append(url)
        if "company_tickers" in url:
            return {"0": {"ticker": "AAPL", "cik_str": 320193}, "1": {"ticker": "BRK-B", "cik_str": 1067983}}
        forms = ["8-K", "8-K", "8-K", "10-Q", "10-K"]
        return {"filings": {"recent": {
            "form": forms, "items": self.items,
            "accessionNumber": [f"0000320193-26-{i:06}" for i in range(5)],
            "filingDate": ["2026-09-14"] * 5,
            "acceptanceDateTime": ["2026-09-14T12:00:00Z"] * 5,
            "reportDate": ["2026-09-12"] * 5, "primaryDocument": ["report.htm"] * 5,
        }}}


def test_sec_identity_mapping_and_shared_cache():
    client = SecClient()
    provider = SecEvidenceProvider(settings(), client, lambda: NOW)
    assert ticker_mapping({"0": {"ticker": "BRK-B", "cik_str": 1067983}})["BRK-B"] == "0001067983"
    first = provider.get_evidence("AAPL")
    assert provider.get_evidence("aapl") == first
    provider.get_evidence("brk.b")
    assert len(client.calls) == 3  # one mapping, two issuer submissions
    assert provider.get_evidence("MISSING") == []
    assert provider.get_evidence("invalid symbol") == []
    assert len(client.calls) == 3


def test_sec_events_provenance_and_ambiguous_non_scoring():
    provider = SecEvidenceProvider(settings(), SecClient(), lambda: NOW)
    items = provider.get_evidence("AAPL")
    assert [int(item.impact) for item in items] == [-1, -2, 0, 0, 0]
    assert [item.scoring_eligible for item in items] == [True, True, False, False, False]
    assert items[0].source_details["cik"] == "0000320193"
    assert items[0].source_details["event_date"] == "2026-09-12"
    assert items[0].source_details["form"] == "8-K"
    assert "000032019326000000" in str(items[0].source_url)
    categories, _ = assess_evidence("AAPL", items + items, now=NOW)
    assert categories["company"].evidence_count == 2
    assert categories["company"].label == "Negative"
    categories, _ = assess_evidence("AAPL", items[2:], now=NOW)
    assert categories["company"].label is None


@pytest.mark.parametrize("item", ["2.01", "1.01", "3.02", "2.05", "unknown"])
def test_sec_ambiguous_items_never_get_direction(item):
    data = SecEvidenceProvider(settings(), SecClient([item]*5), lambda: NOW).get_evidence("AAPL")
    assert all(row.impact == 0 and not row.scoring_eligible for row in data)


class FredClient:
    def __init__(self):
        self.calls = []
        self.fail = False
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs["params"]["series_id"]))
        if self.fail:
            raise TimeoutError("test-secret-not-real")
        if url.endswith("/series"):
            return {"seriess": [{"title": kwargs["params"]["series_id"], "last_updated": "2026-09-14T12:00:00+00:00"}]}
        series = kwargs["params"]["series_id"]
        if series == "A191RL1Q225SBEA":
            dates = pd.date_range("2023-10-01", periods=12, freq="QS")
        else:
            dates = pd.date_range("2025-01-01", periods=20, freq="MS")
        values = [100 + i for i in range(len(dates))] if series == "CPIAUCSL" else [5-i*0.1 for i in range(len(dates))]
        return {"realtime_start": "2026-09-14", "observations": [{"date": str(d.date()), "value": str(v)} for d,v in zip(dates, values)]}


def test_fred_normalization_trends_provenance_and_cross_ticker_cache():
    client = FredClient()
    provider = FredEvidenceProvider(settings(), client, lambda: NOW)
    first = provider.get_evidence("AAPL")
    second = provider.get_evidence("MSFT")
    assert len(client.calls) == 10 and len(first) == len(second) == 5
    assert first[0].raw_provider_id == second[0].raw_provider_id
    assert first[0].id != second[0].id
    assert first[0].observed_at == second[0].observed_at
    assert first[0].impact == 1
    assert first[0].source_details["series_id"] == "FEDFUNDS"
    assert "comparison_value" in first[0].source_details
    assert len(first[1].source_details["observations_used"]) == 16
    assert observations({"observations": [{"date": "2026-01-01", "value": "."}]}) == []


@pytest.mark.parametrize("values, expected", [([1,2,3,4], -1), ([4,3,2,1], 1), ([1,1,1,1], 0)])
def test_fred_change_direction(values, expected):
    rows = [(datetime(2026, i+1, 1).date(), value) for i,value in enumerate(values)]
    assert macro_change(MACRO_SERIES[0], rows)[0] == expected


def test_fred_stale_missing_and_missing_credentials():
    provider = FredEvidenceProvider(Settings(_env_file=None, environment="test", fred_api_key=""), FredClient(), lambda: NOW)
    assert provider.unavailable_reason == "missing_configuration" and provider.get_evidence("AAPL") == []
    client = FredClient()
    provider = FredEvidenceProvider(settings(), client, lambda: NOW+timedelta(days=200))
    assert provider.get_evidence("AAPL") == []
    class Missing(FredClient):
        def get(self, url, **kwargs):
            payload = super().get(url, **kwargs)
            if "observations" in payload:
                payload["observations"][2]["value"] = "."
                payload["observations"] = payload["observations"][-1:]
            return payload
    assert FredEvidenceProvider(settings(), Missing(), lambda: NOW).get_evidence("AAPL") == []


def market_history(direction=1, vix=18, missing=()):
    calls = []
    def history(symbol, period, interval):
        calls.append(symbol)
        if symbol in missing:
            raise TimeoutError("fixture failure")
        values = [vix]*80 if symbol == "^VIX" else [100+direction*i*0.3 for i in range(80)]
        return pd.DataFrame({"Close": values}, index=pd.bdate_range(end="2026-09-14", periods=80))
    return history, calls


@pytest.mark.parametrize("direction,vix,label", [(1,12,"Positive"), (-1,30,"Negative"), (0,18,"Mixed")])
def test_market_regimes(direction, vix, label):
    history, calls = market_history(direction, vix)
    provider = MarketEvidenceProvider(settings(), history, lambda: NOW)
    first = provider.get_evidence("AAPL")
    second = provider.get_evidence("MSFT")
    assert len(calls) == 3 and len(first) == len(second) == 2
    categories, _ = assess_evidence("AAPL", first, now=NOW)
    assert categories["market"].label == label
    assert len(first[0].source_details["benchmarks"]) == 2
    assert first[0].observed_at == second[0].observed_at


def test_market_missing_index_and_provider_failure():
    history, calls = market_history(missing=("QQQ",))
    provider = MarketEvidenceProvider(settings(), history, lambda: NOW)
    items = provider.get_evidence("AAPL")
    assert len(items) == 2 and "unavailable" in items[0].summary
    history, calls = market_history(missing=("SPY", "QQQ", "^VIX"))
    provider = MarketEvidenceProvider(settings(), history, lambda: NOW)
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):
            provider.get_evidence("AAPL")
    assert len(calls) == 3


@pytest.mark.parametrize("factory,flag", [(SecEvidenceProvider,"outlook_sec_enabled"),
    (FredEvidenceProvider,"outlook_fred_enabled"), (MarketEvidenceProvider,"outlook_market_enabled")])
def test_disabled_providers(factory, flag):
    provider = factory(settings(**{flag: False}))
    assert provider.get_evidence("AAPL") == [] and provider.unavailable_reason == "disabled"


def test_sec_and_fred_timeout_are_cached(caplog):
    class Broken:
        calls = 0
        def get(self, *args, **kwargs):
            self.calls += 1
            raise TimeoutError("test-secret-not-real")
    for factory in (SecEvidenceProvider, FredEvidenceProvider):
        client = Broken()
        provider = factory(settings(), client, lambda: NOW)
        for _ in range(2):
            with pytest.raises(ProviderUnavailable):
                provider.get_evidence("AAPL")
        assert client.calls == 1
    assert "test-secret-not-real" not in caplog.text


def test_cache_expiry_failure_backoff_and_singleflight():
    now = [0]
    cache = Cache(clock=lambda: now[0], failure_ttl=2)
    calls = []
    def load():
        calls.append(1)
        return {"values": []}
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: cache.get("key", load, 10), range(5)))
    assert len(calls) == 1
    results[0]["values"].append(1)
    assert cache.get("key", load, 10)["values"] == []
    now[0] = 11
    cache.get("key", load, 10)
    assert len(calls) == 2


def test_json_client_timeout_retries_and_no_secret_logging(monkeypatch, caplog):
    from app.services.outlook_structured import transport
    calls = []
    def broken(request, timeout):
        calls.append(timeout)
        raise TimeoutError("secret-url")
    monkeypatch.setattr(transport, "urlopen", broken)
    monkeypatch.setattr(transport.FRED_GATE, "wait", lambda interval: None)
    with pytest.raises(ProviderUnavailable):
        JsonClient(settings(outlook_http_attempts=2)).get("https://api.stlouisfed.org/fred/series", provider="fred", params={"api_key": "secret-url"})
    assert calls == [5,5] and "secret-url" not in caplog.text
    def limited(request, timeout):
        raise HTTPError(request.full_url, 429, "limited", {}, None)
    monkeypatch.setattr(transport, "urlopen", limited)
    with pytest.raises(ProviderUnavailable):
        JsonClient(settings()).get("https://api.stlouisfed.org/fred/series", provider="fred")


def providers():
    history, _ = market_history(1,12)
    return [SecEvidenceProvider(settings(), SecClient(), lambda: NOW),
            FredEvidenceProvider(settings(), FredClient(), lambda: NOW),
            MarketEvidenceProvider(settings(), history, lambda: NOW)]


@pytest.mark.parametrize("count", [1,2,3])
def test_partial_outlook_counts_and_unsupported_categories(count):
    result = assess_providers("AAPL", providers()[:count], now=NOW)
    assert result.available_categories == count
    assert result.status == "partial" and result.value is not None
    assert result.categories["earnings"].status == "insufficient_data"
    for category in ("industry", "geopolitical"):
        assert result.categories[category].status == "unavailable"
    assert not result.metadata.uses_placeholder_data
    assert "test-secret-not-real" not in result.model_dump_json()


def test_failure_scoped_to_company_and_default_routing(monkeypatch):
    active = providers()
    def broken(ticker):
        raise TimeoutError("secret")
    active[0].get_evidence = broken
    monkeypatch.setattr("app.services.outlook.configured_providers", lambda: active)
    result = analyze_outlook("AAPL", now=NOW)
    assert result.available_categories == 2
    assert result.categories["company"].status == "error"
    assert result.categories["industry"].status == "unavailable"
    assert result.metadata.provider_status["sec"] == "error"


def test_all_disabled_and_default_completion_time():
    disabled = settings(outlook_sec_enabled=False, outlook_fred_enabled=False, outlook_market_enabled=False)
    result = assess_providers("AAPL", [SecEvidenceProvider(disabled), FredEvidenceProvider(disabled), MarketEvidenceProvider(disabled)], now=NOW)
    assert result.status == "placeholder"
    assert result.available_categories == 0


def test_fred_missing_latest_observation_is_not_backfilled():
    class MissingLatest(FredClient):
        def get(self, url, **kwargs):
            payload = super().get(url, **kwargs)
            if "observations" in payload:
                payload["observations"][-1]["value"] = "."
            return payload
    assert FredEvidenceProvider(settings(), MissingLatest(), lambda: NOW).get_evidence("AAPL") == []


def test_authenticated_http_returns_partial_structured_evidence(monkeypatch):
    import asyncio
    from app.main import app
    from app.auth import get_current_user
    from tests.test_authenticated_api_isolation import call_asgi
    monkeypatch.setattr("app.services.outlook.configured_providers", providers)
    with patch.dict(app.dependency_overrides, {get_current_user: lambda: object()}):
        # The fixture clock must also drive aggregation to avoid wall-clock dependency.
        from app.services.outlook import assess_providers as assess
        monkeypatch.setattr("app.main.analyze_outlook", lambda ticker: assess(ticker, providers(), now=NOW))
        status, _, payload = asyncio.run(call_asgi("GET", "/outlook/AAPL"))
    assert status == 200 and payload["available_categories"] == 3
    assert payload["metadata"]["uses_placeholder_data"] is False
    assert payload["categories"]["industry"]["value"] is None


def test_market_stale_or_partial_session_does_not_become_new_context():
    from app.services.outlook_structured.market import completed_history
    frame = pd.DataFrame({"Close": [100,101]}, index=pd.to_datetime(["2026-09-11", "2026-09-14"]))
    result, published = completed_history(frame, NOW.replace(hour=14))
    assert len(result) == 1 and published.day == 11
    assert completed_history(frame, NOW+timedelta(days=10)) is None


def test_sec_rate_gate_and_bounded_settings(monkeypatch):
    from app.services.outlook_structured import transport
    from pydantic import ValidationError
    clock = [0.0]
    sleeps = []
    monkeypatch.setattr(transport, "monotonic", lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(transport, "sleep", sleep)
    gate = transport.RateGate()
    gate.wait(1)
    gate.wait(1)
    assert sleeps == [1]
    with pytest.raises(ValidationError):
        settings(outlook_sec_request_interval=0.1)
    with pytest.raises(ValidationError):
        settings(outlook_http_attempts=3)
