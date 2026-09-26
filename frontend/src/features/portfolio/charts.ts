import type { HistoryPointOut } from "@/lib/api/client";
import { formatPrice } from "@/lib/format";

export const PALETTE = ["#6366f1", "#0ea5e9", "#16a34a", "#f59e0b", "#ec4899", "#8b5cf6", "#14b8a6", "#f97316", "#64748b"];

export function buildAllocationOption(slices: { name: string; value: number }[]) {
  return {
    color: PALETTE,
    tooltip: {
      trigger: "item" as const,
      formatter: (p: { name: string; value: number; percent: number }) => `${p.name}<br/>${formatPrice(p.value)} € (${formatPrice(p.percent)} %)`,
    },
    legend: { type: "scroll" as const, orient: "vertical" as const, right: 0, top: "middle", textStyle: { color: "#52525b" } },
    series: [{
      type: "pie" as const, radius: ["55%", "80%"], center: ["32%", "50%"], avoidLabelOverlap: true,
      itemStyle: { borderColor: "#ffffff", borderWidth: 2 }, label: { show: false }, data: slices,
    }],
  };
}

export function buildHistoryOption(points: HistoryPointOut[]) {
  return {
    color: ["#6366f1", "#a1a1aa"],
    tooltip: { trigger: "axis" as const, valueFormatter: (v: number) => `${formatPrice(v)} €` },
    legend: { top: 0, textStyle: { color: "#52525b" } },
    grid: { left: 64, right: 16, top: 32, bottom: 28 },
    xAxis: {
      type: "category" as const, data: points.map((p) => p.date), boundaryGap: false,
      axisLine: { lineStyle: { color: "#e4e4e7" } }, axisLabel: { color: "#71717a" },
    },
    yAxis: { type: "value" as const, scale: true, splitLine: { lineStyle: { color: "#f4f4f5" } }, axisLabel: { color: "#71717a" } },
    series: [
      { name: "Valeur", type: "line" as const, data: points.map((p) => p.value), showSymbol: false, smooth: true, areaStyle: { opacity: 0.08 } },
      { name: "Montant investi", type: "line" as const, data: points.map((p) => p.invested), showSymbol: false, step: "end" as const, lineStyle: { type: "dashed" as const } },
    ],
  };
}
