const QUARTERS = ["Q1", "Q2", "Q3", "Q4"];
const SIGNED_DECIMAL = /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const ACCEPTED_STATES = new Set(["available", "partial"]);

const validDate = (value) => {
  const raw = String(value || "");
  if (!ISO_DATE.test(raw)) return false;
  const parsed = new Date(`${raw}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === raw;
};

const contractIsCertified = (history) => history?.schema_version === "1" &&
  history?.certification_policy === "sec-gaap-diluted-eps-history-1" &&
  history?.accounting_basis === "gaap" && history?.share_basis === "diluted" &&
  history?.unit === "USD_per_share";

const pointIsCertified = (row) => row?.unit === "USD_per_share" &&
  row?.observation_type === "reported" && ["original", "amended"].includes(row?.reporting_status) &&
  SIGNED_DECIMAL.test(String(row?.exact_eps ?? "")) && Number.isFinite(Number(row.exact_eps)) &&
  validDate(row?.period_start) && validDate(row?.period_end) && row.period_start <= row.period_end &&
  typeof row?.provenance_label === "string" && row.provenance_label.trim().length > 0 &&
  Array.isArray(row?.source_ids) && row.source_ids.length > 0 && row.source_ids.length <= 2 &&
  row.source_ids.every((id) => typeof id === "string" && id.length > 0);

const chartPoint = (row) => ({ ...row, exactLabel: String(row.exact_eps),
  chartValue: Number(row.exact_eps) });

const rowsFor = (history, frequency) => ACCEPTED_STATES.has(history?.[frequency]?.state) &&
  contractIsCertified(history) ? history?.[`${frequency}_points`] : [];

export function normalizeAnnualEPSPoints(history) {
  const rows = rowsFor(history, "annual");
  if (!Array.isArray(rows)) return [];
  const accepted = rows.filter((row) => Number.isInteger(row?.fiscal_year) &&
    row.fiscal_year >= 1900 && row.fiscal_year <= 2200 && pointIsCertified(row));
  const counts = new Map();
  accepted.forEach((row) => counts.set(row.fiscal_year, (counts.get(row.fiscal_year) || 0) + 1));
  const normalized = accepted.filter((row) => counts.get(row.fiscal_year) === 1)
    .sort((left, right) => left.fiscal_year - right.fiscal_year).map(chartPoint);
  if (normalized.some((row, index) => index > 0 && row.period_end <= normalized[index - 1].period_end)) return [];
  return normalized;
}

const quarterIndex = (row) => row.fiscal_year * 4 + QUARTERS.indexOf(row.fiscal_quarter);

export function normalizeQuarterlyEPSPoints(history) {
  const rows = rowsFor(history, "quarterly");
  if (!Array.isArray(rows)) return [];
  const accepted = rows.filter((row) => Number.isInteger(row?.fiscal_year) &&
    row.fiscal_year >= 1900 && row.fiscal_year <= 2200 && QUARTERS.includes(row?.fiscal_quarter) &&
    pointIsCertified(row));
  const counts = new Map();
  accepted.forEach((row) => {
    const identity = `${row.fiscal_year}:${row.fiscal_quarter}`;
    counts.set(identity, (counts.get(identity) || 0) + 1);
  });
  const normalized = accepted.filter((row) => counts.get(`${row.fiscal_year}:${row.fiscal_quarter}`) === 1)
    .sort((left, right) => quarterIndex(left) - quarterIndex(right)).map(chartPoint);
  if (normalized.some((row, index) => index > 0 && row.period_end <= normalized[index - 1].period_end)) return [];
  return normalized;
}

export function segmentAnnualEPSPoints(points) {
  return points.reduce((segments, point) => {
    const current = segments.at(-1);
    if (!current || point.comparison_break_before ||
        point.fiscal_year !== current.at(-1).fiscal_year + 1) segments.push([point]);
    else current.push(point);
    return segments;
  }, []);
}

export function segmentQuarterlyEPSPoints(points) {
  return points.reduce((segments, point) => {
    const current = segments.at(-1);
    if (!current || point.comparison_break_before ||
        quarterIndex(point) !== quarterIndex(current.at(-1)) + 1) segments.push([point]);
    else current.push(point);
    return segments;
  }, []);
}

export const shouldShowZeroBaseline = (points) => points.length > 0 &&
  points.some((point) => point.chartValue <= 0) &&
  points.some((point) => point.chartValue >= 0);

export const formatEPSAxis = (value) => `${Number(value) < 0 ? "-" : ""}$${Math.abs(Number(value)).toLocaleString("en-US", { maximumFractionDigits: 4 })}`;

export function epsTooltipRows(point, mode) {
  if (!point) return [];
  const rows = [mode === "annual" ? `FY${point.fiscal_year}` : `FY${point.fiscal_year} ${point.fiscal_quarter}`,
    `Diluted EPS: ${point.exactLabel} USD/share`, "Basis: Reported GAAP diluted",
    `Reporting status: ${point.reporting_status === "amended" ? "Amended" : "Original"}`,
    `Source: ${point.provenance_label}`];
  if (point.comparison_break_before) rows.splice(3, 0,
    "Comparability: Not established with prior period");
  return rows;
}

const REASONS = {
  feature_disabled: "The certified EPS history feature is not available for this report.",
  historical_acquisition_unavailable: "Certified EPS history could not be acquired for this report.",
  no_certified_observations: "No certified reported GAAP diluted EPS observations are available.",
  conflicted_fiscal_periods: "Certified EPS history is unavailable because accepted fiscal-period evidence conflicts.",
  source_limit_exceeded: "Certified EPS history is incomplete because the bounded source limit was reached.",
};

export function epsAvailabilityMessage(availability, frequency) {
  const reason = availability?.reasons?.find((item) => REASONS[item]);
  return REASONS[reason] || `${frequency === "annual" ? "Annual" : "Quarterly"} diluted EPS history is unavailable for this accepted research snapshot.`;
}
