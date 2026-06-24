from app.services.analyzer import analyze_tickers


DEFAULT_UNIVERSE = "test"
DEFAULT_MAX_SYMBOLS = 25
MAX_ALLOWED_SYMBOLS = 100

SP500_UNIVERSE = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A",
    "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL",
    "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG",
    "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO",
    "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG",
    "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR",
    "BALL", "BAC", "BAX", "BDX", "BRK-B", "BBY", "TECH", "BIIB", "BLK",
    "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO",
    "BF-B", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "COF", "CAH",
    "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR",
    "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD",
    "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS",
    "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP",
    "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP",
    "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI",
    "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG",
    "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE",
    "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV",
    "EME", "EMR", "ETR", "EOG", "EQT", "EFX", "EQIX", "EQR", "ERIE",
    "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR",
    "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FDXF", "FIS",
    "FITB", "FSLR", "FE", "FISV", "FLEX", "F", "FTNT", "FTV", "FOXA",
    "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC",
    "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL",
    "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON",
    "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM",
    "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE",
    "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT",
    "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS",
    "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX",
    "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW",
    "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MRVL",
    "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD",
    "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR",
    "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX",
    "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS",
    "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY",
    "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR",
    "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG",
    "PM", "PSX", "PNW", "PNC", "PPG", "PPL", "PFG", "PG", "PGR", "PLD",
    "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL",
    "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD",
    "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC",
    "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA",
    "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK",
    "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP",
    "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX",
    "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN",
    "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS",
    "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT",
    "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS",
    "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM",
    "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH",
    "ZTS",
]

SCAN_UNIVERSES = {
    "test": [
        "AAPL", "MSFT", "NVDA", "AMD", "META",
        "TSLA", "PLTR", "AMZN", "GOOGL", "NFLX",
        "AVGO", "COIN", "MSTR", "SMCI", "CRM"
    ],
    "mega_cap": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
        "META", "BRK-B", "LLY", "AVGO", "JPM",
        "TSLA", "V", "UNH", "XOM", "MA"
    ],
    "tech": [
        "AAPL", "MSFT", "NVDA", "META", "GOOGL",
        "AMZN", "CRM", "ORCL", "ADBE", "NOW",
        "INTU", "PANW", "CRWD", "SNOW", "PLTR"
    ],
    "semiconductors": [
        "NVDA", "AMD", "AVGO", "TSM", "ASML",
        "QCOM", "TXN", "MU", "INTC", "AMAT",
        "LRCX", "KLAC", "ARM", "MRVL", "SMCI"
    ],
    "sp500_sample": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
        "META", "JPM", "UNH", "XOM", "JNJ",
        "PG", "HD", "COST", "BAC", "KO",
        "PEP", "WMT", "DIS", "NFLX", "ADBE",
        "CRM", "MCD", "ABT", "CSCO", "TMO"
    ],
    "sp500": SP500_UNIVERSE,
}

SCAN_UNIVERSE = SCAN_UNIVERSES[DEFAULT_UNIVERSE]


def get_scan_universe(universe: str):
    universe_key = universe.strip().lower()

    if universe_key not in SCAN_UNIVERSES:
        available = ", ".join(sorted(SCAN_UNIVERSES.keys()))
        raise ValueError(f"Unknown scanner universe '{universe}'. Available universes: {available}")

    return universe_key, SCAN_UNIVERSES[universe_key]


def get_safe_max_symbols(max_symbols: int):
    if max_symbols < 1:
        return 1

    return min(max_symbols, MAX_ALLOWED_SYMBOLS)


def scan_market(
    period: str = "1y",
    interval: str = "1d",
    limit: int = 10,
    universe: str = DEFAULT_UNIVERSE,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
):
    results = []
    universe_key, symbols = get_scan_universe(universe)
    safe_max_symbols = get_safe_max_symbols(max_symbols)
    symbols_to_scan = symbols[:safe_max_symbols]
    batch = analyze_tickers(symbols_to_scan, period, interval)

    for error in batch.get("errors", []):
        print(f"Scanner failed for {error['ticker']}: {error['detail']}")

    for analysis in batch.get("results", []):
        try:
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
                "ticker": analysis.get("ticker"),
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
            print(f"Scanner failed for {analysis.get('ticker')}: {e}")

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
        "universe": universe_key,
        "scanned_count": len(symbols_to_scan),
        "max_symbols": safe_max_symbols,
        "mode": "bullish",
        "count": len(results[:limit]),
        "results": results[:limit]
    }
