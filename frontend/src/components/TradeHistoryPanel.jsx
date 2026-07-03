function formatCurrency(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) return "N/A";

  return number.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function formatDateTime(value) {
  if (!value) return "N/A";

  const date = new Date(value);

  if (!Number.isNaN(date.getTime())) {
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  return value;
}

function TradeHistoryPanel({ trades = [], loading, error }) {
  return (
    <section className="portfolio-section trade-history-panel">
      <div className="portfolio-section-header">
        <h3>Trade History</h3>
      </div>

      {loading && <p className="portfolio-muted">Loading trade history...</p>}
      {error && <p className="portfolio-error">{error}</p>}

      {!loading && !error && trades.length === 0 && (
        <div className="portfolio-empty compact">
          <p>No trades yet.</p>
        </div>
      )}

      {trades.length > 0 && (
        <div className="portfolio-table-wrap">
          <table className="portfolio-table">
            <thead>
              <tr>
                <th>Date/Time</th>
                <th>Symbol</th>
                <th>Action</th>
                <th>Shares</th>
                <th>Price</th>
                <th>Total Value</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => {
                const action = (trade.side || trade.action || "").toUpperCase();
                const tradeKey =
                  trade.id || `${trade.created_at}-${trade.symbol}-${trade.side}`;

                return (
                  <tr key={tradeKey}>
                    <td>
                      {formatDateTime(trade.timestamp || trade.created_at)}
                    </td>
                    <td>
                      <strong>{trade.symbol}</strong>
                    </td>
                    <td className={`trade-action ${action.toLowerCase()}`}>
                      {action || "N/A"}
                    </td>
                    <td>{trade.shares}</td>
                    <td>{formatCurrency(trade.price)}</td>
                    <td>{formatCurrency(trade.total_value)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default TradeHistoryPanel;
