import Tooltip from "./Tooltip";
import {
  SCORE_COMPONENT_ORDER,
  scoreComponentLabel,
  scoreComponentTooltip,
} from "../utils/scoreComponentConfig";

function ScoreBreakdown({ components, version, scoreLabel }) {
  if (!components || typeof components !== "object" || Array.isArray(components)) return null;

  const entries = Object.entries(components)
    .filter(([, component]) => component && typeof component === "object")
    .map(([key, component]) => {
      const score = Number(component.score);
      const maxScore = Number(component.max_score ?? component.max);
      const scoreAvailable = component.score !== null
        && component.score !== undefined
        && Number.isFinite(score);
      if (!Number.isFinite(maxScore) || maxScore <= 0) return null;

      return {
        key,
        score: scoreAvailable ? score : null,
        maxScore,
        unavailableDisplay: typeof component.unavailable_display === "string"
          ? component.unavailable_display
          : "—",
        percentage: scoreAvailable
          ? Math.max(0, Math.min(100, (score / maxScore) * 100))
          : 0,
        tooltip: scoreComponentTooltip(key),
      };
    })
    .filter(Boolean)
    .sort((left, right) => (
      SCORE_COMPONENT_ORDER.indexOf(left.key) - SCORE_COMPONENT_ORDER.indexOf(right.key)
    ));

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
              <Tooltip label={scoreComponentLabel(entry.key)} content={entry.tooltip} />
              <strong>{entry.score ?? entry.unavailableDisplay} / {entry.maxScore}</strong>
            </div>
            <div
              className="technical-component-track"
              role={entry.score === null ? undefined : "progressbar"}
              aria-label={`${scoreComponentLabel(entry.key)}${entry.score === null ? " score unavailable" : ""}`}
              aria-valuemin={entry.score === null ? undefined : 0}
              aria-valuemax={entry.score === null ? undefined : entry.maxScore}
              aria-valuenow={entry.score ?? undefined}
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
