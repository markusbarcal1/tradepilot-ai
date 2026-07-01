function SetupMetric({ label, value }) {
  return (
    <div className="setup-metric-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SetupPanel({ tradeSetup }) {
  if (!tradeSetup) return null;

  const setupNotes = tradeSetup.notes || [];
  const setupMetrics = [
    {
      label: "Entry",
      value: tradeSetup.entry ? `$${tradeSetup.entry}` : "N/A",
    },
    {
      label: "Risk",
      value: tradeSetup.risk_pct ? `${tradeSetup.risk_pct}%` : "N/A",
    },
    {
      label: "Stop",
      value: tradeSetup.stop ? `$${tradeSetup.stop}` : "N/A",
    },
    {
      label: "Reward",
      value: tradeSetup.reward_pct ? `${tradeSetup.reward_pct}%` : "N/A",
    },
    {
      label: "Target",
      value: tradeSetup.target ? `$${tradeSetup.target}` : "N/A",
    },
    {
      label: "R/R",
      value: tradeSetup.risk_reward,
    },
  ];

  return (
    <div className="panel-box">
      <div className="panel-header">
        <h3>Trade Setup</h3>
        <span>{tradeSetup.quality} Quality</span>
      </div>

      <h4 className="setup-title">
        {tradeSetup.setup_type}
      </h4>

      <div className="setup-metrics-compact">
        <div>
          {setupMetrics
            .filter((_, index) => index % 2 === 0)
            .map((metric) => (
            <SetupMetric
              key={metric.label}
              label={metric.label}
              value={metric.value}
            />
          ))}
        </div>

        <div>
          {setupMetrics
            .filter((_, index) => index % 2 === 1)
            .map((metric) => (
            <SetupMetric
              key={metric.label}
              label={metric.label}
              value={metric.value}
            />
          ))}
        </div>
      </div>

      {setupNotes.length > 0 && (
        <div className="setup-notes">
          <div className="setup-notes-title">Notes</div>

          {setupNotes.map((note, index) => (
            <p key={index}>
              <span>•</span>
              {note}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export default SetupPanel;
