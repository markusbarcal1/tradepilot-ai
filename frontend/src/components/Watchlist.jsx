function getScoreClass(score) {
  if (score === undefined || score === null) return "score-empty";
  if (score >= 80) return "score-strong";
  if (score >= 60) return "score-good";
  if (score >= 40) return "score-neutral";
  return "score-weak";
}

function getTimeframeAbbreviation(label) {
  switch (label) {
    case "Monthly":
      return "M";
    case "Weekly":
      return "W";
    case "Daily":
      return "D";
    case "1h":
      return "1H";
    case "30m":
      return "30M";
    case "5m":
      return "5M";
    case "1m":
      return "1M";
    default:
      return label;
  }
}

function Watchlist({ stocks, selectedStock, watchlistScores, timeframe, onSelectStock }) {
  return (
    <div className="watchlist-panel">
      <h3>Watchlist</h3>

      <div className="watchlist-list">
        {stocks.map((stock) => {
          const scores = watchlistScores[stock];

          return (
            <button
              key={stock}
              className={
                selectedStock === stock
                  ? "watchlist-row active"
                  : "watchlist-row"
              }
              onClick={() => onSelectStock(stock)}
            >
              <span>{stock}</span>

              <span className="watchlist-scores">
                <span className="watchlist-timeframe">
                  {getTimeframeAbbreviation(timeframe.label)}
                </span>

                <span className={getScoreClass(scores?.trend)}>
                  T:{scores?.trend ?? "--"}
                </span>

                <span className={getScoreClass(scores?.entry)}>
                  E:{scores?.entry ?? "--"}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default Watchlist;