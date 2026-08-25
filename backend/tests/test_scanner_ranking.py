import unittest

from app.services.scanner import _build_scan_results, normalize_scoring_priorities


def analysis(ticker, technical, quality, financial, valuation):
    return {
        "ticker": ticker,
        "price": 100,
        "technical_score": {"score": technical, "grade": "Test"},
        "trade_quality_score": {"score": quality, "grade": "Test"},
        "financial_score": {"score": financial, "status": "available"},
        "valuation_score": {"score": valuation, "status": "available"},
        "trade_setup": {
            "setup_type": "Momentum Continuation",
            "setup_bias": "Bullish",
            "quality": "Favorable",
        },
    }


class ScannerRankingTests(unittest.TestCase):
    def setUp(self):
        self.analyses = [
            analysis("AAAA", 91, 86, 94, 58),
            analysis("BBBB", 70, 95, 80, 99),
        ]

    def assert_ranking(self, priorities, expected_ticker, expected_score):
        results = _build_scan_results(self.analyses, scoring_priorities=priorities)
        self.assertEqual(results[0]["ticker"], expected_ticker)
        self.assertEqual(results[0]["scanner_score"], expected_score)
        for field in (
            "technical_score", "trade_quality_score", "financial_score",
            "valuation_score", "scanner_score",
        ):
            self.assertIn(field, results[0])

    def test_required_scoring_combinations(self):
        cases = [
            (["technical"], "AAAA", 91.0),
            (["trade_quality"], "BBBB", 95.0),
            (["financial"], "AAAA", 94.0),
            (["valuation"], "BBBB", 99.0),
            (["technical", "trade_quality"], "AAAA", 88.5),
            (["financial", "valuation"], "BBBB", 89.5),
            (["technical", "trade_quality", "financial", "valuation"], "BBBB", 86.0),
        ]
        for priorities, ticker, score in cases:
            with self.subTest(priorities=priorities):
                self.assert_ranking(priorities, ticker, score)

    def test_missing_selected_score_is_explicit_and_not_zero(self):
        unavailable = analysis("MISS", 90, 90, None, 90)
        results = _build_scan_results([unavailable], scoring_priorities=["financial"])
        self.assertIsNone(results[0]["financial_score"])
        self.assertIsNone(results[0]["scanner_score"])
        self.assertEqual(results[0]["scanner_score_available_components"], 0)

    def test_scoring_priorities_require_valid_nonempty_identifiers(self):
        self.assertEqual(
            normalize_scoring_priorities(None),
            ("technical", "trade_quality"),
        )
        with self.assertRaises(ValueError):
            normalize_scoring_priorities([])
        with self.assertRaises(ValueError):
            normalize_scoring_priorities(["technical", "bogus"])


if __name__ == "__main__":
    unittest.main()
