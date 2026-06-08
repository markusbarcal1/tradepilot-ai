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
    <aside className="left-panel">
      <h2>{analysis.ticker}</h2>

      <div className="metrics-grid">
        <Metric label="Price" value={`$${analysis.price}`} />
        <Metric label="20 SMA" value={analysis.sma_20} />
        <Metric label="50 SMA" value={analysis.sma_50} />
        <Metric label="RSI" value={analysis.rsi} />
        <Metric
          label="Volume"
          value={analysis.current_volume?.toLocaleString()}
        />
        <Metric
          label="Avg Volume"
          value={analysis.average_volume?.toLocaleString()}
        />
        <Metric label="RVOL" value={`${analysis.rvol}x`} />
        <Metric label="MACD" value={analysis.macd} />
        <Metric label="Signal" value={analysis.macd_signal} />

        <Metric
          label="Hist"
          value={analysis.macd_hist}
          className={
            analysis.macd_hist >= 0 ? "positive" : "negative"
          }
        />

        <Metric
          label="Support"
          value={
            analysis.support_zone
              ? analysis.support_zone.display
              : "N/A"
          }
        />

        <Metric
          label="Resistance"
          value={
            analysis.resistance_zone
              ? analysis.resistance_zone.display
              : "N/A"
          }
        />
      </div>
    </aside>
  );
}

export default MetricsPanel;