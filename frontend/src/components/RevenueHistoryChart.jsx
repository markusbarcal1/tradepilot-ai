import { useEffect, useMemo, useRef, useState } from "react";
import { ColorType, CrosshairMode, LineSeries, createChart } from "lightweight-charts";
import { annualTooltipRows, formatRevenueAxis, normalizeAnnualRevenuePoints,
  segmentAnnualRevenuePoints } from "../utils/revenueHistoryPresentation";

const THEMES = {
  dark: { background: "#020617", text: "#94a3b8", grid: "#1e293b", border: "#334155" },
  light: { background: "#f8fafc", text: "#475569", grid: "#e2e8f0", border: "#cbd5e1" },
};
export default function RevenueHistoryChart({ annualPoints, theme = "dark" }) {
  const points = useMemo(() => normalizeAnnualRevenuePoints(annualPoints), [annualPoints]);
  const segments = useMemo(() => segmentAnnualRevenuePoints(points), [points]);
  const [hover, setHover] = useState(null);
  const [renderError, setRenderError] = useState(false);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!points.length || !chartRef.current) return undefined;
    let chart;
    try {
      const colors = THEMES[theme] || THEMES.dark;
      const byDate = new Map(points.map((point) => [point.period_end, point]));
      const yearByDate = new Map(points.map((point) => [point.period_end, `FY${point.fiscal_year}`]));
      chart = createChart(chartRef.current, { height: 280, autoSize: true,
        layout: { background: { type: ColorType.Solid, color: colors.background }, textColor: colors.text,
          attributionLogo: true },
        grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
        rightPriceScale: { borderColor: colors.border },
        timeScale: { borderColor: colors.border, timeVisible: false, rightOffset: 2,
          tickMarkFormatter: (time) => yearByDate.get(typeof time === "string" ? time : `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`) || "" },
        crosshair: { mode: CrosshairMode.Normal },
        localization: { priceFormatter: formatRevenueAxis } });
      segments.forEach((segment) => {
        const series = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 3,
          pointMarkersVisible: true, pointMarkersRadius: 5, priceLineVisible: false,
          lastValueVisible: false, crosshairMarkerVisible: true });
        series.setData(segment.map((point) => ({ time: point.period_end, value: point.chartValue })));
      });
      chart.timeScale().fitContent();
      chart.subscribeCrosshairMove((param) => setHover(param.time ? byDate.get(param.time) || null : null));
    } catch { queueMicrotask(() => setRenderError(true)); }
    return () => chart?.remove();
  }, [points, segments, theme]);

  if (!points.length) return <p className="research-chart-unavailable revenue-history-unavailable">Annual revenue history is unavailable for this accepted research snapshot.</p>;
  const hasGaps = segments.length > 1;
  return <section className="research-performance revenue-history" aria-labelledby="revenue-history-title">
    <header className="research-performance-header"><div><p className="research-chart-kicker">Certified annual observations · USD</p><h4 id="revenue-history-title">Annual Revenue History</h4><p>Reported and certified-derived fiscal-year revenue only.</p></div></header>
    <div className="research-chart-legend" aria-label="Annual revenue chart legend"><span className="revenue-actual"><i />Historical revenue</span></div>
    <div className="research-chart-shell"><div ref={chartRef} className="research-chart revenue-history-chart" aria-hidden="true" />
      {hover && <div className="research-chart-tooltip revenue-history-tooltip">{annualTooltipRows(hover).map((row, index) => index === 0 ? <strong key={row}>{row}</strong> : <span key={row}>{row}</span>)}</div>}</div>
    <p className="research-chart-summary" aria-live="polite">{points.length} certified annual observation{points.length === 1 ? "" : "s"}, FY{points[0].fiscal_year} to FY{points.at(-1).fiscal_year}.</p>
    {hasGaps && <p className="research-chart-warning">Missing fiscal years are shown as breaks; no values are interpolated.</p>}
    {renderError && <p className="research-chart-warning" role="status">Interactive chart rendering is unavailable. Certified annual revenue data remains available in the report.</p>}
    <details className="research-methodology"><summary>About This Data</summary><div><p><strong>Measurement:</strong> exact annual revenue accepted by the backend certification contract.</p><p><strong>Scope:</strong> reported and certified-derived historical observations only; projections and malformed observations are excluded.</p><p><strong>Gaps:</strong> missing fiscal years are not filled or connected.</p></div></details>
  </section>;
}
