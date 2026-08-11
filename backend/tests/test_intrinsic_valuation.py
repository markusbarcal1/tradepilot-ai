import json
import math
import unittest

from app.services.valuation_analysis.assumptions import (
    annual_growth_rates, cagr, median_growth, resolve_assumptions, sign_aware_growth,
)
from app.services.valuation_analysis.intrinsic import (
    calculate_intrinsic_score, calculate_intrinsic_value, discounted_cash_flow, earnings_power,
    historical_multiple_reversion, owner_earnings,
    price_difference_metadata,
    score_price_to_fair_value,
)
from app.services.valuation_analysis.models import ValuationSnapshot


def rows(values, key="value"):
    return [{"period": f"202{index}-12-31", key: value} for index, value in enumerate(values)]


def intrinsic_snapshot(sector="Technology", **overrides):
    values = {
        "current_price": 100, "market_cap": 1_000, "free_cash_flow": 100,
        "forward_eps": 6, "expected_eps_growth": 0.10,
        "forward_revenue_growth": 0.08, "beta": 1.1, "total_debt": 200,
        "cash": 80, "diluted_shares": 10, "common_equity_per_share": 20,
        "tax_rate": 0.21, "cost_of_debt": 0.055,
    }
    values.update(overrides.pop("values", {}))
    history = {
        "revenue": rows([700, 760, 820, 900, 980]),
        "operating_income": rows([90, 96, 105, 112, 121]),
        "net_income": rows([55, 61, 68, 75, 82]),
        "eps": rows([4.8, 5.1, 5.5, 5.9, 6.3]),
        "free_cash_flow": rows([70, 78, 84, 92, 100]),
        "depreciation_amortization": rows([18, 19, 20, 21, 22]),
        "capital_expenditure": rows([-24, -25, -26, -28, -29]),
        "valuation_multiples": rows([18, 21, 24, 20, 22], "pe"),
    }
    history.update(overrides.pop("history", {}))
    return ValuationSnapshot("INTRINSIC", sector=sector, currency="USD",
                             financial_currency="USD", values=values, history=history, **overrides)


class GrowthTests(unittest.TestCase):
    def test_cagr_median_and_sign_aware_growth(self):
        self.assertAlmostEqual(cagr([100, 121]), 0.21)
        self.assertAlmostEqual(median_growth([100, 110, 121]), 0.10)
        self.assertIsNone(sign_aware_growth(-1, 2))
        self.assertIsNone(sign_aware_growth(0, 2))
        self.assertEqual([], annual_growth_rates([-1, 1, -2]))

    def test_growth_and_beta_are_capped_with_diagnostics(self):
        snapshot = intrinsic_snapshot(values={"expected_eps_growth": 4, "forward_revenue_growth": 3,
                                              "beta": 8})
        assumptions = resolve_assumptions(snapshot, "technology")
        self.assertLessEqual(assumptions["initial_growth_rate"], 0.30)
        self.assertEqual(2.0, assumptions["beta"])
        self.assertIn("beta_clamped_for_calculation", assumptions["fallbacks_used"])
        self.assertGreater(assumptions["discount_rate"], assumptions["terminal_growth_rate"])


class IntrinsicModelTests(unittest.TestCase):
    def test_dcf_is_finite_monotonic_and_bridges_debt_cash(self):
        # Match after-tax debt cost to cost of equity so changing debt isolates
        # the enterprise-to-equity bridge rather than also changing WACC.
        bridge_values = {"cost_of_debt": 0.095 / (1 - 0.21)}
        model = discounted_cash_flow(
            intrinsic_snapshot(values=bridge_values), "technology", 40
        )
        self.assertEqual("available", model["status"])
        self.assertLessEqual(model["fair_value_low"], model["fair_value_mid"])
        self.assertLessEqual(model["fair_value_mid"], model["fair_value_high"])
        self.assertEqual("simplified_ttm_fcf_dcf", model["calculation_method"])
        self.assertTrue(math.isfinite(model["fair_value_mid"]))
        more_debt = discounted_cash_flow(
            intrinsic_snapshot(values={**bridge_values, "total_debt": 500}),
            "technology", 40,
        )
        self.assertLess(more_debt["fair_value_mid"], model["fair_value_mid"])

    def test_dcf_missing_negative_fcf_and_zero_shares_are_controlled(self):
        for values in ({"free_cash_flow": None}, {"free_cash_flow": -1}, {"diluted_shares": 0}):
            history = {"free_cash_flow": []} if values.get("free_cash_flow") is None else {}
            with self.subTest(values=values):
                model = discounted_cash_flow(intrinsic_snapshot(values=values, history=history),
                                             "technology", 40)
                self.assertNotEqual("available", model["status"])

    def test_earnings_power_normalizes_outlier_and_rejects_losses(self):
        model = earnings_power(intrinsic_snapshot(history={"eps": rows([5, 5.2, 60, 5.4, 5.6])}),
                               "technology", 20)
        self.assertEqual(5.4, model["assumptions"]["normalized_eps"])
        self.assertEqual("unavailable", earnings_power(
            intrinsic_snapshot(history={"eps": rows([-2, -1, -3])}), "technology", 20
        )["status"])

    def test_historical_reversion_percentiles_and_financial_preference(self):
        model = historical_multiple_reversion(intrinsic_snapshot(), "technology", 25)
        self.assertEqual("available", model["status"])
        self.assertLessEqual(model["fair_value_low"], model["fair_value_mid"])
        financial = intrinsic_snapshot(
            sector="Financial Services",
            history={"valuation_multiples": rows([0.8, 1.0, 1.2, 1.1], "price_to_book")},
        )
        self.assertIn("price_to_book", historical_multiple_reversion(
            financial, "financials", 55
        )["calculation_method"])

    def test_owner_earnings_proxy_and_missing_inputs(self):
        model = owner_earnings(intrinsic_snapshot(), "technology", 15)
        self.assertEqual("available", model["status"])
        self.assertIn("maintenance_capex_proxy", model["fallbacks_used"])
        missing = owner_earnings(
            intrinsic_snapshot(history={"depreciation_amortization": []}), "technology", 15
        )
        self.assertEqual("unavailable", missing["status"])


class AggregationAndSectorTests(unittest.TestCase):
    def test_weighted_aggregation_coverage_comparison_and_json(self):
        result = calculate_intrinsic_value(intrinsic_snapshot(), "technology")
        self.assertEqual("available", result["status"])
        self.assertLessEqual(result["fair_value_low"], result["fair_value_mid"])
        self.assertLessEqual(result["fair_value_mid"], result["fair_value_high"])
        available = [model for model in result["models"] if model["status"] == "available"]
        expected = sum(model["fair_value_mid"] * model["weight"] for model in available) / sum(
            model["weight"] for model in available
        )
        self.assertAlmostEqual(expected, result["fair_value_mid"])
        self.assertIn(result["comparison_status"], {
            "below_estimated_fair_value", "near_estimated_fair_value", "above_estimated_fair_value"
        })
        json.dumps(result, allow_nan=False)

    def test_unsupported_models_do_not_reduce_financial_coverage(self):
        result = calculate_intrinsic_value(intrinsic_snapshot(
            sector="Financial Services",
            history={"valuation_multiples": rows([0.8, 1.0, 1.2, 1.1], "price_to_book")},
        ), "financials")
        self.assertEqual(2, result["coverage"]["supported_models"])
        self.assertEqual(2, result["coverage"]["unsupported_models"])
        self.assertEqual(1.0, result["coverage"]["weighted_coverage"])

    def test_missing_supported_model_reduces_coverage(self):
        snapshot = intrinsic_snapshot(history={"valuation_multiples": []})
        result = calculate_intrinsic_value(snapshot, "technology")
        self.assertEqual(1, result["coverage"]["missing_supported_models"])
        self.assertLess(result["coverage"]["weighted_coverage"], 1)

    def test_real_estate_only_uses_historical_reversion(self):
        result = calculate_intrinsic_value(intrinsic_snapshot(sector="Real Estate"), "real_estate")
        states = {model["model"]: model["status"] for model in result["models"]}
        self.assertEqual("available", states["historical_multiple_reversion"])
        self.assertEqual("unsupported_for_sector", states["discounted_cash_flow"])
        self.assertEqual("unsupported_for_sector", states["earnings_power"])
        self.assertEqual("unsupported_for_sector", states["owner_earnings"])


class IntrinsicScoreTests(unittest.TestCase):
    def test_price_curve_anchors_and_monotonic_decline(self):
        cases = ((0.50, 100), (0.60, 100), (0.75, 90), (0.85, 80),
                 (1.00, 60), (1.15, 40), (1.30, 20), (1.50, 0), (2.00, 0))
        scores = []
        for ratio, expected in cases:
            with self.subTest(ratio=ratio):
                score = score_price_to_fair_value(ratio)
                self.assertAlmostEqual(expected, score)
                scores.append(score)
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_confidence_coverage_and_disagreement_only_reduce_score(self):
        high = calculate_intrinsic_score(0.80, "high", 1.0, 0.10)["score"]
        moderate = calculate_intrinsic_score(0.80, "moderate", 1.0, 0.10)["score"]
        low = calculate_intrinsic_score(0.80, "low", 1.0, 0.10)["score"]
        self.assertGreater(high, moderate)
        self.assertGreater(moderate, low)

        full = calculate_intrinsic_score(0.80, "high", 1.0, 0.10)["score"]
        partial = calculate_intrinsic_score(0.80, "high", 0.75, 0.10)["score"]
        half = calculate_intrinsic_score(0.80, "high", 0.50, 0.10)["score"]
        self.assertGreater(full, partial)
        self.assertGreater(partial, half)

        low_disagreement = calculate_intrinsic_score(0.80, "high", 1.0, 0.10)["score"]
        moderate_disagreement = calculate_intrinsic_score(0.80, "high", 1.0, 0.20)["score"]
        high_disagreement = calculate_intrinsic_score(0.80, "high", 1.0, 0.40)["score"]
        self.assertGreater(low_disagreement, moderate_disagreement)
        self.assertGreater(moderate_disagreement, high_disagreement)

    def test_score_missing_and_bounds_are_controlled(self):
        self.assertIsNone(calculate_intrinsic_score(None, "high", 1.0, 0.1))
        self.assertIsNone(calculate_intrinsic_score(0.8, "high", None, 0.1))
        self.assertIsNone(calculate_intrinsic_score(0.8, "high", 1.0, None))
        for ratio in (0, 0.5, 1.0, 2.0, 100):
            result = calculate_intrinsic_score(ratio, "high", 1.0, 0.1)
            self.assertGreaterEqual(result["score"], 0)
            self.assertLessEqual(result["score"], 100)
            json.dumps(result, allow_nan=False)

    def test_aggregate_exposes_backend_score_without_changing_fair_value(self):
        result = calculate_intrinsic_value(intrinsic_snapshot(), "technology")
        self.assertIsInstance(result["score"], float)
        self.assertIn("raw_attractiveness_score", result)
        self.assertIn("score_adjustments", result)
        self.assertAlmostEqual(
            result["price_to_fair_value"], result["current_price"] / result["fair_value_mid"]
        )
        unavailable = calculate_intrinsic_value(
            intrinsic_snapshot(
                values={"free_cash_flow": None, "current_price": None},
                history={
                    "free_cash_flow": [], "eps": [], "valuation_multiples": [],
                    "net_income": [], "depreciation_amortization": [],
                    "capital_expenditure": [],
                },
            ), "technology"
        )
        self.assertIsNone(unavailable["score"])

    def test_discount_premium_and_equal_semantics(self):
        discount = price_difference_metadata(75, 100)
        self.assertEqual("discount", discount["price_difference_type"])
        self.assertEqual("Discount to Midpoint", discount["price_difference_label"])
        self.assertEqual(0.25, discount["price_difference_percentage"])
        premium = price_difference_metadata(125, 100)
        self.assertEqual("premium", premium["price_difference_type"])
        self.assertEqual("Premium to Midpoint", premium["price_difference_label"])
        self.assertEqual(0.25, premium["price_difference_percentage"])
        equal = price_difference_metadata(100, 100)
        self.assertEqual("difference", equal["price_difference_type"])
        self.assertEqual("Difference to Midpoint", equal["price_difference_label"])
        self.assertEqual(0, equal["price_difference_percentage"])


if __name__ == "__main__":
    unittest.main()
