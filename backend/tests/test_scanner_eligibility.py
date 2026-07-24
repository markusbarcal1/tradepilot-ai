import unittest
from unittest.mock import patch

import pandas as pd

from app.services.eligibility import (
    ScannerEligibilityConfig,
    evaluate_market_data_eligibility,
)
from app.services.scanner import scan_market


class ScannerEligibilityTests(unittest.TestCase):
    def test_default_eligibility_config_is_valid_and_extensible(self):
        config = ScannerEligibilityConfig.from_dict({})
        self.assertTrue(config.enabled)
        self.assertEqual(config.minimum_price, 5.0)
        self.assertEqual(config.minimum_average_volume, 500000)
        self.assertEqual(config.minimum_history_bars, 100)
        self.assertTrue(config.exclude_etfs)

        normalized = ScannerEligibilityConfig.from_dict({"minimum_price": -1, "minimum_average_volume": -10, "minimum_history_bars": 0})
        self.assertEqual(normalized.minimum_price, 5.0)
        self.assertEqual(normalized.minimum_average_volume, 500000)
        self.assertEqual(normalized.minimum_history_bars, 100)

    def test_market_data_eligibility_rejects_low_volume_and_short_history(self):
        history = pd.DataFrame(
            {
                "Open": [10.0] * 60,
                "High": [10.5] * 60,
                "Low": [9.5] * 60,
                "Close": [10.0] * 60,
                "Volume": [1000] * 60,
            }
        )

        config = ScannerEligibilityConfig.from_dict({"minimum_average_volume": 500000, "minimum_history_bars": 100})
        result = evaluate_market_data_eligibility("AAPL", history, config)

        self.assertFalse(result.eligible)
        self.assertEqual(result.reason_code, "below_minimum_average_volume")
        self.assertEqual(result.stage, "market_data")

    def test_scan_market_reports_eligibility_summary_when_enabled(self):
        def fake_get_scan_universe(universe):
            return "sp500", ["AAPL", "MSFT"]

        def fake_get_price_history(symbol, period, interval, audit_context=None):
            data = pd.DataFrame(
                {
                    "Open": [10.0, 11.0],
                    "High": [11.0, 12.0],
                    "Low": [9.0, 10.0],
                    "Close": [10.5, 11.5],
                    "Volume": [1000000, 1100000],
                }
            )
            return data

        def fake_analyze_ticker(symbol, period, interval, audit_context=None, eligibility_config=None, universe=None):
            return {
                "ticker": symbol,
                "price": 10.5,
                "trade_quality_score": {"score": 80, "grade": "Good Entry"},
                "technical_score": {"score": 85, "grade": "Bullish"},
                "trade_setup": {
                    "setup_type": "Momentum Continuation",
                    "setup_bias": "Bullish",
                    "quality": "Favorable",
                },
                "support_zone": {"display": "$10"},
                "resistance_zone": {"display": "$12"},
            }

        with patch("app.services.scanner.get_scan_universe", side_effect=fake_get_scan_universe), patch(
            "app.services.analyzer.get_price_history", side_effect=fake_get_price_history
        ), patch("app.services.scanner.analyze_ticker", side_effect=fake_analyze_ticker):
            response = scan_market("1y", "1d", 10, "sp500", max_symbols=2, audit=True, eligibility={"enabled": True})

        self.assertIn("audit", response)
        self.assertEqual(response["audit"]["eligibility"]["symbols_checked"], 2)
        self.assertEqual(response["audit"]["eligibility"]["symbols_eligible"], 2)
        self.assertEqual(response["audit"]["eligibility"]["symbols_excluded"], 0)


if __name__ == "__main__":
    unittest.main()
