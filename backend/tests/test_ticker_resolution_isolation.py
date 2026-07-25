import unittest
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

from app.main import validate_ticker
from app.services.market_data import MarketDataRateLimitError
from app.services.scanner import SP500_UNIVERSE, get_scan_universe, scan_market


def successful_analysis(symbol):
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


class TickerResolutionIsolationTests(unittest.TestCase):
    def test_aapl_and_watchlist_symbol_resolve_before_and_after_scan(self):
        history = pd.DataFrame({"Close": [100.0]})

        with patch("app.main.get_price_history", return_value=history):
            self.assertTrue(validate_ticker("AAPL")["valid"])
            self.assertTrue(validate_ticker("MSFT")["valid"])

            with patch(
                "app.services.scanner.get_scan_universe",
                return_value=("nasdaq", ["LOWVOL", "AAPL"]),
            ), patch(
                "app.services.scanner.analyze_ticker",
                side_effect=lambda symbol, *args, **kwargs: (
                    {
                        "ticker": symbol,
                        "price": 2,
                        "eligibility": {
                            "eligible": False,
                            "reason_code": "below_minimum_price",
                        },
                    }
                    if symbol == "LOWVOL"
                    else successful_analysis(symbol)
                ),
            ):
                response = scan_market(
                    universe="nasdaq",
                    max_symbols=2,
                    max_workers=2,
                    eligibility={"enabled": True},
                )

            self.assertEqual(response["summary"]["skipped_by_eligibility"], 1)
            self.assertEqual(response["summary"]["genuinely_invalid_symbols"], 0)
            self.assertTrue(validate_ticker("AAPL")["valid"])
            self.assertTrue(validate_ticker("MSFT")["valid"])

    def test_temporary_provider_failure_is_not_invalid_ticker(self):
        with patch(
            "app.main.get_price_history",
            side_effect=MarketDataRateLimitError("AAPL", "rate limited"),
        ):
            with self.assertRaises(HTTPException) as raised:
                validate_ticker("AAPL")

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail["code"], "rate_limit")
        self.assertNotEqual(raised.exception.status_code, 404)

    def test_malformed_symbol_is_the_only_locally_permanent_invalid_case(self):
        with self.assertRaises(HTTPException) as raised:
            validate_ticker("not a ticker!")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail["code"], "invalid_ticker")
        self.assertFalse(raised.exception.detail["retryable"])

    def test_failed_scan_cannot_mutate_or_replace_canonical_universe(self):
        canonical_before = tuple(SP500_UNIVERSE)
        _, working_symbols = get_scan_universe("sp500")
        working_symbols.clear()

        self.assertEqual(tuple(SP500_UNIVERSE), canonical_before)
        self.assertIn("AAPL", get_scan_universe("sp500")[1])

        with patch(
            "app.services.scanner.get_scan_universe",
            return_value=("sp500", ["AAPL", "MSFT"]),
        ), patch(
            "app.services.scanner.analyze_ticker",
            side_effect=MarketDataRateLimitError("AAPL", "rate limited"),
        ):
            response = scan_market(
                universe="sp500",
                max_symbols=2,
                max_workers=2,
                eligibility={"enabled": True},
            )

        self.assertEqual(response["summary"]["genuinely_invalid_symbols"], 0)
        self.assertEqual(response["summary"]["temporary_data_failures"], 2)
        self.assertIn("AAPL", get_scan_universe("sp500")[1])

    def test_repeated_provider_failures_open_scanner_only_circuit(self):
        symbols = [f"TEST{i}" for i in range(20)]

        with patch(
            "app.services.scanner.get_scan_universe",
            return_value=("nasdaq", symbols),
        ), patch(
            "app.services.scanner.analyze_ticker",
            side_effect=lambda symbol, *args, **kwargs: (
                (_ for _ in ()).throw(
                    MarketDataRateLimitError(symbol, "rate limited")
                )
            ),
        ):
            response = scan_market(
                universe="nasdaq",
                max_symbols=len(symbols),
                max_workers=2,
            )

        self.assertEqual(response["summary"]["genuinely_invalid_symbols"], 0)
        self.assertEqual(response["summary"]["temporary_data_failures"], len(symbols))
        self.assertTrue(any(
            error["category"] == "provider_circuit_open"
            for error in response["errors"]
        ))


if __name__ == "__main__":
    unittest.main()
