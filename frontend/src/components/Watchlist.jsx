import { useState } from "react";
import { getScoreColorClass } from "../utils/scoreColors";

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
  positions = [],
  onSelectStock,
  onAddStock,
  onRemoveStock,
}) {
  const [newStock, setNewStock] = useState("");
  const positionSymbols = new Set(
    positions
      .filter((position) => Number(position.shares) > 0)
      .map((position) => position.symbol?.trim().toUpperCase())
      .filter(Boolean)
  );

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
              <span className="watchlist-symbol">
                {stock}
                {positionSymbols.has(stock.trim().toUpperCase()) && (
                  <span
                    className="watchlist-position-dot"
                    aria-label="Open position"
                    title="Open position"
                  />
                )}
              </span>

              <span className="watchlist-scores">
                <span className="watchlist-timeframe">
                  {getTimeframeAbbreviation(timeframe.label)}
                </span>

                <span className={getScoreColorClass(scores?.technical)}>
                  T:{scores?.technical ?? "--"}
                </span>

                <span className={getScoreColorClass(scores?.quality)}>
                  Q:{scores?.quality ?? "--"}
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
