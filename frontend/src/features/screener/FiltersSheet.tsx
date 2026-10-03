import { useState, type ReactNode } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";

/** Téléphone : tri et filtres dans un panneau plein écran (ils restent dans l'URL). */
export function FiltersSheet({ children, active }: { children: ReactNode; active: number }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="outline" className="min-h-11" onClick={() => setOpen(true)}>
        <SlidersHorizontal className="size-4" aria-hidden /> Filtres{active ? ` (${active})` : ""}
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="bottom" className="overflow-y-auto p-4 data-[side=bottom]:h-dvh">
          <SheetTitle>Filtres</SheetTitle>
          <div className="flex flex-col gap-3 [&_input:not([type=checkbox])]:min-h-11 [&_input:not([type=checkbox])]:w-full [&_select]:min-h-11 [&_select]:w-full">
            {children}
          </div>
          <Button className="mt-4 min-h-11" onClick={() => setOpen(false)}>Voir les résultats</Button>
        </SheetContent>
      </Sheet>
    </>
  );
}
