import { buildAllocationOption, buildHistoryOption } from "./charts";

test("anneau de répartition", () => {
  const option = buildAllocationOption([{ name: "LVMH", value: 600 }, { name: "Total", value: 400 }]);
  expect(option.series[0].type).toBe("pie");
  expect(option.series[0].radius).toEqual(["55%", "80%"]);
  expect(option.series[0].data).toEqual([{ name: "LVMH", value: 600 }, { name: "Total", value: 400 }]);
});

test("courbe d'évolution : valeur et montant investi", () => {
  const option = buildHistoryOption([{ date: "2026-03-02", value: 20, invested: 20 }, { date: "2026-03-03", value: 24, invested: 20 }]);
  expect(option.xAxis.data).toEqual(["2026-03-02", "2026-03-03"]);
  expect(option.series.map((s) => s.name)).toEqual(["Valeur", "Montant investi"]);
  expect(option.series[0].data).toEqual([20, 24]);
});
