function ScorePanel({ title, scoreData }) {
  if (!scoreData) return null;

  return (
    <div className="panel-box">
      <div className="panel-header">
        <h3>{title}</h3>
        <span>{scoreData.grade}</span>
      </div>

      <div className="score-value">
        {scoreData.score}/100
      </div>

      <div className="reason-list">
        {scoreData.reasons.map((reason, index) => (
          <p key={index}>• {reason}</p>
        ))}
      </div>
    </div>
  );
}

export default ScorePanel;