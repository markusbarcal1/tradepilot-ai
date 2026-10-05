export const AI_ANALYSIS_CATEGORIES = [
  ["company", "Company"],
  ["earnings", "Earnings"],
  ["industry", "Industry"],
  ["economic", "Economic"],
  ["market", "Market"],
  ["geopolitical", "Geopolitical"],
];

const RATINGS = {
  very_positive: { label: "Very Positive", tone: "very-positive" },
  mostly_positive: { label: "Mostly Positive", tone: "mostly-positive" },
  mixed: { label: "Mixed", tone: "mixed" },
  mostly_negative: { label: "Mostly Negative", tone: "mostly-negative" },
  very_negative: { label: "Very Negative", tone: "very-negative" },
  insufficient_data: { label: "Insufficient Data", tone: "insufficient" },
};

export function ratingPresentation(rating) {
  return RATINGS[rating] || { label: "Unavailable", tone: "insufficient" };
}

export function visibleTextItems(items) {
  return Array.isArray(items)
    ? items.filter((item) => typeof item === "string" && item.trim())
    : [];
}

export function visibleKeyPoints(items) {
  return Array.isArray(items)
    ? items.filter((item) => typeof item?.text === "string" && item.text.trim())
    : [];
}
