import { useEffect, useMemo, useRef, useState } from "react";
import { ColorType, CrosshairMode, LineSeries, createChart } from "lightweight-charts";
import { epsAvailabilityMessage, epsTooltipRows, formatEPSAxis, normalizeAnnualEPSPoints,
  normalizeQuarterlyEPSPoints, segmentAnnualEPSPoints, segmentQuarterlyEPSPoints,
  shouldShowZeroBaseline } from "../utils/epsHistoryPresentation";

const THEMES = {
  dark: { background: "#020617", text: "#94a3b8", grid: "#1e293b", border: "#334155", zero: "#cbd5e1" },
  light: { background: "#f8fafc", text: "#475569", grid: "#e2e8f0", border: "#cbd5e1", zero: "#475569" },
};

const safeSource = (point, sourceMap) => (point?.source_ids || []).map((id) => sourceMap?.get(id))
  .find((source) => source && /^https:\/\//i.test(source.url || ""));

function EPSChartRenderer({ mode, points, segments, sourceMap, theme }) {
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
        rightPriceScale: { borderColor: colors.border, autoScale: true },
        timeScale: { borderColor: colors.border, timeVisible: false, rightOffset: 2,
          tickMarkFormatter: (time) => labelByDate.get(typeof time === "string" ? time : `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`) || "" },
        crosshair: { mode: CrosshairMode.Normal }, localization: { priceFormatter: formatEPSAxis } });
      segments.forEach((segment, index) => {
        const series = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 3,
          pointMarkersVisible: true, pointMarkersRadius: 5, priceLineVisible: false,
          lastValueVisible: false, crosshairMarkerVisible: true });
        series.setData(segment.map((point) => ({ time: point.period_end, value: point.chartValue })));
        if (index === 0 && shouldShowZeroBaseline(points)) series.createPriceLine({ price: 0,
          color: colors.zero, lineWidth: 2, lineStyle: 2, axisLabelVisible: false, title: "" });
      });
      chart.timeScale().fitContent();
      chart.subscribeCrosshairMove((param) => setHover(param.time ? byDate.get(param.time) || null : null));
    } catch { queueMicrotask(() => setRenderError(true)); }
    return () => chart?.remove();
  }, [mode, points, segments, theme]);

  if (!points.length) return null;
  const source = safeSource(hover, sourceMap);
  return <>
    <div className="research-chart-shell"><div ref={chartRef} className="research-chart eps-history-chart" aria-hidden="true" />
      {hover && <div className="research-chart-tooltip eps-history-tooltip">{epsTooltipRows(hover, mode).map((row, index) => index === 0 ? <strong key={row}>{row}</strong> : <span key={row}>{row}</span>)}{source && <a href={source.url} target="_blank" rel="noreferrer">{source.title || source.name || "SEC source"}</a>}</div>}</div>
    {renderError && <p className="research-chart-warning" role="status">Interactive chart rendering is unavailable. Certified {mode} EPS data remains available in the report.</p>}
  </>;
}

export default function EPSHistoryChart({ epsHistory, sourceMap, theme = "dark" }) {
  const [mode, setMode] = useState("annual");
  const annual = useMemo(() => normalizeAnnualEPSPoints(epsHistory), [epsHistory]);
  const quarterly = useMemo(() => normalizeQuarterlyEPSPoints(epsHistory), [epsHistory]);
  const points = mode === "annual" ? annual : quarterly;
  const segments = useMemo(() => mode === "annual" ? segmentAnnualEPSPoints(points)
    : segmentQuarterlyEPSPoints(points), [mode, points]);
  const availability = epsHistory?.[mode];
  const annualMode = mode === "annual";
  const first = points[0], last = points.at(-1);

  return <section className="research-performance eps-history" aria-labelledby="eps-history-title">
    <header className="research-performance-header"><div><p className="research-chart-kicker">Certified {mode} observations · USD/share</p><h4 id="eps-history-title">{annualMode ? "Annual" : "Quarterly"} Diluted EPS History</h4><p>Reported GAAP diluted earnings per share only.</p></div>
      <div className="eps-history-modes" role="group" aria-label="Diluted EPS history period">
        <button type="button" aria-pressed={annualMode} onClick={() => setMode("annual")}>Annual</button>
        <button type="button" aria-pressed={!annualMode} onClick={() => setMode("quarterly")}>Quarterly</button>
      </div></header>
    {points.length ? <>
      <div className="research-chart-legend" aria-label={`${annualMode ? "Annual" : "Quarterly"} diluted EPS chart legend`}><span className="eps-reported"><i />Reported GAAP diluted EPS</span><span className="eps-zero"><i />Zero baseline</span></div>
      <EPSChartRenderer key={mode} mode={mode} points={points} segments={segments} sourceMap={sourceMap} theme={theme} />
      <p className="research-chart-summary" aria-live="polite">{points.length} certified {mode} observation{points.length === 1 ? "" : "s"}, {annualMode ? `FY${first.fiscal_year} to FY${last.fiscal_year}` : `FY${first.fiscal_year} ${first.fiscal_quarter} to FY${last.fiscal_year} ${last.fiscal_quarter}`}.</p>
      {availability?.state === "partial" && <p className="research-chart-warning">Some fiscal periods are missing or conflicted; accepted certified observations are shown.</p>}
      {segments.length > 1 && <p className="research-chart-warning">Missing or non-comparable fiscal {annualMode ? "years" : "quarters"} are shown as breaks; no values are interpolated.</p>}
    </> : <p className="research-chart-unavailable eps-history-unavailable">{epsAvailabilityMessage(availability, mode)}</p>}
    <details className="research-methodology"><summary>About This Data</summary><div><p><strong>Measurement:</strong> exact reported GAAP diluted EPS in USD per share accepted by the backend certification contract.</p><p><strong>Scope:</strong> reported observations only; basic EPS, adjusted EPS, derived Q4 EPS, growth calculations, and malformed observations are excluded.</p><p><strong>Gaps:</strong> missing fiscal {annualMode ? "years" : "quarters"} are not filled or connected.</p></div></details>
  </section>;
}
