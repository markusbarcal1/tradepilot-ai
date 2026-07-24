import unittest
from unittest.mock import patch

from app.services.scanner import _resolve_worker_count, scan_market


class ScannerAuditTests(unittest.TestCase):
    def test_scan_market_returns_audit_summary_when_enabled(self):
        def fake_get_scan_universe(universe):
            return "sp500", ["AAPL", "MSFT"]

        def fake_analyze_tickers(symbols, period, interval):
            return {
                "errors": [],
                "results": [
                    {
                        "ticker": "MSFT",
                        "price": 100,
                        "trade_quality_score": {"score": 80, "grade": "Good Entry"},
                        "technical_score": {"score": 85, "grade": "Bullish"},
                        "trade_setup": {
                            "setup_type": "Momentum Continuation",
                            "setup_bias": "Bullish",
                            "quality": "Favorable",
                        },
                        "support_zone": {"display": "$95"},
                        "resistance_zone": {"display": "$105"},
                    },
                    {
                        "ticker": "AAPL",
                        "price": 100,
                        "trade_quality_score": {"score": 75, "grade": "Good Entry"},
                        "technical_score": {"score": 78, "grade": "Bullish"},
                        "trade_setup": {
                            "setup_type": "Momentum Continuation",
                            "setup_bias": "Bullish",
                            "quality": "Favorable",
                        },
                        "support_zone": {"display": "$95"},
                        "resistance_zone": {"display": "$105"},
                    },
                ],
            }

        with patch("app.services.scanner.get_scan_universe", side_effect=fake_get_scan_universe), patch(
            "app.services.scanner.analyze_tickers", side_effect=fake_analyze_tickers
        ):
            response = scan_market("1y", "1d", 10, "sp500", max_symbols=2, audit=True, max_workers=1)

        self.assertIn("audit", response)
        self.assertEqual(response["audit"]["symbols_requested"], 2)
        self.assertEqual(response["audit"]["symbols_completed"], 2)
        self.assertEqual(response["audit"]["symbols_failed"], 0)
        self.assertEqual(response["audit"]["symbols_skipped"], 0)
        self.assertEqual(response["audit"]["execution_model"], "sequential")
        self.assertEqual(response["audit"]["worker_count"], 1)

    def test_resolve_worker_count_uses_safe_defaults(self):
        self.assertEqual(_resolve_worker_count(None), 8)
        self.assertEqual(_resolve_worker_count(0), 1)
        self.assertEqual(_resolve_worker_count("invalid"), 8)
        self.assertEqual(_resolve_worker_count(99), 16)

    def test_scan_market_with_concurrency_isolates_symbol_failures(self):
        def fake_get_scan_universe(universe):
            return "sp500", ["AAPL", "MSFT", "TSLA"]

        def fake_analyze_ticker(symbol, period, interval, audit_context=None):
            if symbol == "MSFT":
                raise ValueError("market data unavailable")

            return {
                "ticker": symbol,
                "price": 100,
                "trade_quality_score": {"score": 80, "grade": "Good Entry"},
                "technical_score": {"score": 85, "grade": "Bullish"},
                "trade_setup": {
                    "setup_type": "Momentum Continuation",
                    "setup_bias": "Bullish",
                    "quality": "Favorable",
                },
                "support_zone": {"display": "$95"},
                "resistance_zone": {"display": "$105"},
            }

        with patch("app.services.scanner.get_scan_universe", side_effect=fake_get_scan_universe), patch(
            "app.services.scanner.analyze_ticker", side_effect=fake_analyze_ticker
        ):
            response = scan_market("1y", "1d", 10, "sp500", max_symbols=3, audit=True, max_workers=4)

        self.assertEqual(response["audit"]["execution_model"], "thread_pool")
        self.assertEqual(response["audit"]["worker_count"], 4)
        self.assertEqual(response["audit"]["symbols_completed"], 2)
        self.assertEqual(response["audit"]["symbols_failed"], 1)
        self.assertEqual(response["audit"]["symbols_skipped"], 0)
        self.assertEqual([item["ticker"] for item in response["results"]], ["AAPL", "TSLA"])


if __name__ == "__main__":
    unittest.main()
