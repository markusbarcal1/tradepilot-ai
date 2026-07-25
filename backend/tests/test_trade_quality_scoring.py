import math
import unittest

from app.services.analyzer import (
    TRADE_QUALITY_FAMILY_WEIGHTS,
    TRADE_QUALITY_SCORE_VERSION,
    calculate_technical_score,
    calculate_trade_quality_score,
    score_trade_risk_reward,
)


def zone(mid, distance, strength="Strong"):
    return {
        "mid": mid,
        "distance_pct": distance,
        "strength": strength,
        "touch_count": 4,
    }


def setup(setup_type, entry, stop, target, bias="Bullish"):
    risk = entry - stop if entry is not None and stop is not None else None
    reward = target - entry if entry is not None and target is not None else None
    ratio = reward / risk if risk is not None and reward is not None and risk > 0 else None
    return {
        "setup_type": setup_type,
        "setup_bias": bias,
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": round(ratio, 2) if ratio is not None else "N/A",
        "risk_pct": round(risk / entry * 100, 2) if risk is not None and entry else None,
    }


class TradeQualityScenarioTests(unittest.TestCase):
    def test_components_include_expandable_detail_contract(self):
        result = calculate_trade_quality_score(
            100, 98, 95, 60, 1.5, 2, 1,
            zone(95, 5), zone(110, 10),
            setup("Momentum Long", entry=100, stop=95, target=110),
        )
        for component in result["components"].values():
            self.assertTrue(component["details"])
            self.assertTrue(all("score" in detail and "max_score" in detail
                                for detail in component["details"]))
    def score(self, price, sma_20, sma_50, rsi, rvol, macd, signal,
              support, resistance, trade_setup):
        return calculate_trade_quality_score(
            price, sma_20, sma_50, rsi, rvol, macd, signal,
            support, resistance, trade_setup,
        )

    def test_strong_breakout_scores_high(self):
        result = self.score(
            100, 98, 95, 60, 2.2, 2, 1,
            zone(95, 5), zone(102, 2),
            setup("Breakout Watch", 102.2, 95, 116.6),
        )
        self.assertGreaterEqual(result["score"], 75)

    def test_weak_extended_breakout_scores_much_lower(self):
        result = self.score(
            100, 85, 80, 76, 0.5, 2, 1,
            zone(80, 20), zone(100.5, 0.5),
            setup("Breakout Watch", 100.7, 80, 105),
        )
        self.assertLess(result["score"], 50)

    def test_controlled_pullback_scores_well(self):
        result = self.score(
            100, 99, 95, 48, 1.2, 1, 0.5,
            zone(98, 2), zone(110, 10),
            setup("Pullback Bounce", 100, 97, 110),
        )
        self.assertGreaterEqual(result["score"], 70)

    def test_falling_knife_stays_low_despite_nearby_support(self):
        result = self.score(
            100, 110, 115, 25, 1.5, -2, -1,
            zone(98, 2), zone(110, 10),
            setup("Breakdown Risk", 100, 102, 96, bias="Bearish"),
        )
        self.assertLessEqual(result["score"], 10)

    def test_strong_technical_stock_can_have_poor_trade_quality(self):
        support = zone(90, 25)
        resistance = zone(125, 4.2)
        technical = calculate_technical_score(
            120, 100, 95, 74, 1.5, 2, 1, support, resistance,
        )
        quality = self.score(
            120, 100, 95, 74, 1.5, 2, 1, support, resistance,
            setup("Momentum Long", 120, 90, 125),
        )
        self.assertGreaterEqual(technical["score"], 70)
        self.assertLess(quality["score"], 40)

    def test_poor_reward_to_risk_scores_poorly(self):
        result = score_trade_risk_reward(setup("Momentum Long", 100, 90, 105))
        self.assertLessEqual(result["score"], 6)

    def test_missing_data_never_produces_nan(self):
        result = self.score(
            None, None, math.nan, None, None, None, None,
            None, None, setup("No Clear Setup", None, None, None, bias="Neutral"),
        )
        self.assertEqual(0, result["score"])
        for component in result["components"].values():
            self.assertTrue(math.isfinite(component["score"]))

    def test_contract_version_caps_and_sum(self):
        result = self.score(
            100, 98, 95, 60, 2.2, 2, 1,
            zone(95, 5), zone(102, 2),
            setup("Breakout Watch", 102.2, 95, 116.6),
        )
        self.assertEqual(TRADE_QUALITY_SCORE_VERSION, result["version"])
        self.assertEqual(set(TRADE_QUALITY_FAMILY_WEIGHTS), set(result["components"]))
        self.assertEqual(result["score"], sum(c["score"] for c in result["components"].values()))
        self.assertEqual(100, sum(c["max_score"] for c in result["components"].values()))
        for key, component in result["components"].items():
            self.assertTrue(0 <= component["score"] <= TRADE_QUALITY_FAMILY_WEIGHTS[key])


if __name__ == "__main__":
    unittest.main()
