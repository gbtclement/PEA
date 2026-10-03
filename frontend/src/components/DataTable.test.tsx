import { act, render, screen } from "@testing-library/react";
import { setViewportWidth } from "@/test/utils";
import { DataTable, type ColumnSpec } from "./DataTable";

type Row = { id: number; name: string };
const ROWS: Row[] = [{ id: 1, name: "A" }, { id: 2, name: "B" }, { id: 3, name: "C" }];
const COLUMNS: ColumnSpec<Row>[] = [{ id: "name", accessorKey: "name", header: "Nom", width: "200px" }];

afterEach(() => setViewportWidth(1200));

test("passer des cartes aux lignes (rotation) remet chaque ligne à sa place", () => {
  setViewportWidth(390);
  render(<DataTable rows={ROWS} columns={COLUMNS} sorting={[]} onSortingChange={() => {}} onRowClick={() => {}}
                    renderCard={(row) => <div>Carte {row.name}</div>} />);
  expect(screen.getByText("Carte B")).toBeInTheDocument();
  act(() => setViewportWidth(1200));
  const rows = screen.getAllByRole("row").slice(1);  // sans l'en-tête
  // Les hauteurs mesurées des cartes ne doivent pas rester : la 2e ligne commence à 56 px (hauteur d'une ligne).
  expect(rows[1].style.transform).toBe("translateY(56px)");
});
