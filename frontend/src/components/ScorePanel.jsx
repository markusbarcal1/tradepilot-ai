import ScoreBreakdown from "./ScoreBreakdown";
import { getScoreColorClass } from "../utils/scoreColors";

function ScorePanel({ title, scoreData, embedded = false }) {
  if (!scoreData) return null;

  return (
    <div className={embedded ? "analysis-section" : "panel-box"}>
      <div className="panel-header">
        <h3>{title}</h3>
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
    </div>
  );
}

export default ScorePanel;
