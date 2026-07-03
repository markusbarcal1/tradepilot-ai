import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";

function mapCandles(data) {
  return data.map((d) => ({
    time: d.time,
    open: Number(d.open),
    high: Number(d.high),
    low: Number(d.low),
    close: Number(d.close),
  }));
}

function mapLine(data, key) {
  return data
    .filter((d) => d[key] !== null)
    .map((d) => ({
      time: d.time,
      value: Number(d[key]),
    }));
}

function TradingChart({ data, analysis, resetKey }) {
  const priceChartRef = useRef(null);
  const volumeChartRef = useRef(null);
  const macdChartRef = useRef(null);
  const chartRefs = useRef(null);
  const dataRef = useRef(data || []);
  const didFitContentRef = useRef(false);
  const lastResetKeyRef = useRef(resetKey);

  const [hoverData, setHoverData] = useState(null);

  useEffect(() => {
    dataRef.current = data || [];
  }, [data]);

  useEffect(() => {
    if (
      chartRefs.current ||
      !priceChartRef.current ||
      !volumeChartRef.current ||
      !macdChartRef.current
    ) {
      return undefined;
    }

    const baseOptions = {
      layout: {
        background: { type: ColorType.Solid, color: "#020617" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      rightPriceScale: {
        borderColor: "#334155",
      },
      timeScale: {
        borderColor: "#334155",
        timeVisible: true,
        secondsVisible: false,
      },
    };

    const priceChart = createChart(priceChartRef.current, {
      ...baseOptions,
      width: priceChartRef.current.clientWidth,
      height: priceChartRef.current.clientHeight,
    });

    const volumeChart = createChart(volumeChartRef.current, {
      ...baseOptions,
      width: volumeChartRef.current.clientWidth,
      height: volumeChartRef.current.clientHeight,
    });

    const macdChart = createChart(macdChartRef.current, {
      ...baseOptions,
      width: macdChartRef.current.clientWidth,
      height: macdChartRef.current.clientHeight,
    });

    const candleSeries = priceChart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const sma20Series = priceChart.addSeries(LineSeries, {
      color: "#38bdf8",
      lineWidth: 2,
    });

    const sma50Series = priceChart.addSeries(LineSeries, {
      color: "#fbbf24",
      lineWidth: 2,
    });

    const resistanceZoneSeries = priceChart.addSeries(LineSeries, {
      color: "rgba(239, 68, 68, 0.65)",
      lineWidth: 2,
      lineStyle: 2,
    });

    const supportZoneSeries = priceChart.addSeries(LineSeries, {
      color: "rgba(34, 197, 94, 0.65)",
      lineWidth: 2,
      lineStyle: 2,
    });

    const volumeSeries = volumeChart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "volume",
      },
    });

    const macdHistogramSeries = macdChart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "price",
        precision: 4,
        minMove: 0.0001,
      },
    });

    const macdSeries = macdChart.addSeries(LineSeries, {
      color: "#a78bfa",
      lineWidth: 2,
    });

    const signalSeries = macdChart.addSeries(LineSeries, {
      color: "#f97316",
      lineWidth: 2,
    });

    const syncCharts = (sourceChart, targetCharts) => {
      sourceChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range) return;
        targetCharts.forEach((targetChart) => {
          targetChart.timeScale().setVisibleLogicalRange(range);
        });
      });
    };

    syncCharts(priceChart, [volumeChart, macdChart]);
    syncCharts(volumeChart, [priceChart, macdChart]);
    syncCharts(macdChart, [priceChart, volumeChart]);

    priceChart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.point) {
        setHoverData(null);
        return;
      }

      const candle = dataRef.current.find((d) => d.time === param.time);

      if (!candle) {
        setHoverData(null);
        return;
      }

      setHoverData({
        ...candle,
        x: param.point.x,
        y: param.point.y,
      });
    });

    chartRefs.current = {
      priceChart,
      volumeChart,
      macdChart,
      candleSeries,
      sma20Series,
      sma50Series,
      resistanceZoneSeries,
      supportZoneSeries,
      volumeSeries,
      macdHistogramSeries,
      macdSeries,
      signalSeries,
    };

    const handleResize = () => {
      if (
        priceChartRef.current &&
        volumeChartRef.current &&
        macdChartRef.current
      ) {
        priceChart.applyOptions({
          width: priceChartRef.current.clientWidth,
          height: priceChartRef.current.clientHeight,
        });

        volumeChart.applyOptions({
          width: volumeChartRef.current.clientWidth,
          height: volumeChartRef.current.clientHeight,
        });

        macdChart.applyOptions({
          width: macdChartRef.current.clientWidth,
          height: macdChartRef.current.clientHeight,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      priceChart.remove();
      volumeChart.remove();
      macdChart.remove();
      chartRefs.current = null;
    };
  }, []);

  useEffect(() => {
    if (!data || data.length === 0 || !chartRefs.current) return;

    const {
      priceChart,
      volumeChart,
      macdChart,
      candleSeries,
      sma20Series,
      sma50Series,
      resistanceZoneSeries,
      supportZoneSeries,
      volumeSeries,
      macdHistogramSeries,
      macdSeries,
      signalSeries,
    } = chartRefs.current;
    const shouldResetRange = lastResetKeyRef.current !== resetKey;
    const visibleRange = shouldResetRange
      ? null
      : priceChart.timeScale().getVisibleLogicalRange();
    const firstTime = data[0].time;
    const lastTime = data[data.length - 1].time;
    const currentPrice = Number(data[data.length - 1].close);

    candleSeries.setData(mapCandles(data));
    sma20Series.setData(mapLine(data, "sma_20"));
    sma50Series.setData(mapLine(data, "sma_50"));

    supportZoneSeries.setData([]);
    resistanceZoneSeries.setData([]);

    if (
      analysis?.support_zone &&
      analysis.support_zone.low !== null &&
      analysis.support_zone.high !== null
    ) {
      const supportLow = Number(analysis.support_zone.low);
      const supportHigh = Number(analysis.support_zone.high);
      let supportLine = null;

      if (supportHigh < currentPrice) {
        supportLine = supportHigh;
      } else if (supportLow < currentPrice) {
        supportLine = supportLow;
      }

      if (supportLine !== null) {
        supportZoneSeries.setData([
          { time: firstTime, value: supportLine },
          { time: lastTime, value: supportLine },
        ]);
      }
    }

    if (
      analysis?.resistance_zone &&
      analysis.resistance_zone.low !== null &&
      analysis.resistance_zone.high !== null
    ) {
      const resistanceLow = Number(analysis.resistance_zone.low);
      const resistanceHigh = Number(analysis.resistance_zone.high);
      let resistanceLine = null;

      if (resistanceLow > currentPrice) {
        resistanceLine = resistanceLow;
      } else if (resistanceHigh > currentPrice) {
        resistanceLine = resistanceHigh;
      }

      if (resistanceLine !== null) {
        resistanceZoneSeries.setData([
          { time: firstTime, value: resistanceLine },
          { time: lastTime, value: resistanceLine },
        ]);
      }
    }

    volumeSeries.setData(
      data.map((d) => ({
        time: d.time,
        value: Number(d.volume),
        color:
          Number(d.close) >= Number(d.open)
            ? "rgba(34, 197, 94, 0.6)"
            : "rgba(239, 68, 68, 0.6)",
      }))
    );

    macdHistogramSeries.setData(
      data
        .filter((d) => d.macd_hist !== null)
        .map((d) => ({
          time: d.time,
          value: Number(d.macd_hist),
          color:
            Number(d.macd_hist) >= 0
              ? "rgba(34, 197, 94, 0.55)"
              : "rgba(239, 68, 68, 0.55)",
        }))
    );

    macdSeries.setData(mapLine(data, "macd"));
    signalSeries.setData(mapLine(data, "macd_signal"));

    if (shouldResetRange) {
      priceChart.timeScale().fitContent();
      volumeChart.timeScale().fitContent();
      macdChart.timeScale().fitContent();
      didFitContentRef.current = true;
      lastResetKeyRef.current = resetKey;
    } else if (visibleRange) {
      priceChart.timeScale().setVisibleLogicalRange(visibleRange);
      volumeChart.timeScale().setVisibleLogicalRange(visibleRange);
      macdChart.timeScale().setVisibleLogicalRange(visibleRange);
    } else if (!didFitContentRef.current) {
      priceChart.timeScale().fitContent();
      volumeChart.timeScale().fitContent();
      macdChart.timeScale().fitContent();
      didFitContentRef.current = true;
    }
  }, [data, analysis?.support_zone, analysis?.resistance_zone, resetKey]);

  return (
    <div className="multi-chart-container">
      <div className="chart-section">
        <div className="chart-label">Price</div>
        <div ref={priceChartRef} className="price-chart" />
      </div>

      <div className="chart-section">
        <div className="chart-label">Volume</div>
        <div ref={volumeChartRef} className="volume-chart" />
      </div>

      <div className="chart-section">
        <div className="chart-label">MACD</div>
        <div ref={macdChartRef} className="macd-chart" />
      </div>

      {hoverData && (
        <div
          className="chart-tooltip"
          style={{
            left: hoverData.x + 30,
            top: hoverData.y + 70,
          }}
        >
          <div className="tooltip-date">{hoverData.time}</div>
          <div>Open: ${hoverData.open}</div>
          <div>High: ${hoverData.high}</div>
          <div>Low: ${hoverData.low}</div>
          <div>Close: ${hoverData.close}</div>
          <div>Volume: {Number(hoverData.volume).toLocaleString()}</div>
          <div>MACD: {hoverData.macd}</div>
          <div>Signal: {hoverData.macd_signal}</div>
          <div>Hist: {hoverData.macd_hist}</div>
        </div>
      )}
    </div>
  );
}

export default TradingChart;
