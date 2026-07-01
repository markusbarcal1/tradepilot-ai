function ScorePanel({ title, scoreData, embedded = false }) {
  if (!scoreData) return null;

  return (
    <div className={embedded ? "analysis-section" : "panel-box"}>
      <div className="panel-header">
        <h3>{title}</h3>
        <span>{scoreData.grade}</span>
      </div>

      <div className="score-value">
        {scoreData.score}/100
      </div>

      <div className="score-reasons">

        {scoreData.positives?.length > 0 && (
          <>
            <div className="score-section-title positive">
              Strengths
            </div>

            {scoreData.positives.map((reason, index) => (
              <div key={index} className="score-reason">
                + {reason}
              </div>
            ))}
          </>
        )}

        {scoreData.negatives?.length > 0 && (
          <>
            <div className="score-section-title negative">
              Weaknesses
            </div>

            {scoreData.negatives.map((reason, index) => (
              <div key={index} className="score-reason">
                - {reason}
              </div>
            ))}
          </>
        )}

      </div>
    </div>
  );
}

export default ScorePanel;
