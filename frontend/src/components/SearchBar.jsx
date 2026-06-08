function SearchBar({ ticker, setTicker, onAnalyze }) {
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
      <button onClick={onAnalyze}>Analyze</button>
    </div>
  );
}

export default SearchBar;