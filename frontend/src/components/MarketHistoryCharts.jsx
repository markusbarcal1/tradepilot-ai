import { useEffect, useMemo, useRef, useState } from "react";
import { ColorType, CrosshairMode, LineSeries, createChart } from "lightweight-charts";

const THEMES = {
  dark: { background: "#020617", text: "#94a3b8", grid: "#1e293b", border: "#334155" },
  light: { background: "#f8fafc", text: "#475569", grid: "#e2e8f0", border: "#cbd5e1" },
};
const chartOptions = (theme, height, formatter) => { const colors = THEMES[theme] || THEMES.dark; return { height, autoSize: true,
  layout: { background: { type: ColorType.Solid, color: colors.background }, textColor: colors.text },
  grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
  rightPriceScale: { borderColor: colors.border }, timeScale: { borderColor: colors.border, rightOffset: 2, barSpacing: 7, minBarSpacing: 3 },
  crosshair: { mode: CrosshairMode.Normal }, localization: { priceFormatter: formatter } }; };
const signed = (value) => `${value >= 0 ? "+" : ""}${Number(value).toFixed(2)}%`;

export default function MarketHistoryCharts({ history, volatility, theme = "dark" }) {
  const windows = useMemo(() => history?.windows || [], [history?.windows]);
  const preferred = windows.find((row) => row.label === "6M") || windows.at(-1);
  const [selected, setSelected] = useState(preferred?.label || null);
  const [equityHover, setEquityHover] = useState(null), [vixHover, setVixHover] = useState(null);
  const [vixBoundaryPositions, setVixBoundaryPositions] = useState(null);
  const equityRef = useRef(null), vixRef = useRef(null);
  const active = useMemo(() => windows.find((row) => row.label === selected) || preferred, [windows, selected, preferred]);

  useEffect(() => {
    if (!active?.points?.length || !equityRef.current) return undefined;
    let chart;
    try {
      chart = createChart(equityRef.current, chartOptions(theme, 280, (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`));
      const spy = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 3, priceLineVisible: false });
      const qqq = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 3, priceLineVisible: false });
      spy.setData(active.points.map((p) => ({ time: p.date, value: Number(p.spy_cumulative_return) })));
      qqq.setData(active.points.map((p) => ({ time: p.date, value: Number(p.qqq_cumulative_return) })));
      chart.timeScale().fitContent();
      chart.subscribeCrosshairMove((param) => setEquityHover(param.time ? active.points.find((p) => p.date === param.time) || null : null));
    } catch { /* Text summary remains authoritative when canvas is unavailable. */ }
    return () => chart?.remove();
  }, [active, theme]);

  useEffect(() => {
    if (!history?.vix_points?.length || !vixRef.current) return undefined;
    let chart, observer;
    try {
      chart = createChart(vixRef.current, chartOptions(theme, 190, (v) => v.toFixed(1)));
      const series = chart.addSeries(LineSeries, { color: "#a78bfa", lineWidth: 3, priceLineVisible: false });
      series.setData(history.vix_points.map((p) => ({ time: p.date, value: Number(p.level) })));
      series.createPriceLine({ price: history.vix_threshold_low, color: "#22c55e", lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
      series.createPriceLine({ price: history.vix_threshold_high, color: "#ef4444", lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
      chart.timeScale().fitContent();
      const positionLabels = () => {
        const low = series.priceToCoordinate(history.vix_threshold_low);
        const high = series.priceToCoordinate(history.vix_threshold_high);
        if (Number.isFinite(low) && Number.isFinite(high)) setVixBoundaryPositions({ low, high });
      };
      positionLabels();
      observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(positionLabels);
      observer?.observe(vixRef.current);
      chart.subscribeCrosshairMove((param) => setVixHover(param.time ? history.vix_points.find((p) => p.date === param.time) || null : null));
    } catch { /* Accessible values remain visible. */ }
    return () => { observer?.disconnect(); chart?.remove(); };
  }, [history, theme]);

  const first = active?.points?.[0], latest = active?.points?.at(-1), vixFirst = history?.vix_points?.[0], vixLatest = history?.vix_points?.at(-1);
  return <div className="market-history" data-snapshot-id={history?.snapshot_id}>
    {active ? <section className="research-performance market-equity-history" aria-labelledby="market-equity-history-title">
      <header className="research-performance-header"><div><p className="research-chart-kicker">Measurement · percentage return</p><h4 id="market-equity-history-title">Historical Broad-Market Adjusted-Price Returns</h4><p>Broad-market performance, rebased from the first shared session.</p></div><div className="research-timeframes" role="group" aria-label="Broad-market historical timeframe">{["1M", "3M", "6M"].map((label) => { const supported = windows.some((row) => row.label === label); return <button key={label} type="button" disabled={!supported} aria-pressed={active.label === label} onClick={() => { if (supported) { setSelected(label); setEquityHover(null); } }}>{label}</button>; })}</div></header>
      <div className="research-chart-legend" aria-label="Broad-market chart legend"><span className="company"><i />SPY · S&amp;P 500 ETF benchmark</span><span className="benchmark"><i />QQQ · Nasdaq-100 ETF benchmark</span></div>
      <div className="research-chart-shell"><div ref={equityRef} className="research-chart market-chart-equity" aria-hidden="true" />{equityHover && <div className="research-chart-tooltip"><strong>{equityHover.date}</strong><span>SPY: {signed(equityHover.spy_cumulative_return)}</span><span>QQQ: {signed(equityHover.qqq_cumulative_return)}</span></div>}</div>
      <p className="research-chart-summary" aria-live="polite">{active.label} observation period: {first.date} to {latest.date}. SPY {signed(latest.spy_cumulative_return)}; QQQ {signed(latest.qqq_cumulative_return)}.</p>
      <p className="research-context">Broad-market history—not company-specific evidence or a prediction.</p>
      {history.equity_coverage?.has_gaps && <p className="research-chart-warning">Only common completed SPY/QQQ sessions are shown; gaps were not filled or interpolated.</p>}
      <details className="research-methodology"><summary>About This Data</summary><div><p><strong>Measurement:</strong> cumulative SPY and QQQ adjusted-price returns.</p><p><strong>Unit:</strong> percent.</p><p><strong>Period:</strong> {active.label}, {first.date} through {latest.date}, common completed sessions only.</p><p><strong>Comparator:</strong> SPY is the S&amp;P 500 ETF benchmark; QQQ is the Nasdaq-100 ETF benchmark.</p><p><strong>Limitations:</strong> Yahoo adjusted Close is requested with auto-adjust enabled. TradePilot does not independently verify a dividend-reinvested total-return index. ETF proxies do not represent every security or the analyzed company&apos;s industry.</p></div></details>
    </section> : <p className="research-chart-unavailable">Historical SPY/QQQ visualization is unavailable for this accepted research snapshot.</p>}
    {history?.vix_points?.length ? <section className="research-performance market-vix-history" aria-labelledby="market-vix-history-title"><header className="research-performance-header"><div><p className="research-chart-kicker">Measurement · index level</p><h4 id="market-vix-history-title">Historical VIX Index Level</h4><p>Closing volatility-index levels over time.</p></div><strong className="market-vix-latest">Latest {Number(volatility?.close ?? vixLatest.level).toFixed(2)} · {volatility?.regime || "unavailable"} regime</strong></header>
      <div className="research-chart-legend"><span className="vix"><i />VIX index level</span></div><div className="research-chart-shell"><div ref={vixRef} className="research-chart market-chart-vix" aria-hidden="true" />{vixBoundaryPositions && <div className="vix-boundary-labels" aria-hidden="true"><span className="low" style={{ top: vixBoundaryPositions.low }}>Low below {history.vix_threshold_low}</span><span className="high" style={{ top: vixBoundaryPositions.high }}>Elevated {history.vix_threshold_high}+</span></div>}{vixHover && <div className="research-chart-tooltip"><strong>{vixHover.date}</strong><span>VIX: {Number(vixHover.level).toFixed(2)}</span></div>}</div>
      <p className="research-chart-summary" aria-live="polite">{vixFirst.date} to {vixLatest.date} · latest {Number(vixLatest.level).toFixed(2)}.</p><p className="research-context">Historical volatility context—not an adjusted-price return, forecast, or probability.</p>
      <details className="research-methodology"><summary>About This Data</summary><div><p><strong>Measurement:</strong> VIX closing index level.</p><p><strong>Unit:</strong> index points.</p><p><strong>Period:</strong> {vixFirst.date} through {vixLatest.date}, completed supported observations.</p><p><strong>Regime boundaries:</strong> low below {history.vix_threshold_low}; normal from {history.vix_threshold_low} to below {history.vix_threshold_high}; elevated at {history.vix_threshold_high} or higher.</p><p><strong>Limitations:</strong> VIX is a volatility index, not a security return, forecast, probability, or company-specific measure.</p></div></details>
    </section> : <p className="research-chart-unavailable">Historical VIX visualization is unavailable for this accepted research snapshot.</p>}
  </div>;
}
