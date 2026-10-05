const COMPONENTS = {
  trend: ["Trend", "Measures price alignment with the short-term and intermediate moving averages, including the SMA20 and SMA50."],
  momentum: ["Momentum", "Measures directional strength using RSI, MACD, and MACD signal positioning."],
  participation: ["Participation", "Measures whether relative trading volume supports the current price move."],
  price_structure: ["Price Structure", "Measures the stock's position relative to nearby support and resistance, including the strength and usability of those levels."],
  profitability: ["Profitability", "Measures how effectively the company turns revenue and invested capital into profit."],
  growth: ["Growth", "Measures the direction and consistency of revenue, earnings, and cash-flow growth."],
  financial_health: ["Financial Health", "Measures liquidity, leverage, and the company’s ability to meet financial obligations."],
  cash_flow_quality: ["Cash Flow Quality", "Measures whether reported earnings are supported by actual operating and free cash flow."],
  relative_valuation: ["Relative Valuation", "Measures how attractive current market multiples appear under the selected sector profile."],
  intrinsic_value: ["Intrinsic Value", "Measures how attractive the current price is relative to estimated fair value after confidence, coverage, and model-disagreement adjustments."],
};

export const SCORE_COMPONENT_ORDER = Object.keys(COMPONENTS);

export function scoreComponentLabel(key) {
  return COMPONENTS[key]?.[0]
    ?? key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function scoreComponentTooltip(key) {
  return COMPONENTS[key]?.[1] || `${scoreComponentLabel(key)} score component.`;
}
