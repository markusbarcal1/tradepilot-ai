import { useEffect, useMemo, useRef, useState } from "react";
import { ColorType, CrosshairMode, LineSeries, createChart } from "lightweight-charts";

const THEMES = {
  dark: { background: "#020617", text: "#94a3b8", grid: "#1e293b", border: "#334155" },
  light: { background: "#f8fafc", text: "#475569", grid: "#e2e8f0", border: "#cbd5e1" },
};

function options(theme, height) {
  const colors = THEMES[theme] || THEMES.dark;
  return { height, autoSize: true,
    layout: { background: { type: ColorType.Solid, color: colors.background }, textColor: colors.text },
    grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
    rightPriceScale: { borderColor: colors.border },
    timeScale: { borderColor: colors.border, timeVisible: false, rightOffset: 2, barSpacing: 7, minBarSpacing: 3 },
    crosshair: { mode: CrosshairMode.Normal },
    localization: { priceFormatter: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%` } };
}

const lineData = (points, key) => points.map((point) => ({ time: point.date, value: Number(point[key]) }));
const signed = (value) => `${value >= 0 ? "+" : ""}${Number(value).toFixed(2)}%`;
const signedPoints = (value) => `${value >= 0 ? "+" : ""}${Number(value).toFixed(2)} pp`;

export default function ResearchPerformanceChart({ history, ticker, benchmark, theme = "dark" }) {
  const windows = useMemo(() => history?.windows || [], [history?.windows]);
  const preferred = windows.find((item) => item.label === "6M") || windows.at(-1);
  const [selected, setSelected] = useState(preferred?.label || null);
  const [hover, setHover] = useState(null);
  const [renderErrorKey, setRenderErrorKey] = useState(null);
  const mainRef = useRef(null), relativeRef = useRef(null);
  const active = useMemo(() => windows.find((item) => item.label === selected) || preferred,
    [windows, selected, preferred]);

  useEffect(() => {
    if (!active?.points?.length || !mainRef.current || !relativeRef.current) return undefined;
    let main, relative;
    try {
      main = createChart(mainRef.current, options(theme, 280));
      relative = createChart(relativeRef.current, options(theme, 150));
      const company = main.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 3, priceLineVisible: false });
      const group = main.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 3, priceLineVisible: false });
      const difference = relative.addSeries(LineSeries, { color: "#a78bfa", lineWidth: 2, priceLineVisible: false });
      difference.createPriceLine({ price: 0, color: "#64748b", lineWidth: 1, lineStyle: 2, axisLabelVisible: true });
      company.setData(lineData(active.points, "company_cumulative_return"));
      group.setData(lineData(active.points, "benchmark_cumulative_return"));
      difference.setData(lineData(active.points, "relative_performance"));
      main.timeScale().fitContent(); relative.timeScale().fitContent();
      const updateHover = (param) => {
        if (!param.time) return setHover(null);
        const point = active.points.find((item) => item.date === param.time);
        if (point) setHover(point);
      };
      main.subscribeCrosshairMove(updateHover); relative.subscribeCrosshairMove(updateHover);
    } catch { queueMicrotask(() => setRenderErrorKey(`${active.label}:${theme}`)); }
    return () => { main?.remove(); relative?.remove(); };
  }, [active, theme]);

  if (!active) return null;
  const first = active.points[0], latest = active.points.at(-1);
  return <div className="research-performance" data-snapshot-id={history.snapshot_id}>
    <header className="research-performance-header"><div><p className="research-chart-kicker">Measurement · percentage return</p><h4>Historical Adjusted-Price Returns</h4><p>Each series starts at 0% on the first common completed session in the selected window.</p></div>
      <div className="research-timeframes" role="group" aria-label="Historical performance timeframe">
        {["1M", "3M", "6M"].map((label) => { const supported = windows.some((item) => item.label === label); return <button key={label} type="button" disabled={!supported} aria-pressed={active.label === label} onClick={() => { if (supported) { setSelected(label); setHover(null); } }}>{label}</button>; })}
      </div></header>
    <div className="research-chart-legend" aria-label="Historical adjusted-price return chart legend"><span className="company"><i />{ticker} adjusted-price return</span><span className="benchmark"><i />{benchmark} benchmark adjusted-price return</span></div>
    <div className="research-chart-shell"><div ref={mainRef} className="research-chart research-chart-main" aria-hidden="true" />
      {hover && <div className="research-chart-tooltip"><strong>{hover.date}</strong><span>{ticker}: {signed(hover.company_cumulative_return)}</span><span>{benchmark}: {signed(hover.benchmark_cumulative_return)}</span><span>Relative: {signedPoints(hover.relative_performance)}</span></div>}</div>
    <p className="research-chart-summary" aria-live="polite">{active.label} observation period: {first.date} to {latest.date}. {ticker} {signed(latest.company_cumulative_return)}; {benchmark} {signed(latest.benchmark_cumulative_return)}.</p>
    <div className="research-relative-header"><div><p className="research-chart-kicker">Measurement · percentage-point difference</p><h5>Relative Adjusted-Price Return</h5></div><strong>{signedPoints(latest.relative_performance)}</strong></div>
    <div ref={relativeRef} className="research-chart research-chart-relative" aria-hidden="true" />
    <p className="research-context">Above and rising means {ticker} is gaining relative to {benchmark}; below and falling means it is losing relative ground. The zero line means equal adjusted-price returns. Historical adjusted-price performance does not predict future returns.</p>
    {history.coverage?.has_gaps && <p className="research-chart-warning">Only common completed sessions are shown; missing sessions were not filled or interpolated.</p>}
    {renderErrorKey === `${active.label}:${theme}` && <p className="research-chart-warning" role="status">Interactive chart rendering is unavailable. The verified data summary remains available above.</p>}
    <details className="research-methodology"><summary>About This Data</summary><div><p><strong>Measurement:</strong> cumulative adjusted-price return and company-minus-benchmark relative return.</p><p><strong>Unit:</strong> percent for each return series; percentage points (pp) for the difference.</p><p><strong>Period:</strong> {active.label}, from {first.date} through {latest.date}, using common completed trading sessions only.</p><p><strong>Benchmark:</strong> {benchmark}, the accepted {history.classification_quality === "sector_fallback" ? "sector fallback" : "industry ETF proxy"} for this snapshot.</p><p><strong>Limitations:</strong> Yahoo adjusted Close is requested with auto-adjust enabled. TradePilot does not independently reconstruct or verify a dividend-reinvested total-return index. ETF proxies may not represent every company in an industry.</p></div></details>
  </div>;
}
