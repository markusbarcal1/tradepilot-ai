import { useState } from "react";

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

function Watchlist({
  stocks,
  selectedStock,
  watchlistScores,
  timeframe,
  addingTicker,
  watchlistError,
  onSelectStock,
  onAddStock,
  onRemoveStock,
}) {
  const [newStock, setNewStock] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!newStock.trim()) return;

    onAddStock(newStock);
    setNewStock("");
  };

  return (
    <div className="watchlist-panel">
      <h3>Watchlist</h3>

      <form className="watchlist-add-form" onSubmit={handleSubmit}>
        <input
          value={newStock}
          onChange={(e) => setNewStock(e.target.value.toUpperCase())}
          placeholder="Add ticker"
        />
        <button type="submit" disabled={addingTicker}>
          {addingTicker ? "…" : "+"}
        </button>
      </form>

      {watchlistError && (<p className="watchlist-error">{watchlistError}</p>)}

      <div className="watchlist-list">
        {stocks.map((stock) => {
          const scores = watchlistScores[stock];

          return (
            <div
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

                <button
                  className="watchlist-remove"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveStock(stock);
                  }}
                >
                  ×
                </button>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default Watchlist;