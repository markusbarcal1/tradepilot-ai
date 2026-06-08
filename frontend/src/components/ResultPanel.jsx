function ResultPanel({ analysis }) {
  if (!analysis) return null;

  return (
    <div className="panel-box result-panel">
      <p>
        <strong>Trend:</strong> {analysis.trend}
      </p>

      <p>
        <strong>Recommendation:</strong> {analysis.recommendation}
      </p>

      <p className="risk">
        {analysis.risk_note}
      </p>
    </div>
  );
}

export default ResultPanel;