const HISTORICAL_TYPES = new Set(["reported", "certified_derived"]);
const DECIMAL = /^(0|[1-9]\d*)(?:\.(\d+))?$/;

export function formatExactRevenue(value) {
  const match = String(value ?? "").match(DECIMAL);
  if (!match) return null;
  const whole = BigInt(match[1]).toLocaleString("en-US");
  return `$${whole}${match[2] ? `.${match[2]}` : ""}`;
}

export function formatRevenueAxis(value) {
  const amount = Math.abs(Number(value));
  const units = [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]];
  const unit = units.find(([scale]) => amount >= scale);
  if (!unit) return `$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value)}`;
  return `$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value / unit[0])}${unit[1]}`;
}

export function normalizeAnnualRevenuePoints(rows) {
  if (!Array.isArray(rows)) return [];
  const accepted = rows.filter((row) => Number.isInteger(row?.fiscal_year) &&
    row.fiscal_year >= 1900 && row.fiscal_year <= 2200 && row.currency === "USD" &&
    HISTORICAL_TYPES.has(row.observation_type) && DECIMAL.test(String(row.exact_revenue ?? "")) &&
    Number.isFinite(Number(row.exact_revenue)) && Number(row.exact_revenue) >= 0 &&
    /^\d{4}-\d{2}-\d{2}$/.test(String(row.period_end || "")));
  const counts = new Map();
  accepted.forEach((row) => counts.set(row.fiscal_year, (counts.get(row.fiscal_year) || 0) + 1));
  return accepted.filter((row) => counts.get(row.fiscal_year) === 1)
    .sort((left, right) => left.fiscal_year - right.fiscal_year)
    .map((row) => ({ ...row, chartValue: Number(row.exact_revenue), exactLabel: formatExactRevenue(row.exact_revenue) }));
}

export function segmentAnnualRevenuePoints(points) {
  return points.reduce((segments, point) => {
    const current = segments.at(-1);
    if (!current || point.fiscal_year !== current.at(-1).fiscal_year + 1) segments.push([point]);
    else current.push(point);
    return segments;
  }, []);
}

const observationLabel = (value) => value === "certified_derived" ? "Certified derived" : "Reported";
const growthLabel = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const amount = Number(value);
  return Number.isFinite(amount) ? `${amount > 0 ? "+" : ""}${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(amount)}%` : null;
};

export function annualTooltipRows(point) {
  if (!point) return [];
  return [`FY${point.fiscal_year}`, `Revenue: ${point.exactLabel}`,
    ...(growthLabel(point.yoy_growth_pct) ? [`YoY growth: ${growthLabel(point.yoy_growth_pct)}`] : []),
    `Status: ${observationLabel(point.observation_type)}`,
    ...(point.provenance_label ? [`Source: ${point.provenance_label}`] : [])];
}
