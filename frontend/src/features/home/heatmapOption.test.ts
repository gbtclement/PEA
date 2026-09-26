import { buildHeatmapOption } from "./heatmapOption";

test("regroupe par secteur et colore selon la variation", () => {
  const option = buildHeatmapOption([
    { id: 1, symbol: "MC", name: "LVMH", sector: "Luxe", market_cap_eur: 300, change_pct: 3 },
    { id: 2, symbol: "RMS", name: "Hermès", sector: "Luxe", market_cap_eur: 200, change_pct: -3 },
    { id: 3, symbol: "TTE", name: "TotalEnergies", sector: "Énergie", market_cap_eur: 100, change_pct: 0 },
  ]) as unknown as { series: { data: { name: string; children: { name: string; value: number; itemStyle: { color: string } }[] }[] }[] };
  const sectors = option.series[0].data;
  expect(sectors.map((s) => s.name)).toEqual(["Luxe", "Énergie"]);
  expect(sectors[0].children[0]).toMatchObject({ name: "MC", value: 300, itemStyle: { color: "rgb(22, 163, 74)" } });
  expect(sectors[0].children[1].itemStyle.color).toBe("rgb(220, 38, 38)");
});
