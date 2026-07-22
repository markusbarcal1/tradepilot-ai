import Tooltip from "./Tooltip";

const COMPONENTS = {
  trend: {
    label: "Trend",
    description: "Measures price alignment with the short-term and intermediate moving averages, including the SMA20 and SMA50.",
  },
  momentum: {
    label: "Momentum",
    description: "Measures directional strength using RSI, MACD, and MACD signal positioning.",
  },
  participation: {
    label: "Participation",
    description: "Measures whether relative trading volume supports the current price move.",
  },
  price_structure: {
    label: "Price Structure",
    description: "Measures the stock's position relative to nearby support and resistance, including the strength and usability of those levels.",
  },
  location: {
    label: "Location",
    description: "Measures how favorable the current price is relative to support, resistance, and the SMA20 and SMA50 for the detected setup.",
  },
  confirmation: {
    label: "Confirmation",
    description: "Measures whether relative volume, RSI, and MACD signal positioning support the proposed bullish entry.",
  },
  risk_reward: {
    label: "Risk / Reward",
    description: "Measures planned upside against downside using the entry, stop, target, reward-to-risk ratio, and stop distance.",
  },
  timing: {
    label: "Timing",
    description: "Measures setup stage and current extension using distance from the SMA20 or SMA50 and RSI.",
  },
  confluence: {
    label: "Confluence",
    description: "Measures how many independent trade-quality families are aligned without counting individual correlated indicators again.",
  },
};

const PREFERRED_ORDER = [
  "trend",
  "momentum",
  "participation",
  "price_structure",
  "location",
  "confirmation",
  "risk_reward",
  "timing",
  "confluence",
];

function componentLabel(key) {
  return COMPONENTS[key]?.label
    ?? key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function ScoreBreakdown({ components, version, scoreLabel }) {
  if (!components || typeof components !== "object") return null;

  const entries = Object.entries(components)
    .filter(([, component]) => component && typeof component === "object")
    .map(([key, component]) => {
      const score = Number(component.score);
      const maxScore = Number(component.max_score ?? component.max);
      if (!Number.isFinite(score) || !Number.isFinite(maxScore) || maxScore <= 0) return null;

      return {
        key,
        score,
        maxScore,
        percentage: Math.max(0, Math.min(100, (score / maxScore) * 100)),
        tooltip: COMPONENTS[key]?.description || `${componentLabel(key)} score component.`,
      };
    })
    .filter(Boolean)
    .sort((left, right) => PREFERRED_ORDER.indexOf(left.key) - PREFERRED_ORDER.indexOf(right.key));

  if (entries.length === 0) return null;

  return (
    <div className="technical-breakdown" aria-label={`${scoreLabel} breakdown`}>
      <div className="technical-breakdown-header">
        <span>Score breakdown</span>
        {version && <span className="technical-score-version">v{version}</span>}
      </div>

      <div className="technical-component-list">
        {entries.map((entry) => (
          <div className="technical-component" key={entry.key}>
            <div className="technical-component-meta">
              <Tooltip label={componentLabel(entry.key)} content={entry.tooltip} />
              <strong>{entry.score} / {entry.maxScore}</strong>
            </div>
            <div
              className="technical-component-track"
              role="progressbar"
              aria-label={componentLabel(entry.key)}
              aria-valuemin="0"
              aria-valuemax={entry.maxScore}
              aria-valuenow={entry.score}
            >
              <span style={{ width: `${entry.percentage}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ScoreBreakdown;
