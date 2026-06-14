function ThesisPanel({ tradeThesis }) {
  if (!tradeThesis) return null;

  return (
    <div className="panel-box">
      <div className="panel-header">
        <h3>Trade Thesis</h3>
        <span>{tradeThesis.rating}</span>
      </div>

      <p className="confidence">
        {tradeThesis.evidence_label}: {tradeThesis.evidence_score}%
      </p>

      <h4>Bull Case</h4>
      {tradeThesis.bull_case.length > 0 ? (
        tradeThesis.bull_case.map((item, index) => (
          <p key={index}>+ {item}</p>
        ))
      ) : (
        <p>No major bullish factors detected.</p>
      )}

      <h4>Bear Case</h4>
      {tradeThesis.bear_case.length > 0 ? (
        tradeThesis.bear_case.map((item, index) => (
          <p key={index}>- {item}</p>
        ))
      ) : (
        <p>No major bearish factors detected.</p>
      )}
    </div>
  );
}

export default ThesisPanel;