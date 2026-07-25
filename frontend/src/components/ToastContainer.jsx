import Toast from "./Toast";

function ToastContainer({ toasts, onDismiss }) {
  return (
    <div className="toast-container" aria-live="assertive" aria-atomic="false">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

export default ToastContainer;
