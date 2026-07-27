import json
import math
import unittest

from app.services.financial_analysis.config import CATEGORY_WEIGHTS, METRIC_WEIGHTS
from app.services.financial_analysis.metrics import (
    calculate_effective_tax_rate,
    calculate_growth,
    calculate_gross_margin,
    calculate_metrics,
    calculate_roe,
    calculate_roic,
    safe_divide,
)
from app.services.financial_analysis.models import FinancialSnapshot
from app.services.financial_analysis.scoring import (
    score_financial_metrics,
    score_higher_is_better,
    score_lower_is_better,
)
from app.services.financial_analysis.service import analyze_financials


def metrics(**overrides):
    baseline = {
        "roic": 0.20,
        "return_on_capital": 0.25,
        "return_on_equity": 0.25,
        "gross_margin": 0.60,
        "operating_margin": 0.25,
        "net_margin": 0.20,
        "revenue_growth": 0.25,
        "eps_growth": 0.30,
        "free_cash_flow_growth": 0.25,
        "operating_income_growth": 0.25,
        "debt_to_equity": 0.3,
        "current_ratio": 2.0,
        "interest_coverage": 10.0,
        "net_debt_to_ebitda": 1.0,
        "free_cash_flow": 1_000_000,
        "operating_cash_flow_to_net_income": 1.2,
        "free_cash_flow_margin": 0.15,
        "positive_cash_flow_consistency": 1.0,
        "operating_cash_flow_margin": 0.25,
    }
    baseline.update(overrides)
    return baseline


class FinancialScoringTests(unittest.TestCase):
    def test_weights_sum_to_100_and_match_categories(self):
        self.assertEqual(100, sum(CATEGORY_WEIGHTS.values()))
        for category, weight in CATEGORY_WEIGHTS.items():
            self.assertEqual(weight, sum(METRIC_WEIGHTS[category].values()))

    def test_strong_company_scores_100_and_clamps(self):
        result = score_financial_metrics(metrics(
            roic=10, return_on_capital=10, revenue_growth=10, current_ratio=100,
        ))
        self.assertEqual("available", result["status"])
        self.assertEqual(100, result["score"])
        self.assertTrue(all(c["score"] <= c["max_score"] for c in result["categories"].values()))

    def test_weak_highly_leveraged_company(self):
        result = score_financial_metrics(metrics(
            roic=-0.2, return_on_capital=-0.2, return_on_equity=-0.2,
            gross_margin=-0.2, operating_margin=-0.2, net_margin=-0.2,
            revenue_growth=-0.5, eps_growth=-1, free_cash_flow_growth=-1,
            operating_income_growth=-1,
            debt_to_equity=8, current_ratio=0.2, interest_coverage=-2,
            net_debt_to_ebitda=12, free_cash_flow=-1,
            operating_cash_flow_to_net_income=0, free_cash_flow_margin=-0.5,
            positive_cash_flow_consistency=0,
            operating_cash_flow_margin=-0.5,
        ))
        self.assertEqual(0, result["score"])

    def test_missing_metrics_are_normalized_and_marked_partial(self):
        partial = {key: None for key in metrics()}
        partial.update({
            "roic": 0.08, "return_on_capital": 0.08,
            "return_on_equity": 0.08, "gross_margin": 0.20,
            "operating_margin": 0.08, "net_margin": 0.05,
            "revenue_growth": 0.0, "eps_growth": 0.0,
            "free_cash_flow_growth": 0.0, "operating_income_growth": 0.0,
        })
        result = score_financial_metrics(partial)
        self.assertEqual("partial", result["status"])
        self.assertEqual(55, result["coverage"]["percentage"])
        self.assertEqual(40, result["score"])
        self.assertEqual(10, result["available_metrics"])
        self.assertEqual(19, result["expected_metrics"])
        profitability = result["categories"]["profitability"]
        self.assertTrue(profitability["normalization_note"] is None)
        self.assertTrue(all("score" in item and "max_score" in item
                            for item in profitability["details"]))

    def test_missing_metric_is_explicitly_unavailable_not_zero(self):
        values = metrics(interest_coverage=None)
        result = score_financial_metrics(values)
        detail = next(
            item for item in result["categories"]["financial_health"]["details"]
            if item["key"] == "interest_coverage"
        )
        self.assertEqual("unavailable", detail["availability"])
        self.assertIsNone(detail["score"])
        self.assertEqual("N/A", detail["formatted_value"])
        self.assertIn("Excluded", detail["reference"])

    def test_insufficient_data_is_unavailable(self):
        result = score_financial_metrics({"operating_margin": 0.2})
        self.assertEqual("unavailable", result["status"])
        self.assertIsNone(result["score"])
        self.assertEqual(set(CATEGORY_WEIGHTS), set(result["categories"]))
        self.assertIsNone(result["categories"]["growth"]["score"])

    def test_null_nan_and_division_by_zero(self):
        self.assertIsNone(safe_divide(1, 0))
        self.assertIsNone(safe_divide(math.nan, 2))
        result = score_financial_metrics({"operating_margin": math.nan})
        self.assertEqual("unavailable", result["status"])
        json.dumps(result, allow_nan=False)

    def test_category_normalization_precedes_overall_normalization(self):
        sparse = {key: None for key in metrics()}
        sparse.update({
            "roic": 0.20,
            "return_on_capital": 0.25,
            "return_on_equity": 0.25,
            "gross_margin": 0.60,
            "operating_margin": 0.25,
            "net_margin": 0.20,
            "revenue_growth": -0.10,
            "debt_to_equity": 3.0,
            "free_cash_flow": -1,
        })
        result = score_financial_metrics(sparse)
        self.assertEqual("partial", result["status"])
        self.assertEqual(30.0, result["score"])
        self.assertEqual(1, result["categories"]["growth"]["available_metrics"])
        self.assertEqual(0.25, result["categories"]["growth"]["coverage"])

    def test_piecewise_anchor_interpolation_and_monotonicity(self):
        anchors = (0.0, 0.08, 0.12, 0.20)
        values = [-1, 0, 0.04, 0.08, 0.10, 0.12, 0.16, 0.20, 10]
        scores = [score_higher_is_better(value, *anchors, 8) for value in values]
        self.assertEqual(0, scores[0])
        self.assertEqual(3.2, scores[3])
        self.assertEqual(5.6, scores[5])
        self.assertEqual(8, scores[-1])
        self.assertEqual(scores, sorted(scores))

    def test_lower_is_better_is_monotonic_and_bounded(self):
        values = [-10, 0.3, 1, 2, 3, 10]
        scores = [score_lower_is_better(value, 0.3, 1, 2, 3, 9) for value in values]
        self.assertEqual(9, scores[0])
        self.assertEqual(0, scores[-1])
        self.assertEqual(scores, sorted(scores, reverse=True))


class FinancialMetricsTests(unittest.TestCase):
    def test_roic_uses_average_invested_capital(self):
        raw = {
            "operating_income": 30, "tax_provision": 5, "pretax_income": 25,
            "total_debt": 50, "stockholders_equity": 100, "cash_and_equivalents": 20,
            "prior_total_debt": 40, "prior_stockholders_equity": 90,
            "prior_cash_and_equivalents": 10,
        }
        self.assertAlmostEqual(24 / 125, calculate_roic(raw))

    def test_roic_current_capital_fallback_and_tax_fallbacks(self):
        raw = {
            "operating_income": 20, "total_debt": 40,
            "stockholders_equity": 80, "cash_and_equivalents": 20,
        }
        self.assertAlmostEqual(15.8 / 100, calculate_roic(raw))
        self.assertEqual(0.21, calculate_effective_tax_rate(None, None))
        self.assertEqual(0.21, calculate_effective_tax_rate(90, 100))

    def test_roic_rejects_nonpositive_capital(self):
        self.assertIsNone(calculate_roic({
            "operating_income": 10, "total_debt": 10,
            "stockholders_equity": 10, "cash_and_equivalents": 20,
        }))

    def test_roe_average_equity_and_negative_equity(self):
        self.assertAlmostEqual(0.2, calculate_roe({
            "net_income": 18, "stockholders_equity": 100, "prior_stockholders_equity": 80,
        }))
        self.assertIsNone(calculate_roe({"net_income": 18, "stockholders_equity": -10}))

    def test_gross_margin_direct_and_cost_fallback(self):
        self.assertEqual(0.4, calculate_gross_margin({"total_revenue": 100, "gross_profit": 40}))
        self.assertEqual(0.4, calculate_gross_margin({"total_revenue": 100, "cost_of_revenue": 60}))

    def test_sign_aware_growth_transitions_and_near_zero(self):
        self.assertEqual(0.25, calculate_growth(125, 100))
        self.assertEqual(1.0, calculate_growth(10, -5))
        self.assertEqual(-1.0, calculate_growth(-5, 10))
        self.assertEqual(0.5, calculate_growth(-5, -10))
        self.assertIsNone(calculate_growth(10, 0))

    def test_operating_cash_flow_margin_and_zero_revenue(self):
        snapshot = FinancialSnapshot("OCF", values={"operating_cash_flow": 20, "total_revenue": 100})
        self.assertEqual(0.2, calculate_metrics(snapshot)["operating_cash_flow_margin"])
        snapshot.values["total_revenue"] = 0
        self.assertIsNone(calculate_metrics(snapshot)["operating_cash_flow_margin"])

    def test_financial_sector_omits_misleading_leverage_metrics(self):
        snapshot = FinancialSnapshot(
            "BANK",
            sector="Financial Services",
            values={"debt_to_equity": 500, "current_ratio": 1.5, "total_debt": 10, "ebitda": 2},
        )
        result = calculate_metrics(snapshot)
        self.assertTrue(all(result[key] is None for key in (
            "debt_to_equity", "current_ratio", "interest_coverage", "net_debt_to_ebitda",
        )))


class FinancialServiceTests(unittest.TestCase):
    def test_unsupported_etf(self):
        def provider(symbol):
            return FinancialSnapshot(symbol, instrument_type="ETF")

        result = analyze_financials("UNITTEST-ETF", provider=provider)
        self.assertEqual("unsupported_instrument_type", result["reason_code"])
        self.assertIsNone(result["score"])

    def test_provider_failure_returns_safe_unavailable_response(self):
        def provider(_symbol):
            raise TimeoutError("provider secret details")

        result = analyze_financials("UNITTEST-FAIL", provider=provider)
        self.assertEqual("provider_error", result["reason_code"])
        self.assertNotIn("secret", result["message"])


if __name__ == "__main__":
    unittest.main()
