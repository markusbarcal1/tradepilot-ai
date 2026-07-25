const TOAST_META = {
  success: { icon: "✓", defaultTitle: "Success" },
  info: { icon: "ℹ", defaultTitle: "Information" },
  warning: { icon: "⚠", defaultTitle: "Warning" },
  error: { icon: "✕", defaultTitle: "Error" },
};

function Toast({ toast, onDismiss }) {
  const meta = TOAST_META[toast.type] ?? TOAST_META.info;

  return (
    <div
      className={`toast toast-${toast.type} toast-${toast.phase}`}
      role="alert"
      aria-live="assertive"
    >
      <span className="toast-icon" aria-hidden="true">{meta.icon}</span>
      <div className="toast-content">
        <strong>{toast.title || meta.defaultTitle}</strong>
        <p>{toast.message}</p>
      </div>
      <button
        className="toast-close"
        type="button"
        aria-label={`Dismiss ${toast.title || meta.defaultTitle} notification`}
        onClick={() => onDismiss(toast.id)}
      >
        ×
      </button>
    </div>
  );
}

export default Toast;
