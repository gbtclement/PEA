import type { ReactNode } from "react";

/** Téléphone : actions de la fiche toujours à portée du pouce, au-dessus de la barre système (iPhone). */
export function MobileActionBar({ children }: { children: ReactNode }) {
  return (
    <div role="toolbar" aria-label="Actions sur ce titre" data-bottom-bar=""
         className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around gap-1 border-t border-border bg-white px-2 pt-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] md:hidden [&_button]:min-h-11">
      {children}
    </div>
  );
}
