function formatCurrency(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) return "N/A";

  return number.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function formatPercent(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) return "0.00%";

  return `${number.toFixed(2)}%`;
}

function getValueClass(value) {
  const number = Number(value);

  if (number > 0) return "positive";
  if (number < 0) return "negative";
  return "neutral";
}

function PortfolioPage({ portfolio, loading, error, onBack, onSelectSymbol }) {
  const positions = portfolio?.positions || [];

  return (
    <main className="portfolio-page">
      <section className="portfolio-card">
        <div className="portfolio-page-header">
          <div>
            <h2>Paper Portfolio</h2>
            <p>Track open paper positions and jump back into analysis.</p>
          </div>

          <button type="button" onClick={onBack}>
            Back to Dashboard
          </button>
        </div>

        {loading && <p className="portfolio-muted">Loading portfolio...</p>}
        {error && <p className="portfolio-error">{error}</p>}

        {!loading && positions.length === 0 && (
          <div className="portfolio-empty">
            <p>No open paper positions yet.</p>
            <button type="button" onClick={onBack}>
              Back to Dashboard
            </button>
          </div>
        )}

        {positions.length > 0 && (
          <div className="portfolio-table-wrap">
            <table className="portfolio-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Shares</th>
                  <th>Avg Cost</th>
                  <th>Current Price</th>
                  <th>Market Value</th>
                  <th>Unrealized P/L</th>
                  <th>Unrealized P/L %</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((position) => (
                  <tr
                    key={position.symbol}
                    onClick={() => onSelectSymbol(position.symbol)}
                  >
                    <td>
                      <strong>{position.symbol}</strong>
                    </td>
                    <td>{position.shares}</td>
                    <td>{formatCurrency(position.avg_cost)}</td>
                    <td>{formatCurrency(position.current_price)}</td>
                    <td>{formatCurrency(position.market_value)}</td>
                    <td className={getValueClass(position.unrealized_pnl)}>
                      {formatCurrency(position.unrealized_pnl)}
                    </td>
                    <td
                      className={getValueClass(
                        position.unrealized_pnl_percent
                      )}
                    >
                      {formatPercent(position.unrealized_pnl_percent)}
                    </td>
                    <td>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelectSymbol(position.symbol);
                        }}
                      >
                        View / Analyze
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

export default PortfolioPage;
