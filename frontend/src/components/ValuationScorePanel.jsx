import { useEffect, useId, useState } from "react";
import ExpandedScoreDetails from "./ExpandedScoreDetails";
import ScoreBreakdown from "./ScoreBreakdown";
import Tooltip from "./Tooltip";
import { getScoreColorClass } from "../utils/scoreColors";

function normalizeValuationState(data, loading, error) {
  if (loading && data == null) return { kind: "loading" };
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
      currency: typeof data.currency === "string" ? data.currency : null,
      intrinsic: data.intrinsic_value && typeof data.intrinsic_value === "object"
        ? data.intrinsic_value
        : null,
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
    categories: data.intrinsic_value && typeof data.intrinsic_value === "object"
      ? {
          ...categories,
          intrinsic_value: {
            score: Number.isFinite(Number(data.intrinsic_value.score))
              && data.intrinsic_value.score !== null
              ? Number(data.intrinsic_value.score)
              : null,
            max_score: 100,
            unavailable_display: "N/A",
          },
        }
      : categories,
    coveragePercentage: Math.max(0, Math.min(100, coveragePercentage)),
    profileLabel: typeof data.sector_profile_label === "string"
      ? data.sector_profile_label
      : "General Company",
    usedDefaultProfile: data.used_default_profile === true,
    currentPrice: Number.isFinite(Number(data.current_price)) ? Number(data.current_price) : null,
    currency: typeof data.currency === "string" ? data.currency : null,
    version: data.scoring_version,
    refreshing: loading,
    intrinsic: data.intrinsic_value && typeof data.intrinsic_value === "object"
      ? data.intrinsic_value
      : null,
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

function confidenceLabel(value) {
  return typeof value === "string"
    ? `${value.charAt(0).toUpperCase()}${value.slice(1)}`
    : "Low";
}

function formatPercent(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : "N/A";
}

export function IntrinsicValueContent({ intrinsic, currency }) {
  if (!intrinsic) return null;
  const available = intrinsic.status === "available";
  const models = Array.isArray(intrinsic.models) ? intrinsic.models : [];
  const coverage = Math.round(Number(intrinsic.coverage?.weighted_coverage) * 100);
  return (
    <div className="intrinsic-value-content">
      {!available ? (
        <p>{intrinsic.message || "Insufficient data to estimate intrinsic value."}</p>
      ) : (
        <>
          <div className="intrinsic-value-summary">
            <div><span>Estimated Fair Value</span><strong>{formatPrice(Number(intrinsic.fair_value_low), currency)} – {formatPrice(Number(intrinsic.fair_value_high), currency)}</strong></div>
            <div><span>Midpoint</span><strong>{formatPrice(Number(intrinsic.fair_value_mid), currency)}</strong></div>
            <div><span>Current Price</span><strong>{formatPrice(Number(intrinsic.current_price), currency)}</strong></div>
            <div>
              <span>{intrinsic.price_difference_label || "Difference to Midpoint"}</span>
              <strong>{formatPercent(intrinsic.price_difference_percentage)}</strong>
            </div>
            <div><span>Confidence</span><strong>{confidenceLabel(intrinsic.confidence)}</strong></div>
            <div><span>Model Coverage</span><strong>{Number.isFinite(coverage) ? `${coverage}%` : "N/A"}</strong></div>
            <div><span>Status</span><strong>{intrinsic.comparison_label || "N/A"}</strong></div>
          </div>
        </>
      )}
      <div className="intrinsic-model-list">
        {models.map((model) => (
          <div className="intrinsic-model" key={model.model}>
            <div><strong>{model.label}</strong><span>{model.status === "available" ? confidenceLabel(model.confidence) : model.status === "unsupported_for_sector" ? "Unsupported" : "Unavailable"}</span></div>
            {model.status === "available" ? (
              <small>{formatPrice(Number(model.fair_value_low), currency)} – {formatPrice(Number(model.fair_value_high), currency)} · Base {formatPrice(Number(model.fair_value_mid), currency)}</small>
            ) : <small>{model.reason || "Required data unavailable"}</small>}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ValuationExpandedContent({
  categories, titleId, profileLabel, usedDefaultProfile, intrinsic, currency,
}) {
  return (
    <div className="valuation-expanded-content">
      <ExpandedScoreDetails
        components={categories}
        scoreLabel="Valuation Score"
        labelledBy={titleId}
        contextLabel={`Scoring Profile: ${profileLabel}${usedDefaultProfile ? " (default)" : ""}`}
      />
      {intrinsic && (
        <section className="score-detail-category intrinsic-value-detail-section">
          <div className="score-detail-category-heading">
            <strong>Intrinsic Value</strong>
            <span>{Number.isFinite(Number(intrinsic.score)) && intrinsic.score !== null
              ? `${Number(intrinsic.score)} / 100`
              : "N/A"}</span>
          </div>
          <IntrinsicValueContent intrinsic={intrinsic} currency={currency} />
        </section>
      )}
    </div>
  );
}

function ValuationScorePanel({ data, loading, error, embedded = false, symbol }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const titleId = useId();
  const matchesActiveSymbol = !symbol
    || typeof data?.symbol !== "string"
    || data.symbol.toUpperCase() === symbol.toUpperCase();
  const visibleData = matchesActiveSymbol ? data : null;
  const state = normalizeValuationState(visibleData, loading, error);
  const displaysScore = state.kind === "available" || state.kind === "partial";
  const hasDetails = displaysScore && Object.values(state.categories).some(
    (category) => Array.isArray(category?.details ?? category?.metrics)
      && (category.details ?? category.metrics).length > 0
  );

  useEffect(() => {
    if (state.kind === "malformed") {
      console.error("Malformed valuation-analysis response:", visibleData);
    }
  }, [visibleData, state.kind]);

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
          <div className="financial-coverage valuation-coverage">
            Coverage: {state.coveragePercentage}% · Current Price: {formatPrice(state.currentPrice, state.currency)}
            {state.kind === "partial" && (
              <Tooltip
                label=""
                content="Missing supported metrics were excluded from scoring and remain reflected in weighted coverage."
              />
            )}
          </div>
          {state.refreshing && <div className="valuation-refreshing" role="status">Refreshing valuation…</div>}
          {hasDetails && (
            <div className={`score-card-details-region ${expanded ? "is-expanded" : ""}`} aria-hidden={!expanded}>
              <div className="valuation-expanded-region" id={detailsId} role="region" aria-labelledby={titleId}>
                <ValuationExpandedContent
                  categories={state.categories}
                  titleId={titleId}
                  profileLabel={state.profileLabel}
                  usedDefaultProfile={state.usedDefaultProfile}
                  intrinsic={state.intrinsic}
                  currency={state.currency}
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default ValuationScorePanel;
