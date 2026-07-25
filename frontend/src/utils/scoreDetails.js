export function humanizeScoreStatus(value) {
  if (typeof value !== "string" || !value.trim()) return "Available";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatScoreDetailValue(detail) {
  if (typeof detail?.formatted_value === "string" && detail.formatted_value.trim()) {
    return detail.formatted_value;
  }

  const value = detail?.value;
  if (value === null || value === undefined) return "Data unavailable";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }
  if (typeof value === "string" && value.trim()) return humanizeScoreStatus(value);
  return "Data unavailable";
}

export function normalizeScoreDetails(component) {
  const details = Array.isArray(component?.details)
    ? component.details
    : Array.isArray(component?.metrics)
      ? component.metrics
      : [];

  return details
    .filter((detail) => detail && typeof detail === "object")
    .map((detail, index) => ({
      ...detail,
      key: typeof detail.key === "string" ? detail.key : `detail-${index}`,
      label: typeof detail.label === "string" ? detail.label : "Score factor",
      displayValue: formatScoreDetailValue(detail),
      displayStatus: humanizeScoreStatus(detail.status),
      available: detail.availability !== "unavailable" && detail.status !== "unavailable",
    }));
}
