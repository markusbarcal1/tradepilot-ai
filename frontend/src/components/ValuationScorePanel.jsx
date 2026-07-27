import { useEffect, useId, useState } from "react";
import ExpandedScoreDetails from "./ExpandedScoreDetails";
import ScoreBreakdown from "./ScoreBreakdown";
import Tooltip from "./Tooltip";
import { getScoreColorClass } from "../utils/scoreColors";

function normalizeValuationState(data, loading, error) {
  if (loading) return { kind: "loading" };
  if (error) return { kind: "error", message: "Valuation analysis is temporarily unavailable." };
  if (data == null) return { kind: "idle", message: "Valuation analysis has not been requested." };
  if (typeof data !== "object" || Array.isArray(data)) {
    return { kind: "malformed", message: "Valuation analysis returned an unexpected response." };
  }
  if (data.status === "unsupported" || data.status === "unavailable") {
    return {
      kind: data.status,
      message: typeof data.message === "string"
        ? data.message
        : "Relative valuation is not available for this instrument.",
    };
  }

  const score = Number(data.score);
  const coveragePercentage = Number(data.coverage?.percentage);
  const categories = data.categories;
  if (
    !Number.isFinite(score)
    || score < 0
    || score > 100
    || !Number.isFinite(coveragePercentage)
    || !categories
    || typeof categories !== "object"
    || Array.isArray(categories)
  ) {
    return { kind: "malformed", message: "Valuation analysis returned an unexpected response." };
  }

  return {
    kind: data.availability === "partial" ? "partial" : "available",
    score,
    label: typeof data.status_label === "string" ? data.status_label : "Relative Valuation",
    categories,
    coveragePercentage: Math.max(0, Math.min(100, coveragePercentage)),
    profileLabel: typeof data.sector_profile_label === "string"
      ? data.sector_profile_label
      : "General Company",
    usedDefaultProfile: data.used_default_profile === true,
    currentPrice: Number.isFinite(Number(data.current_price)) ? Number(data.current_price) : null,
    currency: typeof data.currency === "string" ? data.currency : null,
    version: data.scoring_version,
  };
}

function formatPrice(price, currency) {
  if (!Number.isFinite(price)) return "N/A";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 2,
    }).format(price);
  } catch {
    return `${currency ? `${currency} ` : "$"}${price.toFixed(2)}`;
  }
}

function ValuationScorePanel({ data, loading, error, embedded = false }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const titleId = useId();
  const state = normalizeValuationState(data, loading, error);
  const displaysScore = state.kind === "available" || state.kind === "partial";
  const hasDetails = displaysScore && Object.values(state.categories).some(
    (category) => Array.isArray(category?.details ?? category?.metrics)
      && (category.details ?? category.metrics).length > 0
  );

  useEffect(() => {
    if (state.kind === "malformed") {
      console.error("Malformed valuation-analysis response:", data);
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
        <h3 id={titleId}>Valuation Score</h3>
        <span className={state.kind === "partial" ? "partial-data-badge" : ""}>
          {state.kind === "loading"
            ? "Loading"
            : displaysScore
                ? state.label
                : "Unavailable"}
        </span>
      </div>

      <div className={`score-value ${getScoreColorClass(displaysScore ? state.score : null)}`}>
        {state.kind === "loading" ? "--" : displaysScore ? state.score : "—"}/100
      </div>

      {state.kind === "loading" && (
        <div className="financial-score-state" role="status">Loading valuation data…</div>
      )}
      {!displaysScore && state.kind !== "loading" && (
        <div className="financial-score-state">{state.message}</div>
      )}

      {displaysScore && (
        <>
          <ScoreBreakdown
            components={state.categories}
            version={state.version}
            scoreLabel="Valuation Score"
          />
          <div className="valuation-metadata">
            <span>Coverage: {state.coveragePercentage}%</span>
            <span>Current Price: {formatPrice(state.currentPrice, state.currency)}</span>
            {state.kind === "partial" && (
              <Tooltip
                label=""
                content="Missing supported metrics were excluded from scoring and remain reflected in weighted coverage."
              />
            )}
          </div>
          {hasDetails && (
            <div className={`score-card-details-region ${expanded ? "is-expanded" : ""}`} aria-hidden={!expanded}>
              <ExpandedScoreDetails
                components={state.categories}
                scoreLabel="Valuation Score"
                regionId={detailsId}
                labelledBy={titleId}
                contextLabel={`Scoring Profile: ${state.profileLabel}${state.usedDefaultProfile ? " (default)" : ""}`}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default ValuationScorePanel;
