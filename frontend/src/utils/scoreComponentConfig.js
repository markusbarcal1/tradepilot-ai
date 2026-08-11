const COMPONENTS = {
  trend: ["Trend", "Measures price alignment with the short-term and intermediate moving averages, including the SMA20 and SMA50."],
  momentum: ["Momentum", "Measures directional strength using RSI, MACD, and MACD signal positioning."],
  participation: ["Participation", "Measures whether relative trading volume supports the current price move."],
  price_structure: ["Price Structure", "Measures the stock's position relative to nearby support and resistance, including the strength and usability of those levels."],
  location: ["Location", "Measures how favorable the current price is relative to support, resistance, and the SMA20 and SMA50 for the detected setup."],
  confirmation: ["Confirmation", "Measures whether relative volume, RSI, and MACD signal positioning support the proposed bullish entry."],
  risk_reward: ["Risk / Reward", "Measures planned upside against downside using the entry, stop, target, reward-to-risk ratio, and stop distance."],
  timing: ["Timing", "Measures setup stage and current extension using distance from the SMA20 or SMA50 and RSI."],
  confluence: ["Confluence", "Measures how many independent trade-quality families are aligned without counting individual correlated indicators again."],
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
