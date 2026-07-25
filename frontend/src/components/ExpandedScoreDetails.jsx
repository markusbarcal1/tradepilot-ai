import { normalizeScoreDetails } from "../utils/scoreDetails";
import {
  SCORE_COMPONENT_ORDER,
  scoreComponentLabel,
} from "../utils/scoreComponentConfig";

function ExpandedScoreDetails({ components, scoreLabel, regionId, labelledBy }) {
  if (!components || typeof components !== "object" || Array.isArray(components)) return null;

  const categories = Object.entries(components)
    .filter(([, component]) => component && typeof component === "object")
    .map(([key, component]) => {
      const maxScore = Number(component.max_score ?? component.max);
      const numericScore = Number(component.score);
      const score = component.score !== null
        && component.score !== undefined
        && Number.isFinite(numericScore)
        ? numericScore
        : null;

      return {
        key,
        label: scoreComponentLabel(key),
        score,
        maxScore: Number.isFinite(maxScore) ? maxScore : null,
        details: normalizeScoreDetails(component),
        note: typeof component.normalization_note === "string"
          ? component.normalization_note
          : "",
      };
    })
    .filter((category) => category.details.length > 0)
    .sort((left, right) => (
      SCORE_COMPONENT_ORDER.indexOf(left.key) - SCORE_COMPONENT_ORDER.indexOf(right.key)
    ));

  if (categories.length === 0) return null;

  return (
    <div
      className="expanded-score-details"
      id={regionId}
      role="region"
      aria-label={`${scoreLabel} detailed metrics`}
      aria-labelledby={labelledBy}
    >
      <div className="expanded-score-details-inner">
        <div className="expanded-score-details-title">Detailed metrics</div>
        {categories.map((category) => (
          <section className="score-detail-category" key={category.key}>
            <div className="score-detail-category-heading">
              <strong>{category.label}</strong>
              <span>{category.score ?? "—"} / {category.maxScore ?? "—"}</span>
            </div>

            <div className="score-detail-list">
              {category.details.map((detail) => (
                <div
                  className={`score-detail-item ${detail.available ? "" : "is-unavailable"}`}
                  key={detail.key}
                >
                  <div className="score-detail-heading">
                    <strong>{detail.label}</strong>
                    <span className="score-detail-value">{detail.displayValue}</span>
                  </div>
                  <div className="score-detail-meta">
                    <span className={`score-detail-status status-${String(detail.status || "available").replaceAll("_", "-")}`}>
                      {detail.displayStatus}
                    </span>
                    {detail.available
                      && Number.isFinite(Number(detail.score))
                      && Number.isFinite(Number(detail.max_score)) ? (
                        <span>Contribution: {Number(detail.score)} / {Number(detail.max_score)}</span>
                      ) : (
                        <span>Excluded from score</span>
                      )}
                  </div>
                  {typeof detail.explanation === "string" && detail.explanation && (
                    <p>{detail.explanation}</p>
                  )}
                  {typeof detail.reference === "string"
                    && detail.reference
                    && detail.available && <small>{detail.reference}</small>}
                </div>
              ))}
            </div>

            {category.note && <p className="score-normalization-note">{category.note}</p>}
          </section>
        ))}
      </div>
    </div>
  );
}

export default ExpandedScoreDetails;
