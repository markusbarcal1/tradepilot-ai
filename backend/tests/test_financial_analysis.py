import math
import unittest

from app.services.financial_analysis.config import CATEGORY_WEIGHTS, METRIC_WEIGHTS
from app.services.financial_analysis.metrics import calculate_metrics, safe_divide
from app.services.financial_analysis.models import FinancialSnapshot
from app.services.financial_analysis.scoring import score_financial_metrics
from app.services.financial_analysis.service import analyze_financials


def metrics(**overrides):
    baseline = {
        "return_on_capital": 0.20,
        "operating_margin": 0.25,
        "net_margin": 0.20,
        "revenue_growth": 0.20,
        "eps_growth": 0.25,
        "free_cash_flow_growth": 0.25,
        "debt_to_equity": 0.3,
        "current_ratio": 2.0,
        "interest_coverage": 10.0,
        "net_debt_to_ebitda": 1.0,
        "free_cash_flow": 1_000_000,
        "operating_cash_flow_to_net_income": 1.2,
        "free_cash_flow_margin": 0.15,
        "positive_cash_flow_consistency": 1.0,
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
            return_on_capital=10, revenue_growth=10, current_ratio=100,
        ))
        self.assertEqual("available", result["status"])
        self.assertEqual(100, result["score"])
        self.assertTrue(all(c["score"] <= c["max_score"] for c in result["categories"].values()))

    def test_weak_highly_leveraged_company(self):
        result = score_financial_metrics(metrics(
            return_on_capital=-0.2, operating_margin=-0.2, net_margin=-0.2,
            revenue_growth=-0.5, eps_growth=-1, free_cash_flow_growth=-1,
            debt_to_equity=8, current_ratio=0.2, interest_coverage=-2,
            net_debt_to_ebitda=12, free_cash_flow=-1,
            operating_cash_flow_to_net_income=0, free_cash_flow_margin=-0.5,
            positive_cash_flow_consistency=0,
        ))
        self.assertEqual(0, result["score"])

    def test_missing_metrics_are_normalized_and_marked_partial(self):
        partial = {key: None for key in metrics()}
        partial.update({
            "return_on_capital": 0.1,
            "operating_margin": 0.125,
            "net_margin": 0.1,
            "revenue_growth": 0.05,
            "eps_growth": 0.025,
            "free_cash_flow_growth": 0.025,
        })
        result = score_financial_metrics(partial)
        self.assertEqual("partial", result["status"])
        self.assertEqual(55, result["coverage"]["percentage"])
        self.assertEqual(50, result["score"])
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
        self.assertEqual("Data unavailable", detail["formatted_value"])
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


class FinancialMetricsTests(unittest.TestCase):
    def test_negative_earnings_do_not_fabricate_cash_conversion(self):
        snapshot = FinancialSnapshot(
            "LOSS",
            values={
                "return_on_equity": -0.5, "return_on_assets": -0.1,
                "operating_cash_flow": 5, "net_income": -10,
            },
        )
        result = calculate_metrics(snapshot)
        self.assertEqual(-0.1, result["return_on_capital"])
        self.assertIsNone(result["operating_cash_flow_to_net_income"])

    def test_negative_equity_falls_back_to_roa(self):
        snapshot = FinancialSnapshot(
            "NEG",
            values={"return_on_equity": -2, "return_on_assets": 0.04},
        )
        self.assertEqual(0.04, calculate_metrics(snapshot)["return_on_capital"])

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
