import { useEffect, useMemo, useRef, useState } from "react";
import { ColorType, CrosshairMode, LineSeries, createChart, createSeriesMarkers } from "lightweight-charts";
import { annualTooltipRows, formatRevenueAxis, normalizeAnnualRevenuePoints,
  normalizeQuarterlyRevenuePoints, quarterlyTooltipRows, quarterlyUnavailableMessage,
  segmentAnnualRevenuePoints, segmentQuarterlyRevenuePoints } from "../utils/revenueHistoryPresentation";

const THEMES = {
  dark: { background: "#020617", text: "#94a3b8", grid: "#1e293b", border: "#334155" },
  light: { background: "#f8fafc", text: "#475569", grid: "#e2e8f0", border: "#cbd5e1" },
};

function RevenueChartRenderer({ mode, points, segments, theme }) {
  const [hover, setHover] = useState(null);
  const [renderError, setRenderError] = useState(false);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!points.length || !chartRef.current) return undefined;
    let chart;
    try {
      const colors = THEMES[theme] || THEMES.dark;
      const byDate = new Map(points.map((point) => [point.period_end, point]));
      const labelByDate = new Map(points.map((point) => [point.period_end,
        mode === "annual" ? `FY${point.fiscal_year}` : `FY${point.fiscal_year} ${point.fiscal_quarter}`]));
      chart = createChart(chartRef.current, { height: 280, autoSize: true,
        layout: { background: { type: ColorType.Solid, color: colors.background }, textColor: colors.text,
          attributionLogo: true },
        grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
        rightPriceScale: { borderColor: colors.border },
        timeScale: { borderColor: colors.border, timeVisible: false, rightOffset: 2,
          tickMarkFormatter: (time) => labelByDate.get(typeof time === "string" ? time : `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`) || "" },
        crosshair: { mode: CrosshairMode.Normal },
        localization: { priceFormatter: formatRevenueAxis } });
      segments.forEach((segment) => {
        const series = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 3,
          pointMarkersVisible: true, pointMarkersRadius: 5, priceLineVisible: false,
          lastValueVisible: false, crosshairMarkerVisible: true });
        series.setData(segment.map((point) => ({ time: point.period_end, value: point.chartValue })));
        if (mode === "quarterly") createSeriesMarkers(series, segment.filter((point) => point.derived)
          .map((point) => ({ time: point.period_end, position: "inBar", shape: "square",
            color: "#f59e0b", size: 1.5, text: "Derived Q4" })));
      });
      chart.timeScale().fitContent();
      chart.subscribeCrosshairMove((param) => setHover(param.time ? byDate.get(param.time) || null : null));
    } catch { queueMicrotask(() => setRenderError(true)); }
    return () => chart?.remove();
  }, [mode, points, segments, theme]);

  if (!points.length) return null;
  const tooltipRows = mode === "annual" ? annualTooltipRows(hover) : quarterlyTooltipRows(hover);
  return <>
    <div className="research-chart-shell"><div ref={chartRef} className="research-chart revenue-history-chart" aria-hidden="true" />
      {hover && <div className="research-chart-tooltip revenue-history-tooltip">{tooltipRows.map((row, index) => index === 0 ? <strong key={row}>{row}</strong> : <span key={row}>{row}</span>)}</div>}</div>
    {renderError && <p className="research-chart-warning" role="status">Interactive chart rendering is unavailable. Certified {mode} revenue data remains available in the report.</p>}
  </>;
}

export default function RevenueHistoryChart({ revenueHistory, annualPoints, theme = "dark" }) {
  const [mode, setMode] = useState("annual");
  const annual = useMemo(() => normalizeAnnualRevenuePoints(
    annualPoints ?? revenueHistory?.annual_points), [annualPoints, revenueHistory?.annual_points]);
  const quarterly = useMemo(() => revenueHistory?.availability === "available"
    ? normalizeQuarterlyRevenuePoints(revenueHistory?.points) : [],
  [revenueHistory?.availability, revenueHistory?.points]);
  const points = mode === "annual" ? annual : quarterly;
  const segments = useMemo(() => mode === "annual" ? segmentAnnualRevenuePoints(points)
    : segmentQuarterlyRevenuePoints(points), [mode, points]);
  const annualMode = mode === "annual";
  const hasGaps = segments.length > 1;
  const first = points[0], last = points.at(-1);

  return <section className="research-performance revenue-history" aria-labelledby="revenue-history-title">
    <header className="research-performance-header"><div><p className="research-chart-kicker">Certified {mode} observations · USD</p><h4 id="revenue-history-title">{annualMode ? "Annual" : "Quarterly"} Revenue History</h4><p>{annualMode ? "Reported and certified-derived fiscal-year revenue only." : "Reported quarters and distinctly marked certified-derived Q4 revenue only."}</p></div>
      <div className="revenue-history-modes" aria-label="Revenue history period">
        <button type="button" aria-pressed={annualMode} onClick={() => setMode("annual")}>Annual</button>
        <button type="button" aria-pressed={!annualMode} onClick={() => setMode("quarterly")}>Quarterly</button>
      </div></header>
    {points.length ? <>
      <div className="research-chart-legend" aria-label={`${annualMode ? "Annual" : "Quarterly"} revenue chart legend`}><span className="revenue-actual"><i />Historical revenue</span>{!annualMode && quarterly.some((point) => point.derived) && <span className="revenue-derived"><i />Certified derived Q4</span>}</div>
      <RevenueChartRenderer key={mode} mode={mode} points={points} segments={segments} theme={theme} />
      <p className="research-chart-summary" aria-live="polite">{points.length} certified {mode} observation{points.length === 1 ? "" : "s"}, {annualMode ? `FY${first.fiscal_year} to FY${last.fiscal_year}` : `${first.display_label || `FY${first.fiscal_year} ${first.fiscal_quarter}`} to ${last.display_label || `FY${last.fiscal_year} ${last.fiscal_quarter}`}`}.</p>
      {hasGaps && <p className="research-chart-warning">Missing fiscal {annualMode ? "years" : "quarters"} are shown as breaks; no values are interpolated.</p>}
    </> : <p className="research-chart-unavailable revenue-history-unavailable">{annualMode ? "Annual revenue history is unavailable for this accepted research snapshot." : quarterlyUnavailableMessage(revenueHistory?.availability)}</p>}
    <details className="research-methodology"><summary>About This Data</summary><div><p><strong>Measurement:</strong> exact {mode} revenue accepted by the backend certification contract.</p><p><strong>Scope:</strong> {annualMode ? "reported and certified-derived historical observations only" : "reported quarterly observations and clearly identified certified-derived Q4 observations only"}; projections and malformed observations are excluded.</p><p><strong>Gaps:</strong> missing fiscal {annualMode ? "years" : "quarters"} are not filled or connected.</p></div></details>
  </section>;
}
