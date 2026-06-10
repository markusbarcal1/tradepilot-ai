from app.services.market_data import get_price_history
from app.services.indicators import calculate_sma, calculate_rsi, calculate_macd
import math

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
        bull_case.append("Price is above the 20 SMA.")
        score += 8
    else:
        bear_case.append("Price is below the 20 SMA.")
        score -= 8

    if price > sma_50:
        bull_case.append("Price is above the 50 SMA.")
        score += 8
    else:
        bear_case.append("Price is below the 50 SMA.")
        score -= 8

    if sma_20 > sma_50:
        bull_case.append("20 SMA is above the 50 SMA, showing positive trend structure.")
        score += 8
    else:
        bear_case.append("20 SMA is below the 50 SMA, showing weaker trend structure.")
        score -= 8

    if macd > macd_signal and macd_hist > 0:
        bull_case.append("MACD is above the signal line with positive histogram momentum.")
        score += 10
    elif macd < macd_signal and macd_hist < 0:
        bear_case.append("MACD is below the signal line with negative histogram momentum.")
        score -= 10

    if rvol >= 2:
        bull_case.append("Relative volume is elevated, suggesting strong participation.")
        score += 8
    elif rvol < 0.8:
        bear_case.append("Relative volume is weak, suggesting limited participation.")
        score -= 5

    if rsi >= 70:
        bear_case.append("RSI is overbought, increasing short-term pullback risk.")
        score -= 8
    elif 50 <= rsi < 70:
        bull_case.append("RSI is in a healthy bullish momentum range.")
        score += 5
    elif rsi < 30:
        bear_case.append("RSI is oversold, signaling weakness but possible bounce risk.")
        score -= 5

    if support_zone and support_zone.get("mid"):
        support_strength = support_zone.get("strength", "Unknown")
        support_touches = support_zone.get("touch_count", 0)
        support_distance = support_zone.get("distance_pct")

        if support_distance is not None:
            if support_distance <= 3:
                bull_case.append(
                    f"Price is near {support_strength.lower()} support with {support_touches} prior touch(es)."
                )
                score += 8
            elif support_distance <= 7:
                bull_case.append(
                    f"Support is within {support_distance}% below price, providing a nearby risk reference."
                )
                score += 4
            else:
                bear_case.append(
                    f"Nearest support is {support_distance}% below price, leaving wider downside risk."
                )
                score -= 3

    if resistance_zone and resistance_zone.get("mid"):
        resistance_strength = resistance_zone.get("strength", "Unknown")
        resistance_touches = resistance_zone.get("touch_count", 0)
        resistance_distance = resistance_zone.get("distance_pct")

        if resistance_distance is not None:
            if resistance_distance <= 3:
                bear_case.append(
                    f"Price is close to {resistance_strength.lower()} resistance with {resistance_touches} prior touch(es)."
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
    elif score >= 60:
        thesis_rating = "Bullish"
    elif score >= 45:
        thesis_rating = "Neutral"
    elif score >= 30:
        thesis_rating = "Bearish"
    else:
        thesis_rating = "Strong Bearish"

    return {
        "rating": thesis_rating,
        "confidence": score,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "support": support_text,
        "resistance": resistance_text,
        "risk_reward": risk_reward,
    }

def calculate_trend_score(price, sma_20, sma_50, rsi, rvol, macd, macd_signal):
    score = 0
    reasons = []

    if price > sma_20:
        score += 20
        reasons.append("Price above 20 SMA")

    if price > sma_50:
        score += 20
        reasons.append("Price above 50 SMA")

    if sma_20 > sma_50:
        score += 20
        reasons.append("20 SMA above 50 SMA")

    if macd > macd_signal:
        score += 20
        reasons.append("MACD bullish")

    if 50 <= rsi <= 70:
        score += 15
        reasons.append("RSI in bullish momentum range")
    elif rsi > 70:
        score += 8
        reasons.append("RSI strong but extended")

    if rvol >= 1:
        score += 5
        reasons.append("Volume above average")

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
        "reasons": reasons,
    }

def calculate_entry_score(price, rvol, support_zone, resistance_zone, trade_setup):
    score = 0
    reasons = []

    support = support_zone["mid"] if support_zone and support_zone.get("mid") else None
    resistance = resistance_zone["mid"] if resistance_zone and resistance_zone.get("mid") else None

    rr = trade_setup.get("risk_reward")

    if isinstance(rr, (int, float)):
        if rr >= 3:
            score += 35
            reasons.append("Excellent risk/reward")
        elif rr >= 2:
            score += 25
            reasons.append("Good risk/reward")
        elif rr >= 1.5:
            score += 15
            reasons.append("Acceptable risk/reward")
        else:
            reasons.append("Weak risk/reward")

    if support and price > support:
        distance_to_support = (price - support) / price

        if distance_to_support <= 0.02:
            score += 20
            reasons.append("Entry is close to support")
        elif distance_to_support <= 0.05:
            score += 10
            reasons.append("Entry is reasonably near support")

    if resistance and price < resistance:
        distance_to_resistance = (resistance - price) / price

        if distance_to_resistance >= 0.05:
            score += 20
            reasons.append("Strong upside room to resistance")
        elif distance_to_resistance >= 0.02:
            score += 10
            reasons.append("Some upside room to resistance")

    if rvol >= 2:
        score += 20
        reasons.append("Strong relative volume")
    elif rvol >= 1:
        score += 10
        reasons.append("Above average volume")

    if trade_setup.get("setup_type") != "No Clear Setup":
        score += 10
        reasons.append(f"{trade_setup.get('setup_type')} detected")

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
        "reasons": reasons,
    }

def generate_trade_setup(price, trend, rsi, rvol, macd, macd_signal, macd_hist, support_zone, resistance_zone):
    setup_type = "No Clear Setup"
    entry = None
    stop = None
    target = None
    risk_reward = "N/A"
    quality = "Low"
    notes = []

    support = support_zone["mid"] if support_zone and support_zone.get("mid") else None
    resistance = resistance_zone["mid"] if resistance_zone and resistance_zone.get("mid") else None

    bullish_momentum = macd > macd_signal and macd_hist > 0
    bearish_momentum = macd < macd_signal and macd_hist < 0

    above_support = support is not None and price > support
    below_resistance = resistance is not None and price < resistance

    near_resistance = (
        resistance is not None and price < resistance and ((resistance - price) / price) <= 0.03
    )

    near_support = (
        support is not None and price > support and ((price - support) / price) <= 0.03
    )

    # 1. Breakout Watch
    if resistance and below_resistance and bullish_momentum and near_resistance:
        setup_type = "Breakout Watch"
        entry = round(resistance + (price * 0.002), 2)
        stop = round(support if support else price * 0.97, 2)
        target = round(entry + ((entry - stop) * 2), 2)

        notes.append("Price is near resistance with bullish momentum.")
        notes.append("Potential setup is a breakout above resistance.")

    # 2. Pullback Bounce
    elif support and above_support and near_support and bullish_momentum and rsi < 70:
        setup_type = "Pullback Bounce"
        entry = round(price, 2)
        stop = round(support * 0.985, 2)

        if resistance and resistance > price:
            target = round(resistance, 2)
        else:
            target = round(price + ((price - stop) * 2), 2)

        notes.append("Price is holding near support with bullish momentum.")
        notes.append("Potential setup is a bounce from support.")

    # 3. Momentum Long
    elif price > 0 and bullish_momentum and rsi >= 50 and rsi < 75:
        setup_type = "Momentum Long"
        entry = round(price, 2)

        if support and support < price:
            stop = round(support, 2)
        else:
            stop = round(price * 0.97, 2)

        if resistance and resistance > price:
            target = round(resistance, 2)
        else:
            target = round(price + ((price - stop) * 2), 2)

        notes.append("Bullish momentum is present.")
        notes.append("RSI supports continuation without being extremely overbought.")

        if rvol >= 1:
            notes.append("Volume is confirming the move.")

    # 4. Breakdown Risk
    elif support and price < support and bearish_momentum:
        setup_type = "Breakdown Risk"
        entry = round(price, 2)
        stop = round(support, 2)
        target = round(price - ((stop - price) * 2), 2)

        notes.append("Price is below support with bearish momentum.")
        notes.append("Potential downside continuation risk.")

    # 5. Momentum Short
    elif bearish_momentum and rsi < 50:
        setup_type = "Momentum Short"
        entry = round(price, 2)

        if resistance and resistance > price:
            stop = round(resistance, 2)
        else:
            stop = round(price * 1.03, 2)

        if support and support < price:
            target = round(support, 2)
        else:
            target = round(price - ((stop - price) * 2), 2)

        notes.append("Bearish momentum is present.")
        notes.append("RSI is below 50, showing weaker momentum.")

        if rvol >= 1:
            notes.append("Volume is confirming the move.")

    else:
        notes.append("No clean entry setup detected from current technical conditions.")

    if entry and stop and target:
        risk = abs(entry - stop)
        reward = abs(target - entry)

        if risk > 0:
            rr = round(reward / risk, 2)
            risk_reward = rr

            if rr >= 2:
                quality = "High"
            elif rr >= 1.5:
                quality = "Medium"
            else:
                quality = "Low"

            if rvol < 0.8 and quality == "High":
                quality = "Medium"

            if rvol < 0.6 and quality == "Medium":
                quality = "Low"

    return {
        "setup_type": setup_type,
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": risk_reward,
        "quality": quality,
        "notes": notes,
    }

def analyze_ticker(ticker: str, period: str = "1y", interval: str = "1d"):
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