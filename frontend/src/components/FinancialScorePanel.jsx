import { useEffect, useId, useState } from "react";
import ExpandedScoreDetails from "./ExpandedScoreDetails";
import ScoreBreakdown from "./ScoreBreakdown";
import Tooltip from "./Tooltip";
import { getScoreColorClass } from "../utils/scoreColors";

function normalizeFinancialState(data, loading, error) {
  if (loading) return { kind: "loading" };
  if (error) {
    return {
      kind: "error",
      message: "Financial analysis is temporarily unavailable.",
    };
  }
  if (data == null) {
    return {
      kind: "idle",
      message: "Financial analysis has not been requested.",
    };
  }
  if (typeof data !== "object" || Array.isArray(data)) {
    return {
      kind: "malformed",
      message: "Financial analysis returned an unexpected response.",
    };
  }
  if (data.status === "unavailable") {
    return {
      kind: "unavailable",
      message: typeof data.message === "string"
        ? data.message
        : "Financial analysis is not available for this instrument.",
    };
  }

  const score = Number(data.score);
  const categories = data.categories;
  const coveragePercentage = Number(data.coverage?.percentage);
  const isScoreState = data.status === "available" || data.status === "partial";
  const validCategories = categories
    && typeof categories === "object"
    && !Array.isArray(categories);

  if (
    !isScoreState
    || !Number.isFinite(score)
    || score < 0
    || score > 100
    || !validCategories
    || !Number.isFinite(coveragePercentage)
  ) {
    return {
      kind: "malformed",
      message: "Financial analysis returned an unexpected response.",
    };
  }

  return {
    kind: data.status,
    score,
    label: typeof data.label === "string" ? data.label : "Financial Score",
    categories,
    coveragePercentage: Math.max(0, Math.min(100, coveragePercentage)),
    confidence: typeof data.coverage?.confidence === "string"
      ? data.coverage.confidence
      : "unknown",
    version: data.version,
  };
}

function FinancialScorePanel({ data, loading, error, embedded = false }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const titleId = useId();
  const state = normalizeFinancialState(data, loading, error);
  const displaysScore = state.kind === "available" || state.kind === "partial";
  const hasDetails = displaysScore && Object.values(state.categories).some(
    (category) => Array.isArray(category?.details ?? category?.metrics)
      && (category.details ?? category.metrics).length > 0
  );

  useEffect(() => {
    if (state.kind === "malformed") {
      console.error("Malformed financial-analysis response:", data);
    }
  }, [data, state.kind]);

  const toggle = () => {
    if (hasDetails) setExpanded((current) => !current);
  };

  const handleClick = (event) => {
    if (event.target.closest("button, a, input, select, textarea")) return;
    toggle();
  };

  const handleKeyDown = (event) => {
    if (event.target !== event.currentTarget || !["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    toggle();
  };

  return (
    <div
      className={`${embedded ? "analysis-section" : "panel-box"} ${hasDetails ? "expandable-score-card" : ""}`}
      aria-busy={loading}
      role={hasDetails ? "button" : undefined}
      tabIndex={hasDetails ? 0 : undefined}
      aria-expanded={hasDetails ? expanded : undefined}
      aria-controls={hasDetails ? detailsId : undefined}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
    >
      <div className="panel-header">
        <h3 id={titleId}>Financial Score</h3>
        <span className={state.kind === "partial" ? "partial-data-badge" : ""}>
          {state.kind === "loading"
            ? "Loading"
            : state.kind === "partial"
              ? "Limited Data"
              : displaysScore
                ? state.label
                : "Unavailable"}
        </span>
      </div>

      <div className={`score-value ${getScoreColorClass(displaysScore ? state.score : null)}`}>
        {state.kind === "loading" ? "--" : displaysScore ? state.score : "—"}/100
      </div>

      {state.kind === "loading" && (
        <div className="financial-score-state" role="status">
          Loading financial data…
        </div>
      )}

      {!displaysScore && state.kind !== "loading" && (
        <div className="financial-score-state">{state.message}</div>
      )}

      {displaysScore && (
        <>
          <ScoreBreakdown
            components={state.categories}
            version={state.version}
            scoreLabel="Financial Score"
          />
          <div className="financial-coverage">
            Coverage: {state.coveragePercentage}% · {state.confidence} confidence
            {state.kind === "partial" && (
              <Tooltip
                label=""
                content="Unavailable metrics were excluded and category results were normalized over the available data."
              />
            )}
          </div>
          {hasDetails && (
            <div className={`score-card-details-region ${expanded ? "is-expanded" : ""}`} aria-hidden={!expanded}>
              <ExpandedScoreDetails
                components={state.categories}
                scoreLabel="Financial Score"
                regionId={detailsId}
                labelledBy={titleId}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default FinancialScorePanel;
