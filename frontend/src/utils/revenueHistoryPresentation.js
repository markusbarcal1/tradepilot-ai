const HISTORICAL_TYPES = new Set(["reported", "certified_derived"]);
const SOURCE_KINDS = new Set(["directly_reported", "derived"]);
const GROWTH_STATES = new Set(["available", "unavailable"]);
const QUARTERS = ["Q1", "Q2", "Q3", "Q4"];
const DECIMAL = /^(0|[1-9]\d*)(?:\.(\d+))?$/;
const SIGNED_DECIMAL = /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

const validDate = (value) => {
  const raw = String(value || "");
  if (!ISO_DATE.test(raw)) return false;
  const parsed = new Date(`${raw}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === raw;
};

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

const chartPoint = (row) => ({ ...row, chartValue: Number(row.exact_revenue),
  exactLabel: formatExactRevenue(row.exact_revenue) });

export function normalizeAnnualRevenuePoints(rows) {
  if (!Array.isArray(rows)) return [];
  const accepted = rows.filter((row) => Number.isInteger(row?.fiscal_year) &&
    row.fiscal_year >= 1900 && row.fiscal_year <= 2200 && row.currency === "USD" &&
    HISTORICAL_TYPES.has(row.observation_type) && DECIMAL.test(String(row.exact_revenue ?? "")) &&
    Number.isFinite(Number(row.exact_revenue)) && Number(row.exact_revenue) >= 0 &&
    validDate(row.period_end));
  const counts = new Map();
  accepted.forEach((row) => counts.set(row.fiscal_year, (counts.get(row.fiscal_year) || 0) + 1));
  return accepted.filter((row) => counts.get(row.fiscal_year) === 1)
    .sort((left, right) => left.fiscal_year - right.fiscal_year).map(chartPoint);
}

export function segmentAnnualRevenuePoints(points) {
  return points.reduce((segments, point) => {
    const current = segments.at(-1);
    if (!current || point.fiscal_year !== current.at(-1).fiscal_year + 1) segments.push([point]);
    else current.push(point);
    return segments;
  }, []);
}

const validGrowth = (growth) => {
  if (!growth || !GROWTH_STATES.has(growth.state)) return false;
  if (growth.state === "unavailable") return growth.exact_growth_pct == null &&
    growth.display_growth_pct == null;
  return SIGNED_DECIMAL.test(String(growth.exact_growth_pct ?? "")) &&
    SIGNED_DECIMAL.test(String(growth.display_growth_pct ?? "")) &&
    Number.isFinite(Number(growth.display_growth_pct));
};

const quarterIndex = (row) => row.fiscal_year * 4 + QUARTERS.indexOf(row.fiscal_quarter);

export function normalizeQuarterlyRevenuePoints(rows) {
  if (!Array.isArray(rows)) return [];
  const accepted = rows.filter((row) => Number.isInteger(row?.fiscal_year) &&
    row.fiscal_year >= 1900 && row.fiscal_year <= 2200 && QUARTERS.includes(row.fiscal_quarter) &&
    row.currency === "USD" && SOURCE_KINDS.has(row.source_kind) &&
    row.derived === (row.source_kind === "derived") && DECIMAL.test(String(row.exact_revenue ?? "")) &&
    Number.isFinite(Number(row.exact_revenue)) && Number(row.exact_revenue) >= 0 &&
    validDate(row.period_end) && validGrowth(row.qoq) && validGrowth(row.yoy));
  const counts = new Map();
  accepted.forEach((row) => {
    const identity = `${row.fiscal_year}:${row.fiscal_quarter}`;
    counts.set(identity, (counts.get(identity) || 0) + 1);
  });
  const normalized = accepted.filter((row) => counts.get(`${row.fiscal_year}:${row.fiscal_quarter}`) === 1)
    .sort((left, right) => quarterIndex(left) - quarterIndex(right)).slice(-8).map(chartPoint);
  if (normalized.some((row, index) => index > 0 &&
      row.period_end <= normalized[index - 1].period_end)) return [];
  return normalized;
}

export function segmentQuarterlyRevenuePoints(points) {
  return points.reduce((segments, point) => {
    const current = segments.at(-1);
    if (!current || quarterIndex(point) !== quarterIndex(current.at(-1)) + 1) segments.push([point]);
    else current.push(point);
    return segments;
  }, []);
}

const observationLabel = (value) => value === "certified_derived" ? "Certified derived" : "Reported";
export const growthLabel = (value) => {
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

const growthRow = (label, growth) => growth?.state === "available"
  ? `${label} growth: ${growthLabel(growth.display_growth_pct)}` : `${label} growth: unavailable`;

export function quarterlyTooltipRows(point) {
  if (!point) return [];
  const derived = point.source_kind === "derived";
  return [`FY${point.fiscal_year} ${point.fiscal_quarter}`, `Revenue: ${point.exactLabel}`,
    growthRow("QoQ", point.qoq), growthRow("YoY", point.yoy),
    `Status: ${derived ? "Certified derived Q4" : "Reported"}`,
    ...(derived && point.derivation_formula_identity === "FY-minus-Q1-minus-Q2-minus-Q3"
      ? ["Method: Certified FY minus Q1 minus Q2 minus Q3"] : []),
    ...(!derived && point.source_policy === "historical-financial-observation-schema-1"
      ? ["Source: SEC Company Facts quarterly observation"] : [])];
}

export function quarterlyUnavailableMessage(availability) {
  if (availability === "insufficient_data") return "Quarterly revenue history is insufficient for an eligible consecutive series.";
  if (availability === "conflict") return "Quarterly revenue history is unavailable because the accepted evidence conflicts.";
  return "Quarterly revenue history is unavailable for this accepted research snapshot.";
}
