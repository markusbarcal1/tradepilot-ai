import json
import math
import unittest

from app.services.financial_analysis.profiles import SectorProfile
from app.services.valuation_analysis.metrics import (
    calculate_valuation_metrics,
    currency_consistency,
)
from app.services.valuation_analysis.models import ValuationSnapshot
from app.services.valuation_analysis.profiles import (
    normalize_sector,
    resolve_valuation_profile,
    validate_all_valuation_profiles,
)
from app.services.valuation_analysis.scoring import (
    score_higher_is_better,
    score_lower_is_better,
    score_valuation_metrics,
    valuation_classification,
)
from app.services.valuation_analysis.service import analyze_valuation


def snapshot(**overrides):
    values = {
        "current_price": 100, "market_cap": 1_000, "enterprise_value": 1_200,
        "trailing_eps": 5, "forward_eps": 6.25, "expected_eps_growth": 0.10,
        "revenue": 500, "net_income": 50, "ebitda": 100,
        "common_equity": 400, "operating_cash_flow": 100,
        "capital_expenditure": -40, "free_cash_flow": 60,
        "provider_trailing_pe": 21, "provider_forward_pe": 17,
        "provider_peg_ratio": 1.8, "provider_ev_to_ebitda": 13,
        "provider_price_to_sales": 2.1, "provider_price_to_book": 2.6,
    }
    values.update(overrides.pop("values", {}))
    return ValuationSnapshot(
        overrides.pop("symbol", "TEST"), sector=overrides.pop("sector", "Technology"),
        currency=overrides.pop("currency", "USD"),
        financial_currency=overrides.pop("financial_currency", "USD"),
        values=values, **overrides,
    )


def available_metrics(**overrides):
    raw = calculate_valuation_metrics(snapshot())
    raw.update(overrides)
    return raw


class ValuationMetricTests(unittest.TestCase):
    def test_calculated_values_are_preferred_and_sources_are_exposed(self):
        result = calculate_valuation_metrics(snapshot())
        self.assertEqual(20, result["trailing_pe"]["value"])
        self.assertEqual(16, result["forward_pe"]["value"])
        self.assertEqual(1.6, result["peg_ratio"]["value"])
        self.assertEqual(12, result["ev_to_ebitda"]["value"])
        self.assertEqual(2, result["price_to_sales"]["value"])
        self.assertEqual(2.5, result["price_to_book"]["value"])
        self.assertEqual(0.06, result["free_cash_flow_yield"]["value"])
        self.assertEqual(0.05, result["earnings_yield"]["value"])
        self.assertTrue(all(
            metric["source"] == "calculated" for metric in result.values()
        ))
        self.assertTrue(result["trailing_pe"]["discrepancy_percentage"] > 0)

    def test_pe_negative_zero_and_missing_eps_states(self):
        for eps in (-2, 0):
            with self.subTest(eps=eps):
                result = calculate_valuation_metrics(snapshot(values={"trailing_eps": eps}))
                self.assertEqual("not_meaningful", result["trailing_pe"]["support_state"])
                self.assertLessEqual(result["trailing_pe"]["raw_value"], 0)
        result = calculate_valuation_metrics(snapshot(values={
            "trailing_eps": None, "provider_trailing_pe": None,
        }))
        self.assertEqual("unavailable", result["trailing_pe"]["support_state"])

    def test_forward_pe_missing_estimate_and_provider_fallback(self):
        missing = calculate_valuation_metrics(snapshot(values={
            "forward_eps": None, "provider_forward_pe": None,
        }))
        self.assertEqual("unavailable", missing["forward_pe"]["support_state"])
        fallback = calculate_valuation_metrics(snapshot(values={"forward_eps": None}))
        self.assertEqual(17, fallback["forward_pe"]["value"])
        self.assertEqual("provider", fallback["forward_pe"]["source"])

    def test_peg_percentage_points_decimal_and_invalid_growth(self):
        decimal = calculate_valuation_metrics(snapshot(values={
            "forward_eps": 5, "expected_eps_growth": 0.10,
        }))
        self.assertEqual(2, decimal["peg_ratio"]["value"])
        percentage = calculate_valuation_metrics(snapshot(values={
            "forward_eps": 5, "expected_eps_growth": 10,
        }))
        self.assertEqual(2, percentage["peg_ratio"]["value"])
        for growth in (0, -0.1):
            with self.subTest(growth=growth):
                result = calculate_valuation_metrics(snapshot(values={
                    "expected_eps_growth": growth,
                }))
                self.assertEqual("not_meaningful", result["peg_ratio"]["support_state"])

    def test_ev_ebitda_rejects_negative_inputs(self):
        negative_ebitda = calculate_valuation_metrics(snapshot(values={"ebitda": -10}))
        self.assertEqual("not_meaningful", negative_ebitda["ev_to_ebitda"]["support_state"])
        negative_ev = calculate_valuation_metrics(snapshot(values={"enterprise_value": -100}))
        self.assertEqual("not_meaningful", negative_ev["ev_to_ebitda"]["support_state"])

    def test_sales_and_book_require_positive_denominators(self):
        sales = calculate_valuation_metrics(snapshot(values={"revenue": 0}))
        self.assertEqual("not_meaningful", sales["price_to_sales"]["support_state"])
        book = calculate_valuation_metrics(snapshot(values={"common_equity": -5}))
        self.assertEqual("not_meaningful", book["price_to_book"]["support_state"])

    def test_fcf_capex_signs_and_negative_yields(self):
        negative_capex = calculate_valuation_metrics(snapshot(values={
            "free_cash_flow": None, "operating_cash_flow": 100,
            "capital_expenditure": -40,
        }))
        self.assertEqual(0.06, negative_capex["free_cash_flow_yield"]["value"])
        positive_capex = calculate_valuation_metrics(snapshot(values={
            "free_cash_flow": None, "operating_cash_flow": 100,
            "capital_expenditure": 40,
        }))
        self.assertEqual(0.06, positive_capex["free_cash_flow_yield"]["value"])
        negative = calculate_valuation_metrics(snapshot(values={"free_cash_flow": -20}))
        self.assertEqual(-0.02, negative["free_cash_flow_yield"]["value"])
        self.assertEqual("available", negative["free_cash_flow_yield"]["support_state"])

    def test_negative_earnings_yield_is_available_but_not_cheap(self):
        result = calculate_valuation_metrics(snapshot(values={"net_income": -25}))
        self.assertEqual(-0.025, result["earnings_yield"]["value"])
        self.assertEqual("available", result["earnings_yield"]["support_state"])

    def test_currency_matching_missing_and_mismatch(self):
        self.assertTrue(currency_consistency("usd", "USD"))
        self.assertIsNone(currency_consistency("USD", None))
        self.assertFalse(currency_consistency("USD", "EUR"))
        mismatch = calculate_valuation_metrics(snapshot(
            currency="USD", financial_currency="EUR",
            values={
                "provider_trailing_pe": None, "provider_forward_pe": None,
                "provider_peg_ratio": None, "provider_ev_to_ebitda": None,
                "provider_price_to_sales": None, "provider_price_to_book": None,
            },
        ))
        self.assertTrue(all(
            metric["support_state"] == "unavailable" for metric in mismatch.values()
        ))

    def test_missing_price_and_market_cap_are_controlled(self):
        result = calculate_valuation_metrics(snapshot(values={
            "current_price": None, "market_cap": None,
            "provider_trailing_pe": None, "provider_forward_pe": None,
            "provider_peg_ratio": None, "provider_price_to_sales": None,
            "provider_price_to_book": None,
        }))
        self.assertEqual("unavailable", result["trailing_pe"]["support_state"])
        self.assertEqual("unavailable", result["free_cash_flow_yield"]["support_state"])


class ValuationProfileTests(unittest.TestCase):
    def test_mapping_and_all_profile_validation(self):
        self.assertIs(SectorProfile.TECHNOLOGY, normalize_sector(" information TECHNOLOGY "))
        self.assertIs(SectorProfile.DEFAULT, normalize_sector("Unknown Sector"))
        self.assertTrue(validate_all_valuation_profiles())

    def test_profiles_are_immutable_deterministic_and_total_100(self):
        for profile in SectorProfile:
            with self.subTest(profile=profile.value):
                first = resolve_valuation_profile(profile)
                second = resolve_valuation_profile(profile)
                self.assertEqual(first, second)
                category = first["relative_valuation"]
                self.assertEqual(100, category["weight"])
                self.assertEqual(100, sum(
                    metric["weight"] for metric in category["metrics"].values()
                ))
                with self.assertRaises(TypeError):
                    category["weight"] = 99

    def test_sector_specific_weights_and_exclusions(self):
        financials = resolve_valuation_profile(SectorProfile.FINANCIALS)["relative_valuation"]["metrics"]
        self.assertEqual(27, financials["price_to_book"]["weight"])
        self.assertTrue(financials["ev_to_ebitda"]["unsupported"])
        energy = resolve_valuation_profile(SectorProfile.ENERGY)["relative_valuation"]["metrics"]
        self.assertEqual(25, energy["free_cash_flow_yield"]["weight"])
        self.assertEqual(5, energy["peg_ratio"]["weight"])
        real_estate = resolve_valuation_profile(SectorProfile.REAL_ESTATE)["relative_valuation"]["metrics"]
        self.assertTrue(real_estate["trailing_pe"]["unsupported"])

    def test_same_values_score_differently_by_sector(self):
        metrics = available_metrics()
        default = score_valuation_metrics(metrics, resolve_valuation_profile(SectorProfile.DEFAULT))
        technology = score_valuation_metrics(metrics, resolve_valuation_profile(SectorProfile.TECHNOLOGY))
        self.assertNotEqual(default["score"], technology["score"])
        pe_28 = calculate_valuation_metrics(snapshot(values={
            "current_price": 140, "forward_eps": 5,
        }))
        default = score_valuation_metrics(pe_28, resolve_valuation_profile(SectorProfile.DEFAULT))
        technology = score_valuation_metrics(pe_28, resolve_valuation_profile(SectorProfile.TECHNOLOGY))
        forward_default = next(
            item for item in default["categories"]["relative_valuation"]["details"]
            if item["key"] == "forward_pe"
        )
        forward_technology = next(
            item for item in technology["categories"]["relative_valuation"]["details"]
            if item["key"] == "forward_pe"
        )
        self.assertGreater(forward_technology["score"], forward_default["score"])


class ValuationScoringTests(unittest.TestCase):
    def test_scoring_curves_are_monotonic_bounded_and_anchor_exact(self):
        lower_values = [1, 10, 16, 24, 40, 100]
        lower_scores = [
            score_lower_is_better(value, 10, 16, 24, 40, 20)
            for value in lower_values
        ]
        self.assertEqual(lower_scores, sorted(lower_scores, reverse=True))
        self.assertEqual(20, lower_scores[0])
        self.assertEqual(0, lower_scores[-1])
        higher_scores = [
            score_higher_is_better(value, 0, 0.03, 0.06, 0.10, 12)
            for value in (-1, 0, 0.03, 0.06, 0.10, 1)
        ]
        self.assertEqual(higher_scores, sorted(higher_scores))
        self.assertEqual(0, higher_scores[0])
        self.assertEqual(12, higher_scores[-1])

    def test_classification_boundaries(self):
        cases = {
            0: "Very Expensive", 24.99: "Very Expensive",
            25: "Expensive", 44.99: "Expensive",
            45: "Fairly Valued", 69.99: "Fairly Valued",
            70: "Undervalued", 84.99: "Undervalued",
            85: "Deeply Undervalued", 100: "Deeply Undervalued",
        }
        for score, expected in cases.items():
            with self.subTest(score=score):
                self.assertEqual(expected, valuation_classification(score)[1])

    def test_all_available_has_full_coverage_and_finite_json(self):
        result = score_valuation_metrics(
            available_metrics(), resolve_valuation_profile(SectorProfile.DEFAULT)
        )
        self.assertEqual(100, result["coverage"]["percentage"])
        self.assertEqual(8, result["available_metrics"])
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)
        json.dumps(result, allow_nan=False)

    def test_missing_supported_metric_reduces_coverage_but_not_score_denominator(self):
        metrics = available_metrics()
        metrics["forward_pe"] = {
            "support_state": "unavailable", "value": None,
            "reason": "Forward estimate unavailable",
        }
        result = score_valuation_metrics(metrics, resolve_valuation_profile(SectorProfile.DEFAULT))
        self.assertEqual(80, result["coverage"]["available_weight"])
        self.assertEqual(80, result["coverage"]["percentage"])
        self.assertEqual(7, result["available_metrics"])
        self.assertEqual(1, result["missing_supported_metrics"])

    def test_unsupported_metrics_do_not_reduce_coverage(self):
        result = score_valuation_metrics(
            available_metrics(), resolve_valuation_profile(SectorProfile.FINANCIALS)
        )
        self.assertEqual(100, result["coverage"]["percentage"])
        self.assertEqual(5, result["supported_metrics"])
        self.assertEqual(3, result["unsupported_metrics"])

    def test_unequal_weight_normalization_formula(self):
        profile = {
            "relative_valuation": {
                "label": "Relative Valuation", "weight": 100,
                "metrics": {
                    "forward_pe": {
                        "label": "Forward P/E", "weight": 20, "direction": "lower",
                        "unit": "multiple",
                        "thresholds": {"excellent": 10, "good": 20, "acceptable": 30, "poor": 40},
                    },
                    "trailing_pe": {
                        "label": "Trailing P/E", "weight": 10, "direction": "lower",
                        "unit": "multiple",
                        "thresholds": {"excellent": 10, "good": 20, "acceptable": 30, "poor": 40},
                    },
                    "peg_ratio": {
                        "label": "PEG Ratio", "weight": 70, "direction": "lower",
                        "unit": "multiple",
                        "thresholds": {"excellent": 1, "good": 2, "acceptable": 3, "poor": 4},
                    },
                },
            },
        }
        metrics = {
            "forward_pe": {"support_state": "available", "value": 25},
            "trailing_pe": {"support_state": "available", "value": 10},
            "peg_ratio": {"support_state": "unavailable", "value": None},
        }
        result = score_valuation_metrics(metrics, profile)
        # Forward P/E earns 11/20 and trailing P/E earns 10/10.
        self.assertEqual(70.0, result["categories"]["relative_valuation"]["score"])
        self.assertIsNone(result["score"])  # 30% coverage is below the publishable threshold.
        self.assertEqual(30, result["coverage"]["available_weight"])
        self.assertEqual(0.3, result["coverage"]["weighted_coverage"])
        self.assertEqual(0.6667, result["coverage"]["metric_count_coverage"])

    def test_no_available_metrics_returns_controlled_response(self):
        metrics = {
            key: {"support_state": "unavailable", "value": None}
            for key in available_metrics()
        }
        result = score_valuation_metrics(metrics, resolve_valuation_profile(SectorProfile.DEFAULT))
        self.assertIsNone(result["score"])
        self.assertEqual("unavailable", result["status"])
        json.dumps(result, allow_nan=False)

    def test_negative_multiples_are_never_scored_as_attractive(self):
        metrics = available_metrics()
        for key in ("trailing_pe", "forward_pe", "peg_ratio", "ev_to_ebitda"):
            metrics[key] = {
                "support_state": "not_meaningful", "value": None,
                "raw_value": -1, "reason": "Negative input",
            }
        result = score_valuation_metrics(metrics, resolve_valuation_profile(SectorProfile.DEFAULT))
        for detail in result["categories"]["relative_valuation"]["details"]:
            if detail["key"] in {"trailing_pe", "forward_pe", "peg_ratio", "ev_to_ebitda"}:
                self.assertIsNone(detail["score"])
                self.assertEqual("N/M", detail["display_value"])


class ValuationServiceTests(unittest.TestCase):
    def test_success_metadata_and_unknown_sector_fallback(self):
        def provider(symbol):
            return snapshot(symbol=symbol, sector="Unknown Sector", as_of="2026-01-01",
                            price_source="current_price", price_as_of="2026-01-01")

        result = analyze_valuation("UNITTEST-VALUATION", provider=provider)
        self.assertEqual("default", result["sector_profile"])
        self.assertTrue(result["used_default_profile"])
        self.assertEqual("2A.1", result["scoring_version"])
        self.assertEqual("current_price", result["price_source"])
        json.dumps(result, allow_nan=False)

    def test_unsupported_etf(self):
        def provider(symbol):
            return snapshot(symbol=symbol, instrument_type="ETF")

        result = analyze_valuation("UNITTEST-VALUATION-ETF", provider=provider)
        self.assertEqual("unsupported", result["status"])
        self.assertEqual("unsupported_instrument_type", result["reason_code"])
        self.assertIsNone(result["score"])

    def test_provider_failure_is_safe(self):
        def provider(_symbol):
            raise RuntimeError("secret provider details")

        result = analyze_valuation("UNITTEST-VALUATION-FAIL", provider=provider)
        self.assertEqual("provider_error", result["reason_code"])
        self.assertNotIn("secret", result["message"])


if __name__ == "__main__":
    unittest.main()
