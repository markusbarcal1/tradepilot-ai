import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ToastContainer from "../components/ToastContainer";
import ToastContext from "./ToastContext";
import "../styles/toast.css";

const MAX_TOASTS = 4;
const DEFAULT_DURATION_MS = 4000;
const EXIT_DURATION_MS = 240;

function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextIdRef = useRef(1);
  const timersRef = useRef(new Set());

  const schedule = useCallback((callback, delay) => {
    const timer = window.setTimeout(() => {
      timersRef.current.delete(timer);
      callback();
    }, delay);
    timersRef.current.add(timer);
    return timer;
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((current) => current.map((toast) => (
      toast.id === id ? { ...toast, phase: "exiting" } : toast
    )));

    schedule(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, EXIT_DURATION_MS);
  }, [schedule]);

  const showToast = useCallback(({
    type = "info",
    title,
    message,
    duration = DEFAULT_DURATION_MS,
  }) => {
    if (!message) return null;

    const id = nextIdRef.current;
    nextIdRef.current += 1;
    const toast = { id, type, title, message, phase: "entering" };

    setToasts((current) => [...current.slice(-(MAX_TOASTS - 1)), toast]);
    schedule(() => {
      setToasts((current) => current.map((item) => (
        item.id === id ? { ...item, phase: "visible" } : item
      )));
    }, 10);
    schedule(() => dismissToast(id), Math.max(0, duration));

    return id;
  }, [dismissToast, schedule]);

  useEffect(() => () => {
    timersRef.current.forEach((timer) => window.clearTimeout(timer));
    timersRef.current.clear();
  }, []);

  const value = useMemo(
    () => ({ showToast, dismissToast }),
    [dismissToast, showToast]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  );
}

export default ToastProvider;
