import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getAuthenticatedUser, setApiAuthFailureHandler } from "../api/client";
import { isSupabaseConfigured, supabase } from "../lib/supabase";
import AuthContext from "./AuthContext";


const SIGN_IN_ERROR = "Unable to sign in. Check your credentials and try again.";

function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  const [status, setStatus] = useState(
    isSupabaseConfigured ? "loading" : "configuration-error"
  );
  const verificationIdRef = useRef(0);
  const sessionTokenRef = useRef(null);

  const clearSession = useCallback(() => {
    verificationIdRef.current += 1;
    sessionTokenRef.current = null;
    setSession(null);
    setCurrentUser(null);
    setStatus("unauthenticated");
  }, []);

  const verifySession = useCallback(async (nextSession) => {
    if (
      nextSession?.access_token &&
      sessionTokenRef.current === nextSession.access_token
    ) return;
    sessionTokenRef.current = nextSession?.access_token ?? null;
    const verificationId = verificationIdRef.current + 1;
    verificationIdRef.current = verificationId;

    if (!nextSession?.access_token) {
      setSession(null);
      setCurrentUser(null);
      setStatus("unauthenticated");
      return;
    }

    setSession(nextSession);
    setCurrentUser(null);
    setStatus("verifying");

    try {
      const response = await getAuthenticatedUser();
      if (verificationIdRef.current !== verificationId) return;
      setCurrentUser(response.data);
      setStatus("authorized");
    } catch (error) {
      if (verificationIdRef.current !== verificationId) return;
      if (error?.response?.status === 403) {
        setStatus("forbidden");
        return;
      }
      if (error?.response?.status === 401) {
        clearSession();
        return;
      }
      setStatus("provider-error");
    }
  }, [clearSession]);

  useEffect(() => {
    if (!supabase) return undefined;
    let active = true;

    setApiAuthFailureHandler((statusCode) => {
      if (!active) return;
      if (statusCode === 403) {
        setStatus("forbidden");
        return;
      }
      if (statusCode === 401) {
        clearSession();
        void supabase.auth.signOut({ scope: "local" });
      }
    });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        window.setTimeout(() => {
          if (active) void verifySession(nextSession);
        }, 0);
      }
    );

    void supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return;
      if (error) {
        setStatus("provider-error");
        return;
      }
      void verifySession(data.session);
    });

    return () => {
      active = false;
      verificationIdRef.current += 1;
      listener.subscription.unsubscribe();
      setApiAuthFailureHandler(null);
    };
  }, [clearSession, verifySession]);

  const signIn = useCallback(async (email, password) => {
    if (!supabase) return { error: "Authentication is not configured." };
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return { error: error ? SIGN_IN_ERROR : null };
  }, []);

  const signOut = useCallback(async () => {
    clearSession();
    if (supabase) await supabase.auth.signOut();
  }, [clearSession]);

  const value = useMemo(() => ({
    session,
    user: session?.user ?? null,
    currentUser,
    status,
    signIn,
    signOut,
  }), [session, currentUser, status, signIn, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
