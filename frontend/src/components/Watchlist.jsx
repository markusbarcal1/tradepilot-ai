function Watchlist({ stocks, selectedStock, onSelectStock }) {
  return (
    <div className="watchlist-panel">
      <h3>Watchlist</h3>

      <div className="watchlist-list">
        {stocks.map((stock) => (
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
          </button>
        ))}
      </div>
    </div>
  );
}

export default Watchlist;