import json
import math
import unittest

from app.services.financial_analysis.models import FinancialSnapshot
from app.services.financial_analysis.profiles import (
    PROFILE_LABELS,
    SectorProfile,
    normalize_sector,
    resolve_profile,
    validate_all_profiles,
)
from app.services.financial_analysis.scoring import score_financial_metrics
from app.services.financial_analysis.service import analyze_financials


def complete_metrics(**overrides):
    values = {
        "roic": 0.12, "return_on_capital": 0.15, "return_on_equity": 0.15,
        "gross_margin": 0.40, "operating_margin": 0.15, "net_margin": 0.12,
        "revenue_growth": 0.10, "eps_growth": 0.12, "free_cash_flow_growth": 0.10,
        "operating_income_growth": 0.10, "debt_to_equity": 1.0,
        "current_ratio": 1.5, "interest_coverage": 5.0, "net_debt_to_ebitda": 2.0,
        "free_cash_flow": 1_000_000, "operating_cash_flow_to_net_income": 1.0,
        "free_cash_flow_margin": 0.08, "positive_cash_flow_consistency": 0.75,
        "operating_cash_flow_margin": 0.15,
    }
    values.update(overrides)
    return values


class SectorMappingTests(unittest.TestCase):
    def test_exact_alias_case_and_whitespace_mapping(self):
        cases = {
            "Technology": SectorProfile.TECHNOLOGY,
            " information TECHNOLOGY ": SectorProfile.TECHNOLOGY,
            "Health Care": SectorProfile.HEALTHCARE,
            "Financial Services": SectorProfile.FINANCIALS,
            "Consumer Cyclical": SectorProfile.CONSUMER_DISCRETIONARY,
            "Consumer Defensive": SectorProfile.CONSUMER_STAPLES,
            "Basic   Materials": SectorProfile.MATERIALS,
            "Real Estate": SectorProfile.REAL_ESTATE,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertIs(expected, normalize_sector(raw))

    def test_missing_and_unknown_use_default(self):
        for raw in (None, "", "   ", "Conglomerates", 42):
            with self.subTest(raw=raw):
                self.assertIs(SectorProfile.DEFAULT, normalize_sector(raw))


class ProfileConfigurationTests(unittest.TestCase):
    def test_all_profiles_validate(self):
        self.assertTrue(validate_all_profiles())
        self.assertEqual(set(profile.value for profile in SectorProfile), set(PROFILE_LABELS))

    def test_resolution_is_deterministic_immutable_and_does_not_mutate_default(self):
        before = resolve_profile(SectorProfile.DEFAULT)
        first = resolve_profile(SectorProfile.TECHNOLOGY)
        second = resolve_profile(SectorProfile.TECHNOLOGY)
        self.assertEqual(first, second)
        self.assertEqual(before, resolve_profile(SectorProfile.DEFAULT))
        with self.assertRaises(TypeError):
            first["profitability"]["weight"] = 99

    def test_every_profile_has_valid_weight_totals(self):
        for profile in SectorProfile:
            resolved = resolve_profile(profile)
            with self.subTest(profile=profile.value):
                self.assertEqual(100, sum(category["weight"] for category in resolved.values()))
                for category in resolved.values():
                    self.assertEqual(
                        category["weight"],
                        sum(metric["weight"] for metric in category["metrics"].values()),
                    )
                    for metric in category["metrics"].values():
                        self.assertGreaterEqual(metric["weight"], 0)


class SectorScoringTests(unittest.TestCase):
    def test_default_profile_reproduces_phase_1a(self):
        values = complete_metrics()
        self.assertEqual(
            score_financial_metrics(values),
            score_financial_metrics(values, resolve_profile(SectorProfile.DEFAULT)),
        )

    def test_slow_growth_and_high_leverage_are_penalized_less_for_utilities(self):
        values = complete_metrics(
            roic=0.07, revenue_growth=0.04, eps_growth=0.05,
            debt_to_equity=2.5, net_debt_to_ebitda=4.8,
        )
        technology = score_financial_metrics(values, resolve_profile(SectorProfile.TECHNOLOGY))
        utilities = score_financial_metrics(values, resolve_profile(SectorProfile.UTILITIES))
        self.assertGreater(utilities["score"], technology["score"])
        self.assertGreater(
            utilities["categories"]["growth"]["score"],
            technology["categories"]["growth"]["score"],
        )
        self.assertGreater(
            utilities["categories"]["financial_health"]["score"],
            technology["categories"]["financial_health"]["score"],
        )

    def test_financials_exclude_corporate_leverage_without_reducing_coverage(self):
        result = score_financial_metrics(
            complete_metrics(), resolve_profile(SectorProfile.FINANCIALS)
        )
        self.assertEqual("available", result["status"])
        self.assertEqual(100, result["coverage"]["percentage"])
        self.assertEqual(13, result["supported_metrics"])
        self.assertEqual(19, result["configured_metrics"])
        self.assertEqual(6, result["unsupported_metrics"])
        self.assertEqual(0, result["missing_supported_metrics"])
        self.assertEqual("weighted", result["coverage"]["coverage_method"])
        details = [
            detail
            for category in result["categories"].values()
            for detail in category["details"]
            if detail["status"] == "unsupported_for_sector"
        ]
        self.assertEqual(6, len(details))
        self.assertTrue(all(detail["max_score"] == 0 for detail in details))
        self.assertTrue(all(detail["availability"] == "unsupported_for_sector" for detail in details))

    def test_missing_supported_metric_reduces_sector_coverage(self):
        values = complete_metrics(return_on_equity=None)
        result = score_financial_metrics(values, resolve_profile(SectorProfile.FINANCIALS))
        self.assertEqual("partial", result["status"])
        self.assertLess(result["coverage"]["percentage"], 100)
        self.assertEqual(12, result["available_metrics"])
        self.assertEqual(13, result["expected_metrics"])
        self.assertEqual(1, result["missing_supported_metrics"])

    def test_real_estate_explicitly_excludes_misleading_gaap_metrics(self):
        result = score_financial_metrics(
            complete_metrics(), resolve_profile(SectorProfile.REAL_ESTATE)
        )
        excluded = {
            detail["key"]
            for category in result["categories"].values()
            for detail in category["details"]
            if detail["status"] == "unsupported_for_sector"
        }
        self.assertEqual({
            "net_margin", "eps_growth", "free_cash_flow_growth",
            "operating_cash_flow_to_net_income", "free_cash_flow_margin",
        }, excluded)
        self.assertEqual(100, result["coverage"]["percentage"])

    def test_energy_deemphasizes_growth(self):
        profile = resolve_profile(SectorProfile.ENERGY)
        self.assertEqual(15, profile["growth"]["weight"])
        self.assertEqual(30, profile["financial_health"]["weight"])
        self.assertEqual(30, profile["cash_flow_quality"]["weight"])

    def test_all_profiles_produce_bounded_finite_json(self):
        for profile in SectorProfile:
            with self.subTest(profile=profile.value):
                result = score_financial_metrics(complete_metrics(), resolve_profile(profile))
                self.assertGreaterEqual(result["score"], 0)
                self.assertLessEqual(result["score"], 100)
                self.assertTrue(math.isfinite(result["score"]))
                json.dumps(result, allow_nan=False)

    def test_category_normalization_uses_available_weight_not_metric_count(self):
        default_metrics = resolve_profile(SectorProfile.DEFAULT)["profitability"]["metrics"]
        profile = {
            "profitability": {
                "weight": 20,
                "metrics": {
                    key: {
                        **dict(default_metrics[key]),
                        "thresholds": dict(default_metrics[key]["thresholds"]),
                    }
                    for key in ("roic", "return_on_capital", "return_on_equity")
                },
            },
        }
        profile["profitability"]["metrics"]["roic"]["weight"] = 8
        profile["profitability"]["metrics"]["return_on_capital"]["weight"] = 2
        profile["profitability"]["metrics"]["return_on_equity"]["weight"] = 10
        result = score_financial_metrics({
            # ROIC earns 50% quality (4/8); ROCE earns 2/2; ROE is missing.
            "roic": 0.09333333333333334,
            "return_on_capital": 0.25,
            "return_on_equity": None,
        }, profile)
        category = result["categories"]["profitability"]
        self.assertEqual(10, category["available_weight"])
        self.assertEqual(20, category["supported_weight"])
        self.assertEqual(12.0, category["score"])
        self.assertEqual(0.5, category["weighted_coverage"])
        self.assertEqual(0.6667, category["metric_count_coverage"])

    def test_unsupported_metric_is_excluded_from_both_denominators(self):
        result = score_financial_metrics(
            complete_metrics(), resolve_profile(SectorProfile.REAL_ESTATE)
        )
        growth = result["categories"]["growth"]
        self.assertEqual(4, growth["configured_metrics"])
        self.assertEqual(2, growth["supported_metrics"])
        self.assertEqual(2, growth["unsupported_metrics"])
        self.assertEqual(2, growth["available_metrics"])
        self.assertEqual(25, growth["available_weight"])
        self.assertEqual(25, growth["supported_weight"])
        self.assertEqual(1.0, growth["coverage"])

    def test_no_available_metrics_in_category_is_controlled_and_excluded_once(self):
        values = complete_metrics(
            revenue_growth=None, eps_growth=None,
            free_cash_flow_growth=None, operating_income_growth=None,
        )
        result = score_financial_metrics(values)
        growth = result["categories"]["growth"]
        self.assertIsNone(growth["score"])
        self.assertEqual("Unavailable", growth["label"])
        self.assertEqual("Insufficient supported data to score this category.", growth["normalization_note"])
        available_scores = sum(
            category["score"] for category in result["categories"].values()
            if category["score"] is not None
        )
        available_category_weight = sum(
            category["max_score"] for category in result["categories"].values()
            if category["score"] is not None
        )
        self.assertEqual(
            round(available_scores / available_category_weight * 100, 1),
            result["score"],
        )

    def test_invalid_values_are_missing_supported_and_never_serialize(self):
        for invalid in (None, math.nan, math.inf, -math.inf, "not-a-number"):
            with self.subTest(invalid=invalid):
                result = score_financial_metrics(complete_metrics(roic=invalid))
                profitability = result["categories"]["profitability"]
                self.assertEqual(5, profitability["available_metrics"])
                self.assertEqual(1, profitability["missing_supported_metrics"])
                self.assertLess(profitability["coverage"], 1)
                json.dumps(result, allow_nan=False)

    def test_every_profile_and_category_satisfies_normalization_invariants(self):
        for profile_name in SectorProfile:
            result = score_financial_metrics(
                complete_metrics(), resolve_profile(profile_name)
            )
            with self.subTest(profile=profile_name.value):
                self.assertEqual(
                    result["configured_metrics"],
                    result["supported_metrics"] + result["unsupported_metrics"],
                )
                self.assertEqual(
                    result["supported_metrics"],
                    result["available_metrics"] + result["missing_supported_metrics"],
                )
                category_score_sum = 0
                for category in result["categories"].values():
                    self.assertEqual(
                        category["configured_metrics"],
                        category["supported_metrics"] + category["unsupported_metrics"],
                    )
                    self.assertEqual(
                        category["supported_metrics"],
                        category["available_metrics"] + category["missing_supported_metrics"],
                    )
                    self.assertLessEqual(category["available_weight"], category["supported_weight"])
                    earned = sum(
                        detail["score"] for detail in category["details"]
                        if detail["score"] is not None
                    )
                    self.assertGreaterEqual(earned, 0)
                    self.assertLessEqual(earned, category["available_weight"] + 0.1)
                    if category["score"] is not None:
                        self.assertGreaterEqual(category["score"], 0)
                        self.assertLessEqual(category["score"], category["max_score"])
                        category_score_sum += category["score"]
                self.assertAlmostEqual(result["score"], category_score_sum, delta=0.11)
                self.assertTrue(math.isfinite(result["score"]))


class SectorServiceTests(unittest.TestCase):
    def test_api_metadata_preserves_raw_sector_and_selected_profile(self):
        def provider(symbol):
            return FinancialSnapshot(
                symbol, sector=" Information Technology ", values={},
            )

        result = analyze_financials("UNITTEST-SECTOR-TECH", provider=provider)
        self.assertEqual(" Information Technology ", result["sector"])
        self.assertEqual("technology", result["sector_profile"])
        self.assertEqual("Technology", result["sector_profile_label"])
        self.assertFalse(result["used_default_profile"])
        self.assertEqual("provider", result["sector_source"])

    def test_unknown_sector_exposes_honest_default_fallback(self):
        def provider(symbol):
            return FinancialSnapshot(symbol, sector="Conglomerates", values={})

        result = analyze_financials("UNITTEST-SECTOR-UNKNOWN", provider=provider)
        self.assertEqual("Conglomerates", result["sector"])
        self.assertEqual("default", result["sector_profile"])
        self.assertEqual("General Company", result["sector_profile_label"])
        self.assertTrue(result["used_default_profile"])


if __name__ == "__main__":
    unittest.main()
