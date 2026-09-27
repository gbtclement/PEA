import { getCoreRowModel, getSortedRowModel, createTable } from "@tanstack/react-table";
import type { ScreenerRow } from "@/lib/api/client";
import { buildColumns } from "./columns";

function sortedNames(names: string[]) {
  const table = createTable<ScreenerRow>({
    data: names.map((name, id) => ({ id, name }) as unknown as ScreenerRow),
    columns: buildColumns("stock"),
    state: { sorting: [{ id: "name", desc: false }] },
    onStateChange: () => {},
    renderFallbackValue: null,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  return table.getRowModel().rows.map((r) => r.original.name);
}

test("tri naturel des noms : chiffres d'abord, sans tenir compte des majuscules", () => {
  expect(sortedNames(["ZUCCHI", "2CRSI", "airbus", "74SOFTWARE", "Air Liquide", "A2A", "10X GROUP"]))
    .toEqual(["2CRSI", "10X GROUP", "74SOFTWARE", "A2A", "Air Liquide", "airbus", "ZUCCHI"]);
});
