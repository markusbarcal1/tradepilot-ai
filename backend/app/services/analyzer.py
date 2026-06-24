from app.services.market_data import get_price_history
from app.services.indicators import calculate_sma, calculate_rsi, calculate_macd
from copy import deepcopy
import math
from threading import RLock
from time import time

ANALYSIS_CACHE_TTL_SECONDS = 60
_analysis_cache = {}
_analysis_cache_lock = RLock()

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

def calculate_trend_score(price, sma_20, sma_50, rsi, rvol, macd, macd_signal):
    score = 0
    positives = []
    negatives = []

    if price > sma_20:
        score += 18
        positives.append("Price is above the short-term trend line")
    else:
        negatives.append("Price is below the short-term trend line")

    if price > sma_50:
        score += 20
        positives.append("Price is above the intermediate trend line")
    else:
        negatives.append("Price is below the intermediate trend line")

    if sma_20 > sma_50:
        score += 22
        positives.append("Short-term trend remains above the intermediate trend")
    else:
        negatives.append("Short-term trend is below the intermediate trend")

    if macd > macd_signal:
        score += 18
        positives.append("Momentum is improving")
    else:
        negatives.append("Momentum is weakening")

    if 50 <= rsi <= 70:
        score += 15
        positives.append("RSI supports bullish momentum")
    elif rsi > 70:
        score += 8
        positives.append("RSI is strong but extended")
    elif 40 <= rsi < 50:
        score += 5
        positives.append("RSI is neutral but not deeply weak")
    else:
        negatives.append("RSI shows weak momentum")

    if rvol >= 2:
        score += 7
        positives.append("Volume participation is strong")
    elif rvol >= 1:
        score += 5
        positives.append("Volume is above average")
    elif rvol < 0.7:
        negatives.append("Volume participation is light")

    score = max(0, min(score, 100))

    if score >= 80:
        grade = "Strong Bullish"
    elif score >= 60:
        grade = "Bullish"
    elif score >= 40:
        grade = "Neutral"
    elif score >= 20:
        grade = "Bearish"
    else:
        grade = "Strong Bearish"

    return {
        "score": score,
        "grade": grade,
        "positives": positives,
        "negatives": negatives,
    }

def calculate_entry_score(price, rvol, support_zone, resistance_zone, trade_setup):
    score = 0
    positives = []
    negatives = []

    support = support_zone.get("mid") if support_zone else None
    resistance = resistance_zone.get("mid") if resistance_zone else None

    support_strength = support_zone.get("strength") if support_zone else None
    resistance_strength = resistance_zone.get("strength") if resistance_zone else None

    support_distance = support_zone.get("distance_pct") if support_zone else None
    resistance_distance = resistance_zone.get("distance_pct") if resistance_zone else None

    support_touches = support_zone.get("touch_count", 0) if support_zone else 0
    resistance_touches = resistance_zone.get("touch_count", 0) if resistance_zone else 0

    rr = trade_setup.get("risk_reward")

    if isinstance(rr, (int, float)):
        if rr >= 3:
            score += 30
            positives.append(f"Reward/risk profile is excellent at {rr}:1")
        elif rr >= 2:
            score += 22
            positives.append(f"Reward/risk profile is favorable at {rr}:1")
        elif rr >= 1.5:
            score += 14
            positives.append(f"Reward/risk profile is acceptable at {rr}:1")
        else:
            score += 4
            negatives.append(f"Reward/risk profile is limited at {rr}:1")

    if support and price > support and support_distance is not None:
        if support_distance <= 2:
            score += 22
            positives.append(f"Price is sitting close to support ({support_distance}% below)")
        elif support_distance <= 5:
            score += 14
            positives.append(f"Support is within reasonable range ({support_distance}% below)")
        elif support_distance <= 9:
            score += 6
            positives.append(f"Support is nearby but not ideal ({support_distance}% below)")
        else:
            negatives.append(f"Nearest support is far below price ({support_distance}% below)")

        if support_touches > 0:
            positives.append(f"Support has {support_touches} prior touch(es)")

        if support_strength == "Strong":
            score += 12
            positives.append("Support has strong historical confirmation")
        elif support_strength == "Moderate":
            score += 8
            positives.append("Support has moderate historical confirmation")
        elif support_strength == "Weak":
            score += 3
            negatives.append("Support strength is weak")
        elif support_strength == "Very Weak":
            negatives.append("Support has very limited confirmation")

    if resistance and price < resistance and resistance_distance is not None:
        if resistance_distance >= 8:
            score += 20
            positives.append(f"Strong upside room before resistance ({resistance_distance}% above)")
        elif resistance_distance >= 4:
            score += 12
            positives.append(f"Some upside room before resistance ({resistance_distance}% above)")
        elif resistance_distance >= 2:
            score += 5
            positives.append(f"Limited but usable upside room ({resistance_distance}% above)")
        else:
            score -= 8
            negatives.append(f"Price is pressing too close to resistance ({resistance_distance}% above)")

        if resistance_touches > 0:
            negatives.append(f"Resistance has {resistance_touches} prior touch(es)")

        if resistance_strength in ["Weak", "Very Weak"]:
            score += 5
            positives.append("Resistance overhead appears relatively weak")
        elif resistance_strength == "Moderate":
            negatives.append("Resistance has moderate historical confirmation")
        elif resistance_strength == "Strong":
            score -= 5
            negatives.append("Overhead resistance is historically strong")

    if rvol >= 2:
        score += 18
        positives.append("Strong relative volume supports the setup")
    elif rvol >= 1:
        score += 10
        positives.append("Volume is above average")
    elif rvol < 0.7:
        score -= 5
        negatives.append("Weak relative volume reduces setup quality")

    setup_type = trade_setup.get("setup_type")
    setup_bias = trade_setup.get("setup_bias")

    if setup_type != "No Clear Setup":
        score += 10

        if setup_bias == "Bullish":
            positives.append(f"{setup_type} bullish setup detected")
        elif setup_bias == "Bearish":
            negatives.append(f"{setup_type} bearish setup detected")
        else:
            positives.append(f"{setup_type} setup detected")

    score = max(0, min(score, 100))

    if score >= 80:
        grade = "Excellent Entry"
    elif score >= 65:
        grade = "Good Entry"
    elif score >= 50:
        grade = "Average Entry"
    elif score >= 35:
        grade = "Weak Entry"
    else:
        grade = "Poor Entry"

    return {
        "score": score,
        "grade": grade,
        "positives": positives,
        "negatives": negatives,
    }

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

    trend_score = calculate_trend_score(
        price,
        sma_20,
        sma_50,
        rsi,
        rvol,
        macd,
        macd_signal,
    )

    entry_score = calculate_entry_score(
        price,
        rvol,
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
        "trade_thesis": trade_thesis,
        "trade_setup": trade_setup,
        "trend_score": trend_score,
        "entry_score": entry_score,
        "recommendation": recommendation,
        "period": period,
        "interval": interval,
        "risk_note": "This is not financial advice. Use position sizing and stop-loss rules.",
        "chart_data": chart_data,
    }

    return clean_for_json(response)
