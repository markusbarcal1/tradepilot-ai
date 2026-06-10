function Watchlist({ stocks, selectedStock, watchlistScores, onSelectStock }) {
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
                T:{scores?.trend ?? "--"} E:{scores?.entry ?? "--"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default Watchlist;