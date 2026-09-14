import { useState } from "react";

import useAuth from "../auth/useAuth";
import "./Auth.css";


function InviteSetup() {
  const { completeInvite, signOut } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const result = await completeInvite(password);
      if (result.error) setError(result.error);
    } catch {
      setError("Unable to complete the invitation. Request a new invite and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="invite-title">
        <div className="auth-brand">TradePilot AI</div>
        <span className="auth-badge">Private Beta</span>
        <h1 id="invite-title">Set your password</h1>
        <p>Complete your invitation to access TradePilot AI.</p>
        <form onSubmit={handleSubmit}>
          <label>
            <span>Password</span>
            <input type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          <label>
            <span>Confirm password</span>
            <input type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required />
          </label>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <button type="submit" disabled={submitting}>{submitting ? "Completing…" : "Complete invitation"}</button>
          <button className="auth-secondary-button" type="button" onClick={signOut}>Cancel and sign out</button>
        </form>
      </section>
    </main>
  );
}

export default InviteSetup;
