"""Exercise the real analyzer through HTTP with deterministic market data."""
import asyncio
from unittest.mock import patch

import pandas as pd

from app.auth import get_current_user
from app.main import app
from app.services import analyzer
from tests.test_authenticated_api_isolation import call_asgi


def test_analysis_http_preserves_technical_and_setup_without_retired_score():
    closes = [100 + i * 0.1 + (i % 7) * 0.4 for i in range(180)]
    history = pd.DataFrame({
        "Open": closes, "Close": closes,
        "High": [value + 1 for value in closes],
        "Low": [value - 1 for value in closes],
        "Volume": [1000000] * len(closes),
    }, index=pd.date_range("2025-01-01", periods=len(closes)))
    with patch.dict(app.dependency_overrides, {get_current_user: lambda: object()}), patch(
        "app.services.analyzer.get_price_history", return_value=history
    ), patch.object(analyzer, "_analysis_cache", {}):
        status, _, payload = asyncio.run(call_asgi(
            "GET", "/analyze/TEST", query="period=1y&interval=1wk"
        ))
    assert status == 200
    assert "trade_quality_score" not in payload
    assert "entry_score" not in payload
    score = payload["technical_score"]
    assert 0 <= score["score"] <= 100
    assert score == analyzer.calculate_technical_score(
        *[payload[key] for key in ("price", "sma_20", "sma_50", "rsi", "rvol",
                                  "macd", "macd_signal", "support_zone", "resistance_zone")]
    )
    assert payload["trade_setup"] == analyzer.generate_trade_setup(
        *[payload[key] for key in ("price", "trend", "rsi", "rvol", "macd",
                                  "macd_signal", "macd_hist", "support_zone", "resistance_zone")]
    )
    assert all(component["details"] for component in score["components"].values())
