import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";

function TradingChart({ data, analysis }) {
  const priceChartRef = useRef(null);
  const volumeChartRef = useRef(null);
  const macdChartRef = useRef(null);

  const [hoverData, setHoverData] = useState(null);

  useEffect(() => {
    if (
      !data ||
      data.length === 0 ||
      !priceChartRef.current ||
      !volumeChartRef.current ||
      !macdChartRef.current
    ) {
      return;
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

    candleSeries.setData(
      data.map((d) => ({
        time: d.time,
        open: Number(d.open),
        high: Number(d.high),
        low: Number(d.low),
        close: Number(d.close),
      }))
    );

    const sma20Series = priceChart.addSeries(LineSeries, {
      color: "#38bdf8",
      lineWidth: 2,
    });

    sma20Series.setData(
      data
        .filter((d) => d.sma_20 !== null)
        .map((d) => ({
          time: d.time,
          value: Number(d.sma_20),
        }))
    );

    const sma50Series = priceChart.addSeries(LineSeries, {
      color: "#fbbf24",
      lineWidth: 2,
    });

    sma50Series.setData(
      data
        .filter((d) => d.sma_50 !== null)
        .map((d) => ({
          time: d.time,
          value: Number(d.sma_50),
        }))
    );

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

    const firstTime = data[0].time;
    const lastTime = data[data.length - 1].time;
    const currentPrice = Number(data[data.length - 1].close);

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

    const volumeSeries = volumeChart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "volume",
      },
    })

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

    const macdHistogramSeries = macdChart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "price",
        precision: 4,
        minMove: 0.0001,
      },
    });

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

    const macdSeries = macdChart.addSeries(LineSeries, {
      color: "#a78bfa",
      lineWidth: 2,
    });

    macdSeries.setData(
      data
        .filter((d) => d.macd !== null)
        .map((d) => ({
          time: d.time,
          value: Number(d.macd),
        }))
    );

    const signalSeries = macdChart.addSeries(LineSeries, {
      color: "#f97316",
      lineWidth: 2,
    });

    signalSeries.setData(
      data
        .filter((d) => d.macd_signal !== null)
        .map((d) => ({
          time: d.time,
          value: Number(d.macd_signal),
        }))
    );

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

      const candle = data.find((d) => d.time === param.time);

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

    priceChart.timeScale().fitContent();
    volumeChart.timeScale().fitContent();
    macdChart.timeScale().fitContent();

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
    };
  }, [data]);

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