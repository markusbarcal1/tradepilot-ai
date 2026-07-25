import math
import unittest

from app.services.analyzer import (
    TECHNICAL_FAMILY_WEIGHTS,
    TECHNICAL_SCORE_VERSION,
    calculate_technical_score,
    score_momentum_family,
    score_participation_family,
    score_price_structure_family,
    score_trend_family,
)
from app.services.scanner import _build_scan_results


def zone(mid, distance, strength="Strong"):
    return {
        "mid": mid,
        "distance_pct": distance,
        "strength": strength,
        "touch_count": 4,
    }


class TrendFamilyTests(unittest.TestCase):
    def test_alignment_cases_and_cap(self):
        cases = [
            ((110, 105, 100), 40, "supportive"),
            ((90, 95, 100), 0, "weak"),
            ((105, 100, 110), 14, "mixed"),
        ]
        for values, expected, status in cases:
            with self.subTest(values=values):
                result = score_trend_family(*values)
                self.assertEqual(expected, result["score"])
                self.assertEqual(status, result["status"])
                self.assertLessEqual(result["score"], result["max_score"])

    def test_missing_and_invalid_inputs_are_visible(self):
        for value in (None, math.nan):
            result = score_trend_family(value, 100, 95)
            self.assertEqual(0, result["score"])
            self.assertEqual("unavailable", result["status"])
            self.assertFalse(result["inputs"]["data_available"])


class MomentumFamilyTests(unittest.TestCase):
    def test_supportive_extended_and_oversold_cases(self):
        supportive = score_momentum_family(60, 2, 1)
        extended = score_momentum_family(75, 2, 1)
        oversold = score_momentum_family(25, 1, 2)
        self.assertEqual(30, supportive["score"])
        self.assertEqual("supportive", supportive["status"])
        self.assertEqual(24, extended["score"])
        self.assertEqual("mixed", extended["status"])
        self.assertTrue(extended["negative_reasons"])
        self.assertEqual(7, oversold["score"])
        self.assertEqual("weak", oversold["status"])

    def test_boundaries_and_invalid_inputs(self):
        self.assertEqual("supportive", score_momentum_family(70, 2, 1)["inputs"]["rsi_bucket"])
        for value in (None, math.nan, 101):
            self.assertEqual("unavailable", score_momentum_family(value, 2, 1)["status"])


class ParticipationFamilyTests(unittest.TestCase):
    def test_threshold_boundaries(self):
        for rvol, expected in ((0.7, 5), (1.0, 10), (2.0, 15)):
            with self.subTest(rvol=rvol):
                result = score_participation_family(rvol)
                self.assertEqual(expected, result["score"])
                self.assertLessEqual(result["score"], 15)

    def test_invalid_values(self):
        for value in (None, math.nan, -1):
            self.assertEqual("unavailable", score_participation_family(value)["status"])


class PriceStructureFamilyTests(unittest.TestCase):
    def test_near_support_with_room_to_resistance(self):
        result = score_price_structure_family(100, zone(98, 2), zone(110, 10))
        self.assertEqual(15, result["score"])
        self.assertEqual("supportive", result["status"])

    def test_close_to_strong_resistance_is_penalized(self):
        result = score_price_structure_family(100, zone(97, 3), zone(101, 1, "Strong"))
        self.assertEqual(8, result["score"])
        self.assertEqual("mixed", result["status"])
        self.assertTrue(any("resistance" in reason.lower() for reason in result["negative_reasons"]))

    def test_missing_zone_cases_are_explicit(self):
        support_only = score_price_structure_family(100, zone(98, 2), None)
        resistance_only = score_price_structure_family(100, None, zone(110, 10))
        neither = score_price_structure_family(100, None, None)
        self.assertFalse(support_only["inputs"]["resistance_available"])
        self.assertFalse(resistance_only["inputs"]["support_available"])
        self.assertEqual(0, neither["score"])
        self.assertEqual("unavailable", neither["status"])

    def test_invalid_price_and_zone_values(self):
        for price in (None, math.nan, 0):
            result = score_price_structure_family(price, zone(98, 2), zone(110, 10))
            self.assertEqual("unavailable", result["status"])


class TechnicalScoreContractTests(unittest.TestCase):
    def test_components_include_expandable_detail_contract(self):
        result = calculate_technical_score(
            110, 105, 100, 60, 1.5, 2, 1,
            zone(100, 3), zone(125, 12),
        )
        for component in result["components"].values():
            self.assertTrue(component["details"])
            for detail in component["details"]:
                self.assertIn("label", detail)
                self.assertIn("score", detail)
                self.assertIn("max_score", detail)
                self.assertIn("explanation", detail)
                self.assertIn("availability", detail)

    def test_legacy_contract_components_and_invariants(self):
        result = calculate_technical_score(
            110, 105, 100, 60, 2, 2, 1,
            zone(107, 2.7), zone(121, 10),
        )
        self.assertIsInstance(result["score"], (int, float))
        self.assertIsInstance(result["grade"], str)
        self.assertIsInstance(result["positives"], list)
        self.assertIsInstance(result["negatives"], list)
        self.assertEqual(TECHNICAL_SCORE_VERSION, result["version"])
        self.assertEqual(set(TECHNICAL_FAMILY_WEIGHTS), set(result["components"]))
        self.assertEqual(result["score"], sum(c["score"] for c in result["components"].values()))
        self.assertEqual(100, sum(c["max_score"] for c in result["components"].values()))
        self.assertTrue(0 <= result["score"] <= 100)
        for component in result["components"].values():
            self.assertTrue(0 <= component["score"] <= component["max_score"])
            self.assertEqual(
                {"score", "max_score", "status", "positive_reasons", "negative_reasons", "inputs", "details"},
                set(component),
            )

    def test_grade_boundaries(self):
        from app.services.analyzer import _technical_grade

        cases = ((80, "Strong Bullish"), (60, "Bullish"), (40, "Neutral"),
                 (20, "Bearish"), (19, "Strong Bearish"))
        for score, grade in cases:
            self.assertEqual(grade, _technical_grade(score))

    def test_scanner_reads_legacy_fields_and_preserves_sort_order(self):
        def analysis(ticker, quality_score, technical_score):
            return {
                "ticker": ticker,
                "price": 100,
                "trade_quality_score": {"score": quality_score, "grade": "Good Entry"},
                "technical_score": {
                    **technical_score,
                    "score": technical_score["score"],
                },
                "trade_setup": {
                    "setup_type": "Momentum Continuation",
                    "setup_bias": "Bullish",
                    "quality": "Favorable",
                },
                "support_zone": {"display": "$95"},
                "resistance_zone": {"display": "$110"},
            }

        lower = calculate_technical_score(105, 100, 110, 45, 1, 1, 2)
        higher = calculate_technical_score(110, 105, 100, 60, 2, 2, 1)
        results = _build_scan_results([
            analysis("LOW", 50, lower),
            analysis("HIGH", 50, higher),
            analysis("TOP", 60, lower),
        ])
        self.assertEqual(["TOP", "HIGH", "LOW"], [item["ticker"] for item in results])
        self.assertEqual(higher["score"], results[1]["technical_score"])
        self.assertEqual(results[0]["technical_score"], results[0]["trend_score"])
        self.assertEqual(results[0]["trade_quality_score"], results[0]["entry_score"])
        self.assertEqual("$95", results[0]["support"])


if __name__ == "__main__":
    unittest.main()
