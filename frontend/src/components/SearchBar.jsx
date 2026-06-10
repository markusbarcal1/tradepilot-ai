function SearchBar({ ticker, setTicker, onAnalyze, loading }) {
  return (
    <div className="search-box">
      <input
        value={ticker}
        onChange={(e) => setTicker(e.target.value.toUpperCase())}
        placeholder="Enter ticker, e.g. AAPL"
        onKeyDown={(e) => {
          if (e.key === "Enter") onAnalyze();
        }}
      />

      <button onClick={onAnalyze} disabled={loading}>
        {loading ? <span className="button-spinner"></span> : "Analyze"}
      </button>
    </div>
  );
}

export default SearchBar;