function Metric({ label, value, className = "" }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong className={className}>{value}</strong>
    </div>
  );
}

function MetricsPanel({ analysis }) {
  return (
    <div className="left-panel">
      <h2>{analysis.ticker}</h2>

      <div className="metrics-list">
        <div className="metric-row">
          <span>Price</span>
          <strong>${analysis.price}</strong>
        </div>
        <div className="metric-row">
          <span>Support</span>
          <strong>{analysis.support_zone?.display || "N/A"}</strong>
        </div>

        <div className="metric-row">
          <span>Resistance</span>
          <strong>{analysis.resistance_zone?.display || "N/A"}</strong>
        </div>

        <div className="metric-row">
          <span>20 SMA</span>
          <strong>{analysis.sma_20}</strong>
        </div>

        <div className="metric-row">
          <span>50 SMA</span>
          <strong>{analysis.sma_50}</strong>
        </div>

        <div className="metric-row">
          <span>RSI</span>
          <strong>{analysis.rsi}</strong>
        </div>

        <div className="metric-row">
          <span>MACD</span>
          <strong>{analysis.macd}</strong>
        </div>

        <div className="metric-row">
          <span>Signal</span>
          <strong>{analysis.macd_signal}</strong>
        </div>

        <div className="metric-row">
          <span>Hist</span>
          <strong className={analysis.macd_hist >= 0 ? "positive" : "negative"}>
            {analysis.macd_hist}
          </strong>
        </div>

        <div className="metric-row">
          <span>Volume</span>
          <strong>{analysis.current_volume?.toLocaleString()}</strong>
        </div>

        <div className="metric-row">
          <span>Avg Volume</span>
          <strong>{analysis.average_volume?.toLocaleString()}</strong>
        </div>

        <div className="metric-row">
          <span>RVOL</span>
          <strong>{analysis.rvol}x</strong>
        </div>
      </div>
    </div>
  );
}

export default MetricsPanel;