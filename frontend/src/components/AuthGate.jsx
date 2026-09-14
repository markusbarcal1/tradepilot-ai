import App from "../App";
import useAuth from "../auth/useAuth";
import ToastProvider from "../context/ToastProvider";
import AuthStateScreen from "./AuthStateScreen";
import InviteSetup from "./InviteSetup";
import Login from "./Login";


function AuthGate() {
  const { currentUser, status, signOut } = useAuth();

  if (status === "loading" || status === "verifying") {
    return (
      <AuthStateScreen
        title="Loading your workspace"
        message="Restoring your secure session…"
        loading
      />
    );
  }

  if (status === "configuration-error") {
    return (
      <AuthStateScreen
        title="Authentication is not configured"
        message="Add the required Supabase browser configuration to run TradePilot AI."
      />
    );
  }

  if (status === "provider-error") {
    return (
      <AuthStateScreen
        title="Authentication is temporarily unavailable"
        message="The authentication service could not be reached. Refresh to try again."
      />
    );
  }

  if (status === "forbidden") {
    return (
      <AuthStateScreen
        title="Private beta access required"
        message="This account does not currently have access to the TradePilot AI private beta."
        actionLabel="Sign Out"
        onAction={signOut}
      />
    );
  }

  if (status === "invite-setup") return <InviteSetup />;

  if (status !== "authorized" || !currentUser) return <Login />;

  return (
    <ToastProvider>
      <App
        key={currentUser.user_id}
        userEmail={currentUser.email}
        onSignOut={signOut}
      />
    </ToastProvider>
  );
}

export default AuthGate;
