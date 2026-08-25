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

class HorizontalRayRenderer {
  constructor(color) {
    this.color = color;
    this.point = null;
  }

  update(point) {
    this.point = point;
  }

  draw(target) {
    if (!this.point) return;

    target.useMediaCoordinateSpace(({ context, mediaSize }) => {
      const startX = Math.max(0, this.point.x);

      if (startX >= mediaSize.width) return;

      context.save();
      context.beginPath();
      context.setLineDash([2, 5]);
      context.lineWidth = 1;
      context.strokeStyle = this.color;
      context.moveTo(startX, this.point.y);
      context.lineTo(mediaSize.width, this.point.y);
      context.stroke();
      context.restore();
    });
  }
}

class HorizontalRayPaneView {
  constructor(color) {
    this.rayRenderer = new HorizontalRayRenderer(color);
  }

  update(point) {
    this.rayRenderer.update(point);
  }

  zOrder() {
    return "bottom";
  }

  renderer() {
    return this.rayRenderer;
  }
}

class HorizontalRayPrimitive {
  constructor(color) {
    this.point = null;
    this.paneView = new HorizontalRayPaneView(color);
  }

  attached({ chart, series, requestUpdate }) {
    this.chart = chart;
    this.series = series;
    this.requestUpdate = requestUpdate;
  }

  detached() {
    this.chart = null;
    this.series = null;
    this.requestUpdate = null;
  }

  setPoint(point) {
    this.point = point;
    this.updateAllViews();
    this.requestUpdate?.();
  }

  updateAllViews() {
    if (!this.point || !this.chart || !this.series) {
      this.paneView.update(null);
      return;
    }

    const x = this.chart.timeScale().timeToCoordinate(this.point.time);
    const y = this.series.priceToCoordinate(this.point.value);

    this.paneView.update(x === null || y === null ? null : { x, y });
  }

  paneViews() {
    return [this.paneView];
  }
}

const CHART_THEMES = {
  dark: {
    background: "#020617",
    text: "#94a3b8",
    grid: "#1e293b",
    border: "#334155",
  },
  light: {
    background: "#f8fafc",
    text: "#475569",
    grid: "#e2e8f0",
    border: "#cbd5e1",
  },
};

function getChartOptions(theme) {
  const colors = CHART_THEMES[theme] || CHART_THEMES.dark;

  return {
    layout: {
      background: { type: ColorType.Solid, color: colors.background },
      textColor: colors.text,
    },
    grid: {
      vertLines: { color: colors.grid },
      horzLines: { color: colors.grid },
    },
    rightPriceScale: {
      borderColor: colors.border,
    },
    timeScale: {
      borderColor: colors.border,
      timeVisible: true,
      secondsVisible: false,
    },
  };
}

function TradingChart({
  data,
  analysis,
  positionAverageCost,
  positionShares,
  resetKey,
  theme,
}) {
  const priceChartRef = useRef(null);
  const positionLabelRef = useRef(null);
  const volumeChartRef = useRef(null);
  const macdChartRef = useRef(null);
  const chartRefs = useRef(null);
  const dataRef = useRef(data || []);
  const didFitContentRef = useRef(false);
  const lastResetKeyRef = useRef(resetKey);
  const initialThemeRef = useRef(theme);

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

    const baseOptions = getChartOptions(initialThemeRef.current);

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
      priceLineVisible: false,
    });

    const sma50Series = priceChart.addSeries(LineSeries, {
      color: "#fbbf24",
      lineWidth: 2,
      priceLineVisible: false,
    });

    const sma20Ray = new HorizontalRayPrimitive("rgba(56, 189, 248, 0.42)");
    const sma50Ray = new HorizontalRayPrimitive("rgba(251, 191, 36, 0.42)");
    sma20Series.attachPrimitive(sma20Ray);
    sma50Series.attachPrimitive(sma50Ray);

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

    const updatePositionLabel = () => {
      const positionPrice = chartRefs.current?.positionAverageCost;

      if (!positionLabelRef.current || !Number.isFinite(positionPrice)) return;

      const y = candleSeries.priceToCoordinate(positionPrice);
      positionLabelRef.current.style.display = y === null ? "none" : "flex";

      if (y !== null) {
        positionLabelRef.current.style.top = `${y}px`;
        positionLabelRef.current.style.right = `${candleSeries.priceScale().width()}px`;
      }
    };

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
    priceChart.timeScale().subscribeVisibleLogicalRangeChange(updatePositionLabel);

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
      positionPriceLine: null,
      positionAverageCost: null,
      updatePositionLabel,
      sma20Series,
      sma50Series,
      sma20Ray,
      sma50Ray,
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

        window.requestAnimationFrame(updatePositionLabel);
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      priceChart.timeScale().unsubscribeVisibleLogicalRangeChange(updatePositionLabel);
      priceChart.remove();
      volumeChart.remove();
      macdChart.remove();
      chartRefs.current = null;
    };
  }, []);

  useEffect(() => {
    if (!chartRefs.current) return;

    const options = getChartOptions(theme);
    chartRefs.current.priceChart.applyOptions(options);
    chartRefs.current.volumeChart.applyOptions(options);
    chartRefs.current.macdChart.applyOptions(options);
    window.requestAnimationFrame(chartRefs.current.updatePositionLabel);
  }, [theme]);

  useEffect(() => {
    if (!chartRefs.current) return;

    const { candleSeries } = chartRefs.current;

    if (chartRefs.current.positionPriceLine) {
      candleSeries.removePriceLine(chartRefs.current.positionPriceLine);
      chartRefs.current.positionPriceLine = null;
    }

    const positionIsInvalid =
      !Number.isFinite(positionAverageCost) ||
      positionAverageCost <= 0 ||
      !Number.isFinite(positionShares) ||
      positionShares <= 0;

    if (positionIsInvalid) {
      chartRefs.current.positionAverageCost = null;
      if (positionLabelRef.current) positionLabelRef.current.style.display = "none";
      return;
    }

    chartRefs.current.positionAverageCost = positionAverageCost;

    chartRefs.current.positionPriceLine = candleSeries.createPriceLine({
      price: positionAverageCost,
      color: "rgba(59, 130, 246, 0.72)",
      lineWidth: 2,
      lineStyle: 0,
      axisLabelVisible: false,
    });
    window.requestAnimationFrame(chartRefs.current.updatePositionLabel);
  }, [positionAverageCost, positionShares]);

  useEffect(() => {
    if (!data || data.length === 0 || !chartRefs.current) return;

    const {
      priceChart,
      volumeChart,
      macdChart,
      candleSeries,
      sma20Series,
      sma50Series,
      sma20Ray,
      sma50Ray,
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

    const sma20Data = mapLine(data, "sma_20");
    const sma50Data = mapLine(data, "sma_50");

    candleSeries.setData(mapCandles(data));
    sma20Series.setData(sma20Data);
    sma50Series.setData(sma50Data);
    sma20Ray.setPoint(sma20Data.at(-1) || null);
    sma50Ray.setPoint(sma50Data.at(-1) || null);

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
    window.requestAnimationFrame(chartRefs.current.updatePositionLabel);

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
        <div ref={positionLabelRef} className="position-price-label">
          POS: {positionShares?.toLocaleString("en-US")}{" @ "}
          {positionAverageCost?.toFixed(2)}
        </div>
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
