import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { Menu, Radar } from "lucide-react";
import { SITE_NAME } from "@/seo/schema";
// Le tiroir (et la bibliothèque des fenêtres) n'est chargé qu'au premier appui sur le menu.
const MobileDrawer = lazy(async () => ({ default: (await import("./MobileDrawer")).MobileDrawer }));

/** Sous 1024 px : barre du haut et menu en tiroir (la barre latérale est masquée). */
export function MobileHeader({ footer, account, admin = false }: { footer?: ReactNode; account?: ReactNode; admin?: boolean }) {
  const [open, setOpen] = useState(false);
  const [used, setUsed] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);  // changement de page (bouton retour compris) : tiroir fermé
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-2 border-b border-border bg-white px-2 lg:hidden">
      <button type="button" aria-label="Ouvrir le menu" aria-haspopup="dialog" aria-expanded={open} onClick={() => { setUsed(true); setOpen(true); }}
              className="flex size-11 items-center justify-center rounded-lg hover:bg-muted">
        <Menu className="size-5" aria-hidden />
      </button>
      <Link to="/" className="flex min-h-11 items-center gap-2 font-semibold tracking-tight">
        <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Radar className="size-4" aria-hidden />
        </span>
        {SITE_NAME}
      </Link>
      {used && (
        <Suspense fallback={null}>
          <MobileDrawer open={open} onOpenChange={setOpen} footer={footer} account={account} admin={admin} />
        </Suspense>
      )}
    </header>
  );
}
