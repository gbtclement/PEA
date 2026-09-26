import type { HeatmapItem } from "@/lib/api/client";
import { changeColor } from "@/lib/colors";
import { formatPct } from "@/lib/format";

type Leaf = { name: string; value: number; id: number; fullName: string; change: number; itemStyle: { color: string } };

export function buildHeatmapOption(items: HeatmapItem[]) {
  const sectors = new Map<string, Leaf[]>();
  for (const item of items) {
    const leaves = sectors.get(item.sector) ?? [];
    leaves.push({ name: item.symbol, value: item.market_cap_eur, id: item.id, fullName: item.name, change: item.change_pct,
                  itemStyle: { color: changeColor(item.change_pct) } });
    sectors.set(item.sector, leaves);
  }
  return {
    tooltip: {
      formatter: (info: { data?: Partial<Leaf> & { name: string } }) =>
        info.data?.fullName ? `${info.data.fullName}<br/>${formatPct(info.data.change)}` : info.data?.name ?? "",
    },
    series: [{
      type: "treemap",
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      width: "100%",
      height: "100%",
      label: { show: true, formatter: "{b}", fontSize: 11, color: "#18181b" },
      upperLabel: { show: true, height: 18, color: "#52525b", fontSize: 11 },
      levels: [
        { itemStyle: { borderColor: "#ffffff", borderWidth: 2, gapWidth: 2 } },
        { itemStyle: { borderColor: "#ffffff", borderWidth: 1, gapWidth: 1 } },
      ],
      data: [...sectors.entries()].map(([name, children]) => ({ name, children })),
    }],
  };
}
