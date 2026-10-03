import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { Menu, Radar } from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { SITE_NAME } from "@/seo/schema";
import { SidebarNav } from "./Sidebar";

/** Sous 1024 px : barre du haut et menu en tiroir (la barre latérale est masquée). */
export function MobileHeader({ footer, account, admin = false }: { footer?: ReactNode; account?: ReactNode; admin?: boolean }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);  // changement de page (bouton retour compris) : tiroir fermé
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-2 border-b border-border bg-white px-2 lg:hidden">
      <button type="button" aria-label="Ouvrir le menu" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}
              className="flex size-11 items-center justify-center rounded-lg hover:bg-muted">
        <Menu className="size-5" aria-hidden />
      </button>
      <Link to="/" className="flex min-h-11 items-center gap-2 font-semibold tracking-tight">
        <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Radar className="size-4" aria-hidden />
        </span>
        {SITE_NAME}
      </Link>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="gap-0 overflow-y-auto p-0 pt-14 data-[side=left]:w-72">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <SidebarNav admin={admin} account={account} onNavigate={() => setOpen(false)} />
          {footer && <div className="border-t border-border px-6 py-4">{footer}</div>}
        </SheetContent>
      </Sheet>
    </header>
  );
}
