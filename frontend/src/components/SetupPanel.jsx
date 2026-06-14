function MiniStat({ label, value }) {
  return (
    <div className="mini-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SetupPanel({ tradeSetup }) {
  if (!tradeSetup) return null;

  return (
    <div className="panel-box">
      <div className="panel-header">
        <h3>Trade Setup</h3>
        <span>{tradeSetup.quality} Quality</span>
      </div>

      <h4 className="setup-title">
        {tradeSetup.setup_type}
      </h4>

      <div className="setup-mini-grid">
        <MiniStat
          label="Entry"
          value={tradeSetup.entry ? `$${tradeSetup.entry}` : "N/A"}
        />

        <MiniStat
          label="Stop"
          value={tradeSetup.stop ? `$${tradeSetup.stop}` : "N/A"}
        />

        <MiniStat
          label="Risk"
          value={tradeSetup.risk_pct ? `${tradeSetup.risk_pct}%` : "N/A"}
        />

        <MiniStat
          label="Target"
          value={tradeSetup.target ? `$${tradeSetup.target}` : "N/A"}
        />

        <MiniStat
          label="Reward"
          value={tradeSetup.reward_pct ? `${tradeSetup.reward_pct}%` : "N/A"}
        />

        <MiniStat
          label="R/R"
          value={tradeSetup.risk_reward}
        />
      </div>

      <div className="reason-list">
        {tradeSetup.notes.map((note, index) => (
          <p key={index}>• {note}</p>
        ))}
      </div>
    </div>
  );
}

export default SetupPanel;