import { useRef, type ReactNode } from "react";
import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef, type SortingState } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useIsMobile } from "@/lib/useIsMobile";
/** Colonne de tableau : largeur CSS grid (ex. "80px" ou "minmax(150px, 2fr)") et alignement. */
export type ColumnSpec<T> = ColumnDef<T> & { width: string; align?: "right" };

type Props<T> = {
  rows: T[];
  columns: ColumnSpec<T>[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  onRowClick: (row: T) => void;
  getRowId?: (row: T) => string;
  /** Hauteur de la zone qui défile (classes Tailwind). */
  heightClass?: string;
  /** Téléphone : une carte par ligne au lieu des colonnes (même tri, même virtualisation). */
  renderCard?: (row: T) => ReactNode;
  /** Hauteur de la liste de cartes sur téléphone. */
  cardHeightClass?: string;
};

const ROW_HEIGHT = 56;
const CARD_HEIGHT = 112;  // estimation, mesurée ensuite ligne par ligne
const COLUMN_GAP = 6;  // px, doit correspondre à gap-x-1.5

/** Tableau triable et virtualisé : l'en-tête colle en haut et partage le défilement des lignes (colonnes alignées). */
export function DataTable<T>({ rows, columns, sorting, onSortingChange, onRowClick, getRowId,
                              heightClass = "h-[calc(100vh-270px)] min-h-[400px]", renderCard,
                              cardHeightClass = "h-[calc(100dvh-220px)] min-h-[360px]" }: Props<T>) {
  const cards = useIsMobile() && renderCard !== undefined;
  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: (updater) => onSortingChange(typeof updater === "function" ? updater(sorting) : updater),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableSortingRemoval: false,  // un clic inverse le sens ; sans ça, le 3e clic enlevait le tri (ordre d'origine, l'air mélangé)
    getRowId,
  });
  const scrollRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const tableRows = table.getRowModel().rows;
  const virtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => (cards ? CARD_HEIGHT : ROW_HEIGHT),
    overscan: 12,
    initialRect: { width: 1200, height: 800 },
    scrollMargin: bodyRef.current?.offsetTop ?? 0,  // les lignes commencent sous l'en-tête collant
  });
  const template = columns.map((c) => c.width).join(" ");
  // Largeur minimale des colonnes + marges : en dessous, le tableau défile horizontalement au lieu d'être coupé.
  // En-tête et lignes partagent le même conteneur de défilement : la barre verticale réduit leur largeur à tous
  // les deux, les colonnes restent donc alignées.
  const minWidth = columns.reduce((sum, c) => sum + Number(/(\d+)px/.exec(c.width)?.[1] ?? 0), 32 + COLUMN_GAP * (columns.length - 1));

  if (cards) {
    return (
      <div ref={scrollRef} className={cn(cardHeightClass, "overflow-auto")}>
        <div ref={bodyRef} style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
          {virtualizer.getVirtualItems().map((item) => (
            <div key={item.key} data-index={item.index} ref={virtualizer.measureElement} className="absolute inset-x-0 pb-2"
                 style={{ transform: `translateY(${item.start - virtualizer.options.scrollMargin}px)` }}>
              {renderCard!(tableRows[item.index].original)}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div role="table" aria-rowcount={tableRows.length + 1} ref={scrollRef}
         className={cn(heightClass, "overflow-auto text-sm tabular-nums")}>
      <div style={{ minWidth }}>
      <div role="row" className="sticky top-0 z-10 grid items-center gap-x-1.5 border-b border-border bg-card px-4 py-2 text-xs font-medium text-muted-foreground"
           style={{ gridTemplateColumns: template }}>
        {table.getHeaderGroups()[0].headers.map((header) => {
          const spec = header.column.columnDef as ColumnSpec<T>;
          const sorted = header.column.getIsSorted();
          return (
            <div role="columnheader" key={header.id} className={cn(spec.align === "right" && "text-right")}
                 aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined}>
              {header.column.getCanSort() ? (
                <button type="button" onClick={header.column.getToggleSortingHandler()}
                        className={cn("inline-flex items-center gap-1 hover:text-foreground", sorted && "text-foreground")}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {sorted === "asc" && <ArrowUp className="size-3" />}
                  {sorted === "desc" && <ArrowDown className="size-3" />}
                </button>
              ) : flexRender(header.column.columnDef.header, header.getContext())}
            </div>
          );
        })}
      </div>
        <div ref={bodyRef} style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
          {virtualizer.getVirtualItems().map((item) => {
            const row = tableRows[item.index];
            return (
              <div role="row" key={row.id} onClick={() => onRowClick(row.original)}
                   className="absolute inset-x-0 grid cursor-pointer items-center gap-x-1.5 border-b border-border px-4 hover:bg-muted/60"
                   style={{ gridTemplateColumns: template, height: ROW_HEIGHT, transform: `translateY(${item.start - virtualizer.options.scrollMargin}px)` }}>
                {row.getVisibleCells().map((cell) => (
                  <div role="cell" key={cell.id}
                       className={cn("truncate", (cell.column.columnDef as ColumnSpec<T>).align === "right" && "flex justify-end")}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
