function formatCurrency(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) return "N/A";

  return number.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function formatSignedCurrency(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) return "N/A";
  if (number < 0) return `(${formatCurrency(Math.abs(number))})`;

  return formatCurrency(number);
}

function formatPercent(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) return "(0.00%)";

  return `(${number.toFixed(2)}%)`;
}

function getValueClass(value) {
  const number = Number(value);

  if (number > 0) return "positive";
  if (number < 0) return "negative";
  return "neutral";
}

function PaperPortfolioSummary({ portfolio, loading, error }) {
  const cashBalance = portfolio?.cash_balance;
  const accountEquity = portfolio?.account_equity;
  const openPnl = portfolio?.open_pnl || 0;
  const openPnlPercent = portfolio?.open_pnl_percent || 0;
  const dayChange = portfolio?.day_change || 0;
  const dayChangePercent = portfolio?.day_change_percent || 0;
  const openPositions = portfolio?.positions_count || 0;

  return (
    <div className="panel-box paper-summary">
      <div className="paper-summary-header">
        <h3>Paper Portfolio</h3>
        <span>{loading ? "Syncing" : "Live"}</span>
      </div>

      <div className="paper-summary-content">
        <div className="paper-summary-grid">
          <div className="paper-stat-tile">
            <span>Cash</span>
            <strong>{formatCurrency(cashBalance)}</strong>
          </div>
          <div className="paper-stat-tile">
            <span>Account Equity</span>
            <strong>{formatCurrency(accountEquity)}</strong>
          </div>
          <div className="paper-stat-tile">
            <span>Open P/L</span>
            <strong className={getValueClass(openPnl)}>
              {formatSignedCurrency(openPnl)}
            </strong>
            <em className={getValueClass(openPnl)}>{formatPercent(openPnlPercent)}</em>
          </div>
          <div className="paper-stat-tile">
            <span>Day Change</span>
            <strong className={getValueClass(dayChange)}>
              {formatSignedCurrency(dayChange)}
            </strong>
            <em className={getValueClass(dayChange)}>
              {formatPercent(dayChangePercent)}
            </em>
          </div>
          <div className="paper-stat-tile">
            <span>Positions</span>
            <strong>{openPositions}</strong>
          </div>

          <button type="button" className="paper-stat-tile portfolio-placeholder" disabled>
            View Portfolio
          </button>
        </div>
      </div>

      {error && <p className="paper-summary-error">{error}</p>}
    </div>
  );
}

export default PaperPortfolioSummary;
