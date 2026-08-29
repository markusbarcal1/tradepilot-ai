import "./Auth.css";


function AuthStateScreen({ title, message, actionLabel, onAction, loading = false }) {
  return (
    <main className="auth-shell">
      <section className="auth-card auth-state-card">
        <div className="auth-brand">TradePilot AI</div>
        {loading && <div className="auth-spinner" aria-hidden="true" />}
        <h1>{title}</h1>
        <p>{message}</p>
        {onAction && (
          <button type="button" onClick={onAction}>{actionLabel}</button>
        )}
      </section>
    </main>
  );
}

export default AuthStateScreen;
