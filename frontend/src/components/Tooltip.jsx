import { useId } from "react";

function Tooltip({ label, content }) {
  const tooltipId = useId();

  return (
    <span className="tooltip">
      <span>{label}</span>
      <button
        className="tooltip-trigger"
        type="button"
        aria-label={`About ${label}`}
        aria-describedby={tooltipId}
      >
        ?
      </button>
      <span className="tooltip-content" id={tooltipId} role="tooltip">
        {content}
      </span>
    </span>
  );
}

export default Tooltip;
