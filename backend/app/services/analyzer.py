from app.services.market_data import get_price_history
from app.services.indicators import calculate_sma, calculate_rsi, calculate_macd
from copy import deepcopy
import math
from threading import RLock
from time import time

ANALYSIS_CACHE_TTL_SECONDS = 60
_analysis_cache = {}
_analysis_cache_lock = RLock()

TECHNICAL_SCORE_VERSION = "2.0"
TECHNICAL_FAMILY_WEIGHTS = {
    "trend": 40,
    "momentum": 30,
    "participation": 15,
    "price_structure": 15,
}

TRADE_QUALITY_SCORE_VERSION = "1.0"
TRADE_QUALITY_FAMILY_WEIGHTS = {
    "location": 30,
    "confirmation": 25,
    "risk_reward": 20,
    "timing": 15,
    "confluence": 10,
}

def safe_float(value, decimals=2):
    try:
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, decimals)
    except Exception:
        return None
    
def clean_for_json(value):
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, dict):
        return {k: clean_for_json(v) for k, v in value.items()}

    if isinstance(value, list):
        return [clean_for_json(item) for item in value]

    return value

def find_support_resistance(data, lookback: int = 160, window: int = 3):
    recent = data.tail(lookback).copy()
    current_price = float(recent["Close"].iloc[-1])

    swing_highs = []
    swing_lows = []

    for i in range(window, len(recent) - window):
        current_high = float(recent["High"].iloc[i])
        current_low = float(recent["Low"].iloc[i])

        left_highs = recent["High"].iloc[i - window:i]
        right_highs = recent["High"].iloc[i + 1:i + window + 1]

        left_lows = recent["Low"].iloc[i - window:i]
        right_lows = recent["Low"].iloc[i + 1:i + window + 1]

        if current_high > left_highs.max() and current_high > right_highs.max():
            swing_highs.append(current_high)

        if current_low < left_lows.min() and current_low < right_lows.min():
            swing_lows.append(current_low)

    def get_strength(touch_count, distance_pct):
        if touch_count >= 4 and distance_pct <= 5:
            return "Strong"
        if touch_count >= 3 and distance_pct <= 8:
            return "Moderate"
        if touch_count >= 2:
            return "Weak"
        return "Very Weak"

    def build_zone_from_anchor(levels, anchor, zone_side):
        tolerance = current_price * 0.015

        clustered = [
            level for level in levels
            if abs(level - anchor) <= tolerance
        ]

        if not clustered:
            return None

        zone_low = round(min(clustered), 2)
        zone_high = round(max(clustered), 2)
        zone_mid = round((zone_low + zone_high) / 2, 2)

        touch_count = len(clustered)
        distance_pct = round(abs(current_price - zone_mid) / current_price * 100, 2)

        min_zone_width = current_price * 0.003
        zone_width = zone_high - zone_low

        is_zone = zone_width >= min_zone_width

        strength = get_strength(touch_count, distance_pct)

        if is_zone:
            display = f"${zone_low} - ${zone_high}"
            zone_type = f"{zone_side}_zone"
        else:
            display = f"${zone_mid}"
            zone_type = f"{zone_side}_level"

        return {
            "low": zone_low,
            "high": zone_high,
            "mid": zone_mid,
            "display": display,
            "is_zone": is_zone,
            "type": zone_type,
            "strength": strength,
            "touch_count": touch_count,
            "distance_pct": distance_pct,
        }

    valid_supports = sorted(
        [level for level in swing_lows if level < current_price],
        key=lambda level: abs(level - current_price)
    )

    valid_resistances = sorted(
        [level for level in swing_highs if level > current_price],
        key=lambda level: abs(level - current_price)
    )

    support_zone = (
        build_zone_from_anchor(swing_lows, valid_supports[0], "support")
        if valid_supports
        else None
    )

    resistance_zone = (
        build_zone_from_anchor(swing_highs, valid_resistances[0], "resistance")
        if valid_resistances
        else None
    )

    if support_zone is None:
        recent_low = round(float(recent["Low"].min()), 2)

        if recent_low < current_price:
            distance_pct = round(abs(current_price - recent_low) / current_price * 100, 2)

            support_zone = {
                "low": recent_low,
                "high": recent_low,
                "mid": recent_low,
                "display": f"${recent_low}",
                "is_zone": False,
                "type": "recent_low",
                "strength": "Weak",
                "touch_count": 1,
                "distance_pct": distance_pct,
            }

    if resistance_zone is None:
        yearly_high = round(float(data["High"].tail(252).max()), 2)

        if yearly_high > current_price:
            distance_pct = round(abs(yearly_high - current_price) / current_price * 100, 2)

            resistance_zone = {
                "low": yearly_high,
                "high": yearly_high,
                "mid": yearly_high,
                "display": f"${yearly_high}",
                "is_zone": False,
                "type": "52_week_high",
                "strength": "Weak",
                "touch_count": 1,
                "distance_pct": distance_pct,
            }
        else:
            resistance_zone = {
                "low": None,
                "high": None,
                "mid": None,
                "display": "Price Discovery",
                "is_zone": False,
                "type": "price_discovery",
                "strength": "N/A",
                "touch_count": 0,
                "distance_pct": None,
            }

    return {
        "support_zone": support_zone,
        "resistance_zone": resistance_zone,
    }

def generate_trade_thesis(price, sma_20, sma_50, rsi, rvol, macd, macd_signal, macd_hist, support_zone, resistance_zone):
    bull_case = []
    bear_case = []
    score = 50

    if price > sma_20:
        bull_case.append("Price is holding above the short-term trend line.")
        score += 8
    else:
        bear_case.append("Price has slipped below the short-term trend line.")
        score -= 8

    if price > sma_50:
        bull_case.append("Price remains above the intermediate trend line.")
        score += 8
    else:
        bear_case.append("Price is trading below the intermediate trend line.")
        score -= 8

    if sma_20 > sma_50:
        bull_case.append("The 20 SMA remains above the 50 SMA, supporting a constructive trend structure.")
        score += 8
    else:
        bear_case.append("The 20 SMA is below the 50 SMA, suggesting weaker trend structure.")
        score -= 8

    if macd > macd_signal and macd_hist > 0:
        bull_case.append("Momentum is improving, with MACD above the signal line.")
        score += 10
    elif macd < macd_signal and macd_hist < 0:
        bear_case.append("Momentum is weakening, with MACD below the signal line.")
        score -= 10

    if rvol >= 2:
        bull_case.append("Relative volume is elevated, showing strong participation.")
        score += 8
    elif rvol < 0.8:
        bear_case.append("Relative volume is light, suggesting limited conviction behind the move.")
        score -= 5

    if rsi >= 70:
        bear_case.append("RSI is extended, increasing the risk of a short-term pullback.")
        score -= 8
    elif 50 <= rsi < 70:
        bull_case.append("RSI is in a healthy bullish momentum range.")
        score += 5
    elif rsi < 30:
        bear_case.append("RSI is oversold, signaling weakness despite possible bounce potential.")
        score -= 5

    if support_zone and support_zone.get("mid"):
        support_strength = support_zone.get("strength", "unknown").lower()
        support_touches = support_zone.get("touch_count", 0)
        support_distance = support_zone.get("distance_pct")

        if support_distance is not None:
            if support_distance <= 3:
                bull_case.append(
                    f"Price is trading near {support_strength} support that has been tested {support_touches} time(s)."
                )
                score += 8
            elif support_distance <= 7:
                bull_case.append(
                    f"Support sits {support_distance}% below price, giving traders a nearby downside reference."
                )
                score += 4
            else:
                bear_case.append(
                    f"Nearest support is {support_distance}% below price, leaving wider downside risk."
                )
                score -= 3

    if resistance_zone and resistance_zone.get("mid"):
        resistance_strength = resistance_zone.get("strength", "unknown").lower()
        resistance_touches = resistance_zone.get("touch_count", 0)
        resistance_distance = resistance_zone.get("distance_pct")

        if resistance_distance is not None:
            if resistance_distance <= 3:
                bear_case.append(
                    f"Price is pressing into {resistance_strength} resistance that has been tested {resistance_touches} time(s)."
                )
                score -= 6
            elif resistance_distance >= 7:
                bull_case.append(
                    f"Resistance is {resistance_distance}% above price, leaving meaningful upside room."
                )
                score += 6
            else:
                bull_case.append(
                    f"Resistance is {resistance_distance}% above price, leaving some upside room."
                )
                score += 3

    support_text = support_zone["display"] if support_zone else "N/A"
    resistance_text = resistance_zone["display"] if resistance_zone else "N/A"

    risk_reward = "N/A"

    if support_zone and resistance_zone:
        support_level = support_zone.get("mid")
        resistance_level = resistance_zone.get("mid")

        if support_level and resistance_level and price > support_level:
            downside = price - support_level
            upside = resistance_level - price

            if downside > 0 and upside > 0:
                risk_reward = round(upside / downside, 2)

    score = max(0, min(100, score))

    if score >= 75:
        thesis_rating = "Strong Bullish"
        evidence_label = "Bullish Evidence"
    elif score >= 60:
        thesis_rating = "Bullish"
        evidence_label = "Bullish Evidence"
    elif score >= 45:
        thesis_rating = "Neutral"
        evidence_label = "Mixed Evidence"
    elif score >= 30:
        thesis_rating = "Bearish"
        evidence_label = "Bearish Evidence"
    else:
        thesis_rating = "Strong Bearish"
        evidence_label = "Bearish Evidence"

    evidence_score = score if score >= 45 else 100 - score

    return {
        "rating": thesis_rating,
        "evidence_label": evidence_label,
        "evidence_score": evidence_score,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "support": support_text,
        "resistance": resistance_text,
        "risk_reward": risk_reward,
    }

def _valid_number(value, *, minimum=None, maximum=None):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if minimum is not None and number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _family_result(score, max_score, status, positives, negatives, inputs):
    return {
        "score": max(0, min(int(round(score)), max_score)),
        "max_score": max_score,
        "status": status,
        "positive_reasons": positives,
        "negative_reasons": negatives,
        "inputs": inputs,
    }


def score_trend_family(price, sma_20, sma_50):
    max_score = TECHNICAL_FAMILY_WEIGHTS["trend"]
    price = _valid_number(price, minimum=0)
    sma_20 = _valid_number(sma_20, minimum=0)
    sma_50 = _valid_number(sma_50, minimum=0)
    available = price is not None and sma_20 is not None and sma_50 is not None
    inputs = {
        "data_available": available,
        "price_above_sma_20": price > sma_20 if available else None,
        "price_above_sma_50": price > sma_50 if available else None,
        "sma_20_above_sma_50": sma_20 > sma_50 if available else None,
    }
    if not available:
        return _family_result(0, max_score, "unavailable", [],
                              ["Trend inputs are missing or invalid"], inputs)

    positives = []
    negatives = []
    score = 0
    if inputs["price_above_sma_20"]:
        score += 14
        positives.append("Price is above the short-term moving average")
    else:
        negatives.append("Price is below the short-term moving average")
    if inputs["price_above_sma_50"]:
        score += 14
        positives.append("Price is above the intermediate moving average")
    else:
        negatives.append("Price is below the intermediate moving average")
    if inputs["sma_20_above_sma_50"]:
        score += 12
        positives.append("The short-term moving average is above the intermediate average")
    else:
        negatives.append("The short-term moving average is not above the intermediate average")

    status = "supportive" if score >= 28 else "mixed" if score >= 14 else "weak"
    return _family_result(score, max_score, status, positives, negatives, inputs)


def score_momentum_family(rsi, macd, macd_signal):
    max_score = TECHNICAL_FAMILY_WEIGHTS["momentum"]
    rsi = _valid_number(rsi, minimum=0, maximum=100)
    macd = _valid_number(macd)
    macd_signal = _valid_number(macd_signal)
    available = rsi is not None and macd is not None and macd_signal is not None
    inputs = {
        "data_available": available,
        "macd_above_signal": macd > macd_signal if available else None,
        "rsi_bucket": None,
    }
    if not available:
        return _family_result(0, max_score, "unavailable", [],
                              ["Momentum inputs are missing or invalid"], inputs)

    positives = []
    negatives = []
    if macd > macd_signal:
        score = 16
        positives.append("MACD is above its signal line")
    elif macd == macd_signal:
        score = 8
        negatives.append("MACD is flat against its signal line")
    else:
        score = 4
        negatives.append("MACD is below its signal line")

    if rsi > 70:
        score += 8
        inputs["rsi_bucket"] = "extended"
        positives.append("RSI shows strong momentum")
        negatives.append("RSI is extended above 70")
    elif rsi >= 50:
        score += 14
        inputs["rsi_bucket"] = "supportive"
        positives.append("RSI is in a supportive 50-70 range")
    elif rsi >= 40:
        score += 8
        inputs["rsi_bucket"] = "neutral"
        negatives.append("RSI is below the supportive momentum range")
    elif rsi >= 30:
        score += 5
        inputs["rsi_bucket"] = "weak"
        negatives.append("RSI shows weak momentum")
    else:
        score += 3
        inputs["rsi_bucket"] = "oversold"
        negatives.append("RSI is oversold; this alone is not a bullish signal")

    status = "supportive" if score >= 21 and rsi <= 70 else "mixed" if score >= 12 else "weak"
    return _family_result(score, max_score, status, positives, negatives, inputs)


def score_participation_family(rvol):
    max_score = TECHNICAL_FAMILY_WEIGHTS["participation"]
    rvol = _valid_number(rvol, minimum=0)
    inputs = {"data_available": rvol is not None, "relative_volume_bucket": None}
    if rvol is None:
        return _family_result(0, max_score, "unavailable", [],
                              ["Relative volume is missing or invalid"], inputs)
    if rvol >= 2:
        score, status, bucket = 15, "elevated", "elevated"
        positives = ["Relative volume shows elevated participation; direction comes from trend and momentum"]
        negatives = []
    elif rvol >= 1:
        score, status, bucket = 10, "normal", "above_average"
        positives = ["Relative volume shows above-average participation"]
        negatives = []
    elif rvol >= 0.7:
        score, status, bucket = 5, "light", "light"
        positives = []
        negatives = ["Relative volume shows light participation"]
    else:
        score, status, bucket = 0, "weak", "very_light"
        positives = []
        negatives = ["Relative volume shows very light participation"]
    inputs["relative_volume_bucket"] = bucket
    return _family_result(score, max_score, status, positives, negatives, inputs)


def _zone_inputs(zone):
    if not isinstance(zone, dict):
        return None, None, None
    mid = _valid_number(zone.get("mid"), minimum=0)
    distance = _valid_number(zone.get("distance_pct"), minimum=0)
    strength = zone.get("strength")
    strength = strength.lower() if isinstance(strength, str) else None
    return mid, distance, strength


def score_price_structure_family(price, support_zone, resistance_zone):
    max_score = TECHNICAL_FAMILY_WEIGHTS["price_structure"]
    price = _valid_number(price, minimum=0)
    support_mid, support_distance, support_strength = _zone_inputs(support_zone)
    resistance_mid, resistance_distance, resistance_strength = _zone_inputs(resistance_zone)
    support_available = (price is not None and price > 0 and support_mid is not None
                         and support_mid < price and support_distance is not None)
    resistance_available = (price is not None and price > 0 and resistance_mid is not None
                            and resistance_mid > price and resistance_distance is not None)
    inputs = {
        "data_available": price is not None and price > 0 and (support_available or resistance_available),
        "support_available": support_available,
        "resistance_available": resistance_available,
        "support_distance_bucket": None,
        "support_strength": support_strength,
        "resistance_distance_bucket": None,
        "resistance_strength": resistance_strength,
    }
    if price is None or price <= 0:
        return _family_result(0, max_score, "unavailable", [],
                              ["Price is missing or invalid for structure scoring"], inputs)

    score = 0
    positives = []
    negatives = []
    if support_available:
        if support_distance <= 3:
            inputs["support_distance_bucket"] = "nearby"
            score += {"strong": 8, "moderate": 7, "weak": 6, "very weak": 5}.get(support_strength, 5)
            positives.append("Confirmed support is nearby")
        elif support_distance <= 7:
            inputs["support_distance_bucket"] = "usable"
            score += 5 if support_strength in ("strong", "moderate") else 4
            positives.append("Support provides a usable downside reference")
        else:
            inputs["support_distance_bucket"] = "distant"
            score += 2 if support_strength in ("strong", "moderate") else 1
            negatives.append("Nearest support is far below price")
    else:
        negatives.append("Support data is unavailable or not below price")

    if resistance_available:
        if resistance_distance >= 7:
            inputs["resistance_distance_bucket"] = "ample_room"
            score += 7
            positives.append("Price has meaningful room before resistance")
        elif resistance_distance >= 3:
            inputs["resistance_distance_bucket"] = "usable_room"
            score += 5
            positives.append("Price has usable room before resistance")
        else:
            inputs["resistance_distance_bucket"] = "nearby"
            score += 0 if resistance_strength == "strong" else 1 if resistance_strength == "moderate" else 2
            negatives.append("Price is close to overhead resistance")
    else:
        negatives.append("Resistance data is unavailable or not above price")

    if not support_available and not resistance_available:
        status = "unavailable"
    elif score >= 11:
        status = "supportive"
    elif score >= 6:
        status = "mixed"
    else:
        status = "weak"
    return _family_result(score, max_score, status, positives, negatives, inputs)


def _technical_grade(score):
    if score >= 80:
        return "Strong Bullish"
    if score >= 60:
        return "Bullish"
    if score >= 40:
        return "Neutral"
    if score >= 20:
        return "Bearish"
    return "Strong Bearish"


def calculate_technical_score(price, sma_20, sma_50, rsi, rvol, macd,
                              macd_signal, support_zone=None, resistance_zone=None):
    components = {
        "trend": score_trend_family(price, sma_20, sma_50),
        "momentum": score_momentum_family(rsi, macd, macd_signal),
        "participation": score_participation_family(rvol),
        "price_structure": score_price_structure_family(price, support_zone, resistance_zone),
    }
    score = sum(component["score"] for component in components.values())
    positives = []
    negatives = []
    for component in components.values():
        positives.extend(reason for reason in component["positive_reasons"] if reason not in positives)
        negatives.extend(reason for reason in component["negative_reasons"] if reason not in negatives)
    return {
        "score": score,
        "grade": _technical_grade(score),
        "positives": positives,
        "negatives": negatives,
        "version": TECHNICAL_SCORE_VERSION,
        "components": components,
    }


def calculate_trend_score(price, sma_20, sma_50, rsi, rvol, macd, macd_signal,
                          support_zone=None, resistance_zone=None):
    """Deprecated compatibility wrapper. Use calculate_technical_score."""
    return calculate_technical_score(
        price, sma_20, sma_50, rsi, rvol, macd, macd_signal,
        support_zone, resistance_zone,
    )

def _bullish_setup(trade_setup):
    return (
        isinstance(trade_setup, dict)
        and trade_setup.get("setup_bias") == "Bullish"
        and trade_setup.get("setup_type") not in (None, "No Clear Setup")
    )


def _distance_pct(first, second):
    first = _valid_number(first, minimum=0)
    second = _valid_number(second, minimum=0)
    if first is None or first <= 0 or second is None or second <= 0:
        return None
    return abs(first - second) / first * 100


def score_trade_location(price, sma_20, sma_50, support_zone, resistance_zone, trade_setup):
    max_score = TRADE_QUALITY_FAMILY_WEIGHTS["location"]
    price = _valid_number(price, minimum=0)
    sma_20 = _valid_number(sma_20, minimum=0)
    sma_50 = _valid_number(sma_50, minimum=0)
    support_mid, support_distance, support_strength = _zone_inputs(support_zone)
    resistance_mid, resistance_distance, _ = _zone_inputs(resistance_zone)
    setup_type = trade_setup.get("setup_type") if isinstance(trade_setup, dict) else None
    valid_setup = _bullish_setup(trade_setup)
    sma_distance = min(
        [distance for distance in (
            _distance_pct(price, sma_20), _distance_pct(price, sma_50)
        ) if distance is not None],
        default=None,
    )
    inputs = {
        "valid_bullish_setup": valid_setup,
        "setup_type": setup_type,
        "support_distance_bucket": None,
        "support_strength": support_strength,
        "resistance_distance_bucket": None,
        "moving_average_distance_bucket": None,
    }
    if price is None or price <= 0 or not valid_setup:
        return _family_result(0, max_score, "unavailable", [],
                              ["No valid bullish setup is available for location scoring"], inputs)

    if support_mid is None or support_mid >= price:
        support_distance = None
    if resistance_mid is None or resistance_mid <= price:
        resistance_distance = None

    score = 0
    positives = []
    negatives = []
    if setup_type == "Breakout Watch":
        if resistance_distance is not None and resistance_distance <= 3:
            score += 18
            inputs["resistance_distance_bucket"] = "breakout_nearby"
            positives.append("Price is close to the planned breakout level")
        elif resistance_distance is not None and resistance_distance <= 5:
            score += 10
            inputs["resistance_distance_bucket"] = "breakout_developing"
            positives.append("The breakout level is within developing range")
        else:
            negatives.append("The breakout level is not near the current price")
        if support_distance is not None and support_distance <= 10:
            score += 6
            inputs["support_distance_bucket"] = "defined"
            positives.append("Support provides a defined downside reference")
        else:
            negatives.append("Support is too distant or unavailable")
        if sma_distance is not None and sma_distance <= 5:
            score += 6
            inputs["moving_average_distance_bucket"] = "controlled"
            positives.append("Price remains reasonably close to a moving average")
        else:
            negatives.append("Price is extended from the available moving averages")
    elif setup_type == "Pullback Bounce":
        if support_distance is not None and support_distance <= 3:
            score += 18
            inputs["support_distance_bucket"] = "nearby"
            positives.append("Price is close to support for the pullback setup")
            score += 4 if support_strength in ("strong", "moderate") else 2
        elif support_distance is not None and support_distance <= 6:
            score += 10
            inputs["support_distance_bucket"] = "usable"
            positives.append("Support remains within usable range")
        else:
            negatives.append("The pullback is not close to a support reference")
        if sma_distance is not None and sma_distance <= 3:
            score += 8
            inputs["moving_average_distance_bucket"] = "nearby"
            positives.append("Price is near a moving average during the pullback")
        elif sma_distance is not None and sma_distance <= 6:
            score += 4
            inputs["moving_average_distance_bucket"] = "usable"
        else:
            negatives.append("The pullback is extended from the moving averages")
    else:  # Momentum Long
        if support_distance is not None and support_distance <= 5:
            score += 10
            inputs["support_distance_bucket"] = "usable"
            positives.append("Support is within a usable range")
        elif support_distance is not None and support_distance <= 10:
            score += 5
            inputs["support_distance_bucket"] = "distant"
        else:
            negatives.append("Support is distant or unavailable")
        if resistance_distance is not None and resistance_distance >= 8:
            score += 12
            inputs["resistance_distance_bucket"] = "ample_room"
            positives.append("There is ample room before resistance")
        elif resistance_distance is not None and resistance_distance >= 4:
            score += 8
            inputs["resistance_distance_bucket"] = "usable_room"
            positives.append("There is usable room before resistance")
        else:
            negatives.append("Upside room before resistance is limited")
        if sma_distance is not None and sma_distance <= 5:
            score += 8
            inputs["moving_average_distance_bucket"] = "controlled"
            positives.append("Price is not excessively extended from its moving averages")
        elif sma_distance is not None and sma_distance <= 10:
            score += 3
            inputs["moving_average_distance_bucket"] = "extended"
        else:
            negatives.append("Price is excessively extended from its moving averages")

    status = "supportive" if score >= 21 else "mixed" if score >= 12 else "weak"
    return _family_result(score, max_score, status, positives, negatives, inputs)


def score_trade_confirmation(rsi, rvol, macd, macd_signal, trade_setup):
    max_score = TRADE_QUALITY_FAMILY_WEIGHTS["confirmation"]
    rsi = _valid_number(rsi, minimum=0, maximum=100)
    rvol = _valid_number(rvol, minimum=0)
    macd = _valid_number(macd)
    macd_signal = _valid_number(macd_signal)
    valid_setup = _bullish_setup(trade_setup)
    inputs = {
        "valid_bullish_setup": valid_setup,
        "relative_volume_bucket": None,
        "macd_above_signal": macd > macd_signal if macd is not None and macd_signal is not None else None,
        "rsi_bucket": None,
    }
    if not valid_setup:
        return _family_result(0, max_score, "unavailable", [],
                              ["No valid bullish setup is available for confirmation scoring"], inputs)

    score = 0
    positives = []
    negatives = []
    if rvol is None:
        negatives.append("Relative volume is unavailable")
    elif rvol >= 2:
        score += 10
        inputs["relative_volume_bucket"] = "strong"
        positives.append("Relative volume strongly confirms the setup")
    elif rvol >= 1:
        score += 7
        inputs["relative_volume_bucket"] = "supportive"
        positives.append("Relative volume supports the setup")
    elif rvol >= 0.7:
        score += 3
        inputs["relative_volume_bucket"] = "light"
        negatives.append("Volume confirmation is light")
    else:
        inputs["relative_volume_bucket"] = "weak"
        negatives.append("Volume does not confirm the setup")

    if macd is None or macd_signal is None:
        negatives.append("MACD confirmation is unavailable")
    elif macd > macd_signal:
        score += 8
        positives.append("MACD confirms bullish entry momentum")
    else:
        negatives.append("MACD does not confirm bullish entry momentum")

    if rsi is None:
        negatives.append("RSI confirmation is unavailable")
    elif 50 <= rsi <= 70:
        score += 7
        inputs["rsi_bucket"] = "supportive"
        positives.append("RSI supports the proposed entry")
    elif 40 <= rsi < 50:
        score += 3
        inputs["rsi_bucket"] = "stabilizing"
        negatives.append("RSI has not fully confirmed the entry")
    elif rsi > 70:
        score += 2
        inputs["rsi_bucket"] = "extended"
        negatives.append("RSI is extended")
    else:
        inputs["rsi_bucket"] = "weak"
        negatives.append("RSI remains weak")

    status = "supportive" if score >= 18 else "mixed" if score >= 10 else "weak"
    return _family_result(score, max_score, status, positives, negatives, inputs)


def score_trade_risk_reward(trade_setup):
    max_score = TRADE_QUALITY_FAMILY_WEIGHTS["risk_reward"]
    setup = trade_setup if isinstance(trade_setup, dict) else {}
    entry = _valid_number(setup.get("entry"), minimum=0)
    stop = _valid_number(setup.get("stop"), minimum=0)
    target = _valid_number(setup.get("target"), minimum=0)
    risk_pct = _valid_number(setup.get("risk_pct"), minimum=0)
    valid = (_bullish_setup(setup) and entry is not None and entry > 0
             and stop is not None and target is not None and stop < entry < target)
    risk = entry - stop if valid else None
    reward = target - entry if valid else None
    ratio = reward / risk if valid and risk > 0 else None
    inputs = {
        "valid_trade_plan": valid and ratio is not None and math.isfinite(ratio),
        "reward_to_risk_bucket": None,
        "stop_distance_bucket": None,
    }
    if not inputs["valid_trade_plan"]:
        return _family_result(0, max_score, "unavailable", [],
                              ["A valid long entry, stop, and target are required"], inputs)

    if ratio >= 3:
        score, bucket = 20, "strong"
    elif ratio >= 2:
        score, bucket = 16, "good"
    elif ratio >= 1.5:
        score, bucket = 12, "moderate"
    elif ratio >= 1:
        score, bucket = 6, "limited"
    else:
        score, bucket = 2, "poor"
    inputs["reward_to_risk_bucket"] = bucket
    positives = [f"The planned reward-to-risk ratio is {round(ratio, 2)}:1"] if ratio >= 1.5 else []
    negatives = [] if ratio >= 1.5 else [f"The planned reward-to-risk ratio is only {round(ratio, 2)}:1"]
    if risk_pct is None:
        risk_pct = risk / entry * 100
    if risk_pct > 10:
        score = min(score, 8)
        inputs["stop_distance_bucket"] = "very_wide"
        negatives.append("The planned stop is very wide")
    elif risk_pct > 6:
        score = max(0, score - 3)
        inputs["stop_distance_bucket"] = "wide"
        negatives.append("The planned stop is wide")
    else:
        inputs["stop_distance_bucket"] = "controlled"
        positives.append("The planned stop distance is controlled")
    status = "supportive" if score >= 14 else "mixed" if score >= 8 else "weak"
    return _family_result(score, max_score, status, positives, negatives, inputs)


def score_trade_timing(price, sma_20, sma_50, rsi, trade_setup):
    max_score = TRADE_QUALITY_FAMILY_WEIGHTS["timing"]
    price = _valid_number(price, minimum=0)
    rsi = _valid_number(rsi, minimum=0, maximum=100)
    setup_type = trade_setup.get("setup_type") if isinstance(trade_setup, dict) else None
    valid_setup = _bullish_setup(trade_setup)
    sma_distance = min(
        [distance for distance in (
            _distance_pct(price, sma_20), _distance_pct(price, sma_50)
        ) if distance is not None],
        default=None,
    )
    inputs = {
        "valid_bullish_setup": valid_setup,
        "setup_stage": setup_type,
        "moving_average_extension_bucket": None,
        "rsi_timing_bucket": None,
    }
    if price is None or price <= 0 or not valid_setup:
        return _family_result(0, max_score, "unavailable", [],
                              ["No valid bullish setup is available for timing scoring"], inputs)

    stage_points = {"Breakout Watch": 5, "Pullback Bounce": 5, "Momentum Long": 3}.get(setup_type, 0)
    score = stage_points
    positives = ["The setup is at a defined entry stage"] if stage_points else []
    negatives = []
    if sma_distance is None:
        negatives.append("Moving-average extension is unavailable")
    elif sma_distance <= 3:
        score += 7
        inputs["moving_average_extension_bucket"] = "early"
        positives.append("Price remains close to a moving-average reference")
    elif sma_distance <= 6:
        score += 5
        inputs["moving_average_extension_bucket"] = "reasonable"
        positives.append("Price extension remains reasonable")
    elif sma_distance <= 10:
        score += 2
        inputs["moving_average_extension_bucket"] = "late"
        negatives.append("The entry is becoming extended")
    else:
        inputs["moving_average_extension_bucket"] = "chasing"
        negatives.append("Price is too extended from its moving averages")

    if rsi is None:
        negatives.append("RSI timing is unavailable")
    elif rsi > 75:
        inputs["rsi_timing_bucket"] = "very_extended"
        negatives.append("RSI indicates a late, extended entry")
    elif rsi > 70:
        score += 2
        inputs["rsi_timing_bucket"] = "extended"
        negatives.append("RSI indicates some entry extension")
    elif rsi >= 40:
        score += 3
        inputs["rsi_timing_bucket"] = "constructive"
        positives.append("RSI timing is constructive")
    else:
        inputs["rsi_timing_bucket"] = "weak"
        negatives.append("RSI does not show entry stabilization")
    status = "supportive" if score >= 11 else "mixed" if score >= 6 else "weak"
    return _family_result(score, max_score, status, positives, negatives, inputs)


def score_trade_confluence(components, valid_setup):
    max_score = TRADE_QUALITY_FAMILY_WEIGHTS["confluence"]
    aligned = [
        key for key in ("location", "confirmation", "risk_reward", "timing")
        if components[key]["score"] >= components[key]["max_score"] * 0.6
    ] if valid_setup else []
    score = {0: 0, 1: 2, 2: 5, 3: 8, 4: 10}[len(aligned)]
    inputs = {"valid_bullish_setup": valid_setup, "aligned_families": aligned}
    positives = [f"{len(aligned)} independent trade-quality families are aligned"] if aligned else []
    negatives = [] if len(aligned) >= 2 else ["Independent trade evidence has limited confluence"]
    status = "supportive" if score >= 8 else "mixed" if score >= 5 else "weak"
    return _family_result(score, max_score, status, positives, negatives, inputs)


def _trade_quality_grade(score):
    if score >= 80:
        return "Excellent Entry"
    if score >= 65:
        return "Good Entry"
    if score >= 50:
        return "Average Entry"
    if score >= 35:
        return "Weak Entry"
    return "Poor Entry"


def calculate_trade_quality_score(price, sma_20, sma_50, rsi, rvol, macd,
                                  macd_signal, support_zone, resistance_zone,
                                  trade_setup):
    components = {
        "location": score_trade_location(
            price, sma_20, sma_50, support_zone, resistance_zone, trade_setup
        ),
        "confirmation": score_trade_confirmation(rsi, rvol, macd, macd_signal, trade_setup),
        "risk_reward": score_trade_risk_reward(trade_setup),
        "timing": score_trade_timing(price, sma_20, sma_50, rsi, trade_setup),
    }
    components["confluence"] = score_trade_confluence(components, _bullish_setup(trade_setup))
    score = max(0, min(100, sum(component["score"] for component in components.values())))
    positives = []
    negatives = []
    for component in components.values():
        positives.extend(reason for reason in component["positive_reasons"] if reason not in positives)
        negatives.extend(reason for reason in component["negative_reasons"] if reason not in negatives)
    return {
        "score": score,
        "grade": _trade_quality_grade(score),
        "positives": positives,
        "negatives": negatives,
        "version": TRADE_QUALITY_SCORE_VERSION,
        "components": components,
    }


def calculate_entry_score(price, rvol, support_zone, resistance_zone, trade_setup,
                          sma_20=None, sma_50=None, rsi=None, macd=None, macd_signal=None):
    """Deprecated compatibility wrapper. Use calculate_trade_quality_score."""
    return calculate_trade_quality_score(
        price, sma_20, sma_50, rsi, rvol, macd, macd_signal,
        support_zone, resistance_zone, trade_setup,
    )

def generate_trade_setup(price, trend, rsi, rvol, macd, macd_signal, macd_hist, support_zone, resistance_zone):
    setup_type = "No Clear Setup"
    setup_bias = "Neutral"
    entry = None
    stop = None
    target = None
    risk_reward = "N/A"
    risk_pct = None
    reward_pct = None
    quality = "Low"
    notes = []

    support = support_zone.get("mid") if support_zone else None
    resistance = resistance_zone.get("mid") if resistance_zone else None

    support_strength = support_zone.get("strength") if support_zone else None
    resistance_strength = resistance_zone.get("strength") if resistance_zone else None
    support_distance = support_zone.get("distance_pct") if support_zone else None
    resistance_distance = resistance_zone.get("distance_pct") if resistance_zone else None

    bullish_momentum = macd > macd_signal and macd_hist > 0
    bearish_momentum = macd < macd_signal and macd_hist < 0

    above_support = support is not None and price > support
    below_resistance = resistance is not None and price < resistance

    near_resistance = (
        resistance is not None
        and price < resistance
        and ((resistance - price) / price) <= 0.03
    )

    near_support = (
        support is not None
        and price > support
        and ((price - support) / price) <= 0.03
    )

    # 1. Breakout Watch
    if resistance and below_resistance and bullish_momentum and near_resistance:
        setup_type = "Breakout Watch"
        setup_bias = "Bullish"
        entry = round(resistance + (price * 0.002), 2)
        stop = round(support if support else price * 0.97, 2)
        target = round(entry + ((entry - stop) * 2), 2)

        notes.append("Price is approaching resistance with improving momentum.")
        notes.append("A breakout trigger would require confirmation above resistance.")
        notes.append(f"Resistance strength is rated {resistance_strength or 'Unknown'}.")

    # 2. Pullback Bounce
    elif support and above_support and near_support and bullish_momentum and rsi < 70:
        setup_type = "Pullback Bounce"
        setup_bias = "Bullish"
        entry = round(price, 2)
        stop = round(support * 0.985, 2)

        if resistance and resistance > price:
            target = round(resistance, 2)
        else:
            target = round(price + ((price - stop) * 2), 2)

        notes.append("Price is holding near support while momentum improves.")
        notes.append("This suggests a potential bounce setup from a defined risk area.")
        notes.append(f"Support strength is rated {support_strength or 'Unknown'}.")

    # 3. Momentum Long
    elif price > 0 and bullish_momentum and 50 <= rsi < 75:
        setup_type = "Momentum Long"
        setup_bias = "Bullish"
        entry = round(price, 2)

        if support and support < price:
            stop = round(support, 2)
        else:
            stop = round(price * 0.97, 2)

        if resistance and resistance > price:
            target = round(resistance, 2)
        else:
            target = round(price + ((price - stop) * 2), 2)

        notes.append("Bullish momentum is active and RSI supports continuation.")
        notes.append("The setup favors continuation as long as momentum holds.")

        if rvol >= 1:
            notes.append("Volume is supportive of the move.")
        else:
            notes.append("Volume confirmation is limited.")

    # 4. Breakdown Risk
    elif support and price < support and bearish_momentum:
        setup_type = "Breakdown Risk"
        setup_bias = "Bearish"
        entry = round(price, 2)
        stop = round(support, 2)
        target = round(price - ((stop - price) * 2), 2)

        notes.append("Price is trading below support with weakening momentum.")
        notes.append("This increases the risk of downside continuation.")
        notes.append(f"Former support strength was rated {support_strength or 'Unknown'}.")

    # 5. Momentum Short
    elif bearish_momentum and rsi < 50:
        setup_type = "Momentum Short"
        setup_bias = "Bearish"
        entry = round(price, 2)

        if resistance and resistance > price:
            stop = round(resistance, 2)
        else:
            stop = round(price * 1.03, 2)

        if support and support < price:
            target = round(support, 2)
        else:
            target = round(price - ((stop - price) * 2), 2)

        notes.append("Bearish momentum is active and RSI remains below 50.")
        notes.append("The setup favors downside continuation unless momentum reverses.")

        if rvol >= 1:
            notes.append("Volume is supportive of the move.")
        else:
            notes.append("Volume confirmation is limited.")

    else:
        notes.append("No clean trade setup is currently detected.")
        notes.append("Conditions may need more confirmation before defining a trade plan.")

    if entry and stop and target:
        risk = abs(entry - stop)
        reward = abs(target - entry)

        if risk > 0:
            rr = round(reward / risk, 2)
            risk_reward = rr
            risk_pct = round((risk / entry) * 100, 2)
            reward_pct = round((reward / entry) * 100, 2)

            if rr >= 3:
                quality = "High Conviction"
            elif rr >= 2:
                quality = "Attractive"
            elif rr >= 1.5:
                quality = "Acceptable"
            else:
                quality = "Unfavorable"

            if rvol < 0.8 and quality in ["High Conviction", "Attractive"]:
                quality = "Acceptable"
                notes.append("Quality is reduced because relative volume is below average.")

            if rvol < 0.6 and quality == "Acceptable":
                quality = "Unfavorable"
                notes.append("Quality is reduced further because volume participation is weak.")

            notes.append(f"Estimated risk is {risk_pct}% from entry to stop.")
            notes.append(f"Estimated reward is {reward_pct}% from entry to target.")
            notes.append(f"Reward/risk ratio is {risk_reward}:1.")

    return {
        "setup_type": setup_type,
        "setup_bias": setup_bias,
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": risk_reward,
        "risk_pct": risk_pct,
        "reward_pct": reward_pct,
        "quality": quality,
        "notes": notes,
        "support_distance_pct": support_distance,
        "resistance_distance_pct": resistance_distance,
    }

def _cache_key(ticker: str, period: str, interval: str):
    return (ticker.strip().upper(), period, interval)


def _get_cached_analysis(key):
    with _analysis_cache_lock:
        cached = _analysis_cache.get(key)

        if not cached:
            return None

        expires_at, analysis = cached

        if expires_at <= time():
            del _analysis_cache[key]
            return None

        return deepcopy(analysis)


def _set_cached_analysis(key, analysis):
    with _analysis_cache_lock:
        _analysis_cache[key] = (
            time() + ANALYSIS_CACHE_TTL_SECONDS,
            deepcopy(analysis),
        )


def analyze_ticker(ticker: str, period: str = "1y", interval: str = "1d"):
    key = _cache_key(ticker, period, interval)
    cached = _get_cached_analysis(key)

    if cached is not None:
        return cached

    analysis = _analyze_ticker_uncached(key[0], period, interval)
    _set_cached_analysis(key, analysis)

    return deepcopy(analysis)


def analyze_tickers(symbols, period: str = "1y", interval: str = "1d"):
    results = []
    errors = []

    for symbol in symbols:
        clean_symbol = str(symbol).strip().upper()

        if not clean_symbol:
            continue

        try:
            results.append(analyze_ticker(clean_symbol, period, interval))
        except Exception as e:
            errors.append({
                "ticker": clean_symbol,
                "detail": str(e),
            })

    return {
        "period": period,
        "interval": interval,
        "count": len(results),
        "results": results,
        "errors": errors,
    }


def _analyze_ticker_uncached(ticker: str, period: str = "1y", interval: str = "1d"):
    data = get_price_history(ticker, period, interval)
    data = data.dropna(subset=["Open", "High", "Low", "Close"])

    if interval == "1d":
        try:
            intraday = get_price_history(ticker, "1d", "5m")
            intraday = intraday.dropna(subset=["Open", "High", "Low", "Close"])

            if not intraday.empty:
                current_day = intraday.index[-1].normalize()

                data.loc[current_day, "Open"] = safe_float(intraday["Open"].iloc[0], 2)
                data.loc[current_day, "High"] = safe_float(intraday["High"].max(), 2)
                data.loc[current_day, "Low"] = safe_float(intraday["Low"].min(), 2)
                data.loc[current_day, "Close"] = safe_float(intraday["Close"].iloc[-1], 2)
                data.loc[current_day, "Volume"] = int(intraday["Volume"].sum())

                data = data.sort_index()
        except Exception as e:
            print("Intraday daily candle update failed:", e)

    data["SMA_20"] = calculate_sma(data, 20)
    data["SMA_50"] = calculate_sma(data, 50)
    data["RSI"] = calculate_rsi(data)
    data["MACD"], data["MACD_SIGNAL"], data["MACD_HIST"] = calculate_macd(data)

    latest = data.iloc[-1]

    levels = find_support_resistance(data)
    support_zone = levels["support_zone"]
    resistance_zone = levels["resistance_zone"]

    price = safe_float(latest["Close"], 2)
    sma_20 = safe_float(latest["SMA_20"], 2)
    sma_50 = safe_float(latest["SMA_50"], 2)
    rsi = safe_float(latest["RSI"], 2)
    macd = safe_float(latest["MACD"], 4)
    macd_signal = safe_float(latest["MACD_SIGNAL"], 4)
    macd_hist = safe_float(latest["MACD_HIST"], 4)

    current_volume = int(latest["Volume"]) if safe_float(latest["Volume"], 0) is not None else 0
    average_volume = int(data["Volume"].tail(20).mean()) if len(data) >= 20 else current_volume
    rvol = round(current_volume / average_volume, 2) if average_volume > 0 else 0

    if price > sma_20 > sma_50 and rsi < 70:
        trend = "Bullish"
        recommendation = "Possible Long / Watch"
    elif price < sma_20 < sma_50:
        trend = "Bearish"
        recommendation = "Avoid Long / Possible Short Bias"
    elif rsi > 70:
        trend = "Overbought"
        recommendation = "Avoid chasing"
    elif rsi < 30:
        trend = "Oversold"
        recommendation = "Watch for bounce confirmation"
    else:
        trend = "Neutral"
        recommendation = "Neutral / No clear trade"

    chart_data = []

    for date, row in data.iterrows():
        chart_data.append({
            "time": date.strftime("%Y-%m-%d") if interval in ["1d", "1wk", "1mo"] else int(date.timestamp()),
            "open": safe_float(row["Open"], 2),
            "high": safe_float(row["High"], 2),
            "low": safe_float(row["Low"], 2),
            "close": safe_float(row["Close"], 2),
            "volume": int(row["Volume"]) if safe_float(row["Volume"], 0) is not None else 0,
            "sma_20": safe_float(row["SMA_20"], 2),
            "sma_50": safe_float(row["SMA_50"], 2),
            "macd": safe_float(row["MACD"], 4),
            "macd_signal": safe_float(row["MACD_SIGNAL"], 4),
            "macd_hist": safe_float(row["MACD_HIST"], 4),
        })

    trade_thesis = generate_trade_thesis(
        price, sma_20, sma_50, rsi, rvol,
        macd, macd_signal, macd_hist,
        support_zone, resistance_zone
    )

    trade_setup = generate_trade_setup(
    price,
    trend,
    rsi,
    rvol,
    macd,
    macd_signal,
    macd_hist,
    support_zone,
    resistance_zone,
    )

    technical_score = calculate_technical_score(
        price,
        sma_20,
        sma_50,
        rsi,
        rvol,
        macd,
        macd_signal,
        support_zone,
        resistance_zone,
    )

    trade_quality_score = calculate_trade_quality_score(
        price,
        sma_20,
        sma_50,
        rsi,
        rvol,
        macd,
        macd_signal,
        support_zone,
        resistance_zone,
        trade_setup,
    )

    response = {
        "ticker": ticker.upper(),
        "price": price,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "current_volume": current_volume,
        "average_volume": average_volume,
        "rvol": rvol,
        "trend": trend,
        "support_zone": support_zone,
        "resistance_zone": resistance_zone,
        # Deprecated compatibility payload. The dashboard no longer renders a
        # Trade Thesis, but external clients may still rely on this field.
        "trade_thesis": trade_thesis,
        "trade_setup": trade_setup,
        "technical_score": technical_score,
        # Deprecated compatibility alias. technical_score is canonical.
        "trend_score": technical_score,
        "trade_quality_score": trade_quality_score,
        # Deprecated compatibility alias. trade_quality_score is canonical.
        "entry_score": trade_quality_score,
        "recommendation": recommendation,
        "period": period,
        "interval": interval,
        "risk_note": "This is not financial advice. Use position sizing and stop-loss rules.",
        "chart_data": chart_data,
    }

    return clean_for_json(response)
