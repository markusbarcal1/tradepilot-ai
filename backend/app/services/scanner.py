from app.services.analyzer import analyze_ticker


SCAN_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMD", "META",
    "TSLA", "PLTR", "AMZN", "GOOGL", "NFLX",
    "AVGO", "COIN", "MSTR", "SMCI", "CRM"
]


def scan_market(period: str = "1y", interval: str = "1d", limit: int = 10):
    results = []

    for symbol in SCAN_UNIVERSE:
        try:
            analysis = analyze_ticker(symbol, period, interval)

            entry_score_data = analysis.get("entry_score", {})
            trend_score_data = analysis.get("trend_score", {})
            trade_setup = analysis.get("trade_setup", {})
            trade_thesis = analysis.get("trade_thesis", {})

            entry_score = entry_score_data.get("score", 0)
            trend_score = trend_score_data.get("score", 0)

            setup_type = trade_setup.get("setup_type")
            setup_bias = trade_setup.get("setup_bias")
            setup_quality = trade_setup.get("quality")

            # Scanner v1: bullish long setups only
            if setup_bias != "Bullish":
                continue

            if setup_type == "No Clear Setup":
                continue

            if setup_quality == "Unfavorable":
                continue

            results.append({
                "ticker": analysis.get("ticker", symbol),
                "price": analysis.get("price"),

                "entry_score": entry_score,
                "entry_grade": entry_score_data.get("grade"),
                "trend_score": trend_score,
                "trend_grade": trend_score_data.get("grade"),

                "setup_type": setup_type,
                "setup_bias": setup_bias,
                "setup_quality": setup_quality,

                "entry": trade_setup.get("entry"),
                "stop": trade_setup.get("stop"),
                "target": trade_setup.get("target"),
                "risk_reward": trade_setup.get("risk_reward"),
                "risk_pct": trade_setup.get("risk_pct"),
                "reward_pct": trade_setup.get("reward_pct"),

                "rsi": analysis.get("rsi"),
                "rvol": analysis.get("rvol"),

                "support": trade_thesis.get("support"),
                "resistance": trade_thesis.get("resistance"),

                "notes": trade_setup.get("notes", []),
            })

        except Exception as e:
            print(f"Scanner failed for {symbol}: {e}")

    results.sort(
        key=lambda stock: (
            stock["entry_score"],
            stock["trend_score"]
        ),
        reverse=True
    )

    return {
        "period": period,
        "interval": interval,
        "mode": "bullish",
        "count": len(results[:limit]),
        "results": results[:limit]
    }