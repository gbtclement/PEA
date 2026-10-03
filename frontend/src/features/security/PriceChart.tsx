import { useEffect, useRef } from "react";
import { CandlestickSeries, createChart, HistogramSeries, LineSeries, type Time } from "lightweight-charts";
import type { HistoryOut } from "@/lib/api/client";
import { useIsMobile } from "@/lib/useIsMobile";

const UP = "#16a34a";
const DOWN = "#dc2626";
const priceFormat = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const parisDateTime = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const parisTime = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "2-digit", minute: "2-digit" });
const parisDay = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", day: "2-digit", month: "short" });

// L'intraday arrive en secondes UTC : on l'affiche à l'heure de Paris (les séances quotidiennes restent des dates).
function formatTime(time: unknown): string {
  return typeof time === "number" ? parisDateTime.format(time * 1000) : String(time);
}

function formatTick(time: unknown): string | null {
  if (typeof time !== "number") return null;
  const moment = time * 1000;
  return parisTime.format(moment) === "09:00" ? parisDay.format(moment) : parisTime.format(moment);
}

type Props = { history: HistoryOut; showSma50: boolean; showSma200: boolean; showRsi: boolean; showMacd: boolean };

export function PriceChart({ history, showSma50, showSma200, showRsi, showMacd }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mobile = useIsMobile();

  useEffect(() => {
    const chart = createChart(ref.current!, {
      autoSize: true,
      // Glissement vertical sur le graphique : la page défile (téléphone), le graphique ne bouge que dans le sens horizontal.
      handleScroll: { vertTouchDrag: false },
      layout: { background: { color: "#ffffff" }, textColor: "#52525b", attributionLogo: true, panes: { separatorColor: "#e4e4e7" } },
      grid: { vertLines: { color: "#f4f4f5" }, horzLines: { color: "#f4f4f5" } },
      localization: { locale: "fr-FR", priceFormatter: (p: number) => priceFormat.format(p), timeFormatter: formatTime },
      timeScale: { timeVisible: history.intraday, borderColor: "#e4e4e7", tickMarkFormatter: formatTick },
      rightPriceScale: { borderColor: "#e4e4e7" },
    });
    const t = (time: string | number) => time as Time;

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP, downColor: DOWN, borderVisible: false, wickUpColor: UP, wickDownColor: DOWN,
    });
    candles.setData(history.bars.map((b) => ({
      time: t(b.time), open: b.open ?? b.close, high: b.high ?? b.close, low: b.low ?? b.close, close: b.close,
    })));

    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume" });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volume.setData(history.bars.map((b) => ({
      time: t(b.time), value: b.volume ?? 0,
      color: b.close >= (b.open ?? b.close) ? "rgba(22, 163, 74, 0.3)" : "rgba(220, 38, 38, 0.3)",
    })));

    const lineOptions = { lineWidth: 2 as const, priceLineVisible: false, lastValueVisible: false };
    if (showSma50) chart.addSeries(LineSeries, { ...lineOptions, color: "#6366f1" }).setData(history.sma50.map((p) => ({ time: t(p.time), value: p.value })));
    if (showSma200) chart.addSeries(LineSeries, { ...lineOptions, color: "#f59e0b" }).setData(history.sma200.map((p) => ({ time: t(p.time), value: p.value })));

    let pane = 0;
    if (showRsi) {
      pane += 1;
      chart.addSeries(LineSeries, { ...lineOptions, lineWidth: 1, color: "#8b5cf6" }, pane)
        .setData(history.rsi.map((p) => ({ time: t(p.time), value: p.value })));
    }
    if (showMacd) {
      pane += 1;
      chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, pane)
        .setData(history.macd.map((p) => ({ time: t(p.time), value: p.histogram, color: p.histogram >= 0 ? "rgba(22,163,74,0.5)" : "rgba(220,38,38,0.5)" })));
      chart.addSeries(LineSeries, { ...lineOptions, lineWidth: 1, color: "#0ea5e9" }, pane).setData(history.macd.map((p) => ({ time: t(p.time), value: p.macd })));
      chart.addSeries(LineSeries, { ...lineOptions, lineWidth: 1, color: "#f97316" }, pane).setData(history.macd.map((p) => ({ time: t(p.time), value: p.signal })));
    }
    chart.panes().slice(1).forEach((p) => p.setHeight(110));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [history, showSma50, showSma200, showRsi, showMacd]);

  const height = (mobile ? 300 : 420) + (showRsi ? 110 : 0) + (showMacd ? 110 : 0);  // téléphone : moins haut
  return <div ref={ref} role="img" aria-label="Graphique des cours en chandeliers avec volumes et indicateurs" style={{ height }} className="w-full" />;
}
