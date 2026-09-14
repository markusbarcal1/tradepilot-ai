import SearchBar from "./SearchBar";

function Header({
  ticker,
  setTicker,
  onAnalyze,
  loading,
  currentView,
  onNavigate,
  userEmail,
  onSignOut,
  theme,
  onToggleTheme,
}) {
  return (
    <header className="top-bar">
      <div className="brand-column">
        <button
          type="button"
          className="brand-link"
          onClick={() => onNavigate("dashboard")}
          aria-label="Go to Dashboard"
        >
          <h1>TradePilot AI</h1>
        </button>
      </div>

      <SearchBar
        ticker={ticker}
        setTicker={setTicker}
        onAnalyze={onAnalyze}
        loading={loading}
      />

      <nav className="top-nav" aria-label="Primary navigation">
        {["Dashboard", "Watchlist", "Scanner", "Portfolio"].map((item) => {
          const view = item.toLowerCase();
          const isActive = currentView === view;

          return (
            <button
              key={item}
              type="button"
              className={isActive ? "active" : ""}
              onClick={() => onNavigate(view)}
            >
              {item}
            </button>
          );
        })}

        <button
          type="button"
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
        <div className="auth-user-controls">
          {userEmail && <span title={userEmail}>{userEmail}</span>}
          <button type="button" onClick={onSignOut}>Sign Out</button>
        </div>
      </nav>
    </header>
  );
}

export default Header;
