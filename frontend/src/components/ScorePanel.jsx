import { useId, useState } from "react";
import ExpandedScoreDetails from "./ExpandedScoreDetails";
import ScoreBreakdown from "./ScoreBreakdown";
import { getScoreColorClass } from "../utils/scoreColors";

function ScorePanel({ title, scoreData, embedded = false }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const titleId = useId();
  const hasDetails = Object.values(scoreData?.components ?? {}).some(
    (component) => Array.isArray(component?.details) && component.details.length > 0
  );

  if (!scoreData) return null;

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
      role={hasDetails ? "button" : undefined}
      tabIndex={hasDetails ? 0 : undefined}
      aria-expanded={hasDetails ? expanded : undefined}
      aria-controls={hasDetails ? detailsId : undefined}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
    >
      <div className="panel-header">
        <h3 id={titleId}>{title}</h3>
        <span>{scoreData.grade}</span>
      </div>

      <div className={`score-value ${getScoreColorClass(scoreData.score)}`}>
        {scoreData.score ?? "--"}/100
      </div>

      <ScoreBreakdown
        components={scoreData.components}
        version={scoreData.version}
        scoreLabel={title}
      />

      {hasDetails && (
        <div className={`score-card-details-region ${expanded ? "is-expanded" : ""}`} aria-hidden={!expanded}>
          <ExpandedScoreDetails
            components={scoreData.components}
            scoreLabel={title}
            regionId={detailsId}
            labelledBy={titleId}
          />
        </div>
      )}
    </div>
  );
}

export default ScorePanel;
