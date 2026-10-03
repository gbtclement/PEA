import { lazy, Suspense } from "react";
import { Link, Navigate, Outlet, useLocation } from "react-router";
import { AssistantPanelProvider } from "@/features/assistant/AssistantPanel";
import { useMe } from "@/features/auth/useMe";
import { AccountMenu } from "./AccountMenu";
import { MobileHeader } from "./MobileHeader";
import { MarketStatus } from "./MarketStatus";
import { Sidebar } from "./Sidebar";
import { SignUpBanner } from "./SignUpBanner";
import { SITE_NAME } from "@/seo/schema";

// Notifications « toast » : chargées juste après le premier affichage, pas avant.
const Toaster = lazy(async () => ({ default: (await import("sonner")).Toaster }));

// Lisibles avant d'accepter : on ne consent pas à un texte qu'on ne peut pas ouvrir.
const LEGAL_PAGES = ["/cgu", "/cgv", "/confidentialite", "/mentions-legales"];

export function Layout() {
  const { me } = useMe();
  const location = useLocation();
  if (me?.terms_outdated && !LEGAL_PAGES.includes(location.pathname)) {  // nouvelle version des CGU : l'accepter avant toute page
    return <Navigate to={`/accepter-cgu?suite=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }
  return (
    <AssistantPanelProvider>
      {/* Barre d'actions fixée en bas (fiche, téléphone) : place réservée sous le pied de page, qui reste lisible. */}
      <div className="min-h-screen bg-background text-foreground max-md:has-[[data-bottom-bar]]:pb-[calc(3.75rem+env(safe-area-inset-bottom))]">
        <MobileHeader footer={<MarketStatus />} account={<AccountMenu />} admin={me?.role === "admin"} />
        <Sidebar footer={<MarketStatus />} account={<AccountMenu />} admin={me?.role === "admin"} />
        <main className="px-4 py-4 md:px-8 md:py-6 lg:ml-60">
          <div className="mx-auto max-w-[1400px]">
            <SignUpBanner />
            <Outlet />
          </div>
        </main>
        <footer className="px-4 pb-6 md:px-8 lg:ml-60">
          <div className="mx-auto max-w-[1400px] space-y-1 border-t border-border pt-4 text-xs text-muted-foreground">
            <p>
              {SITE_NAME} est un outil d'aide à la décision et d'apprentissage, pas un conseil en investissement. Cours Yahoo Finance
              en différé ; enveloppes compatibles (PEA, PEA-PME) déduites automatiquement, à confirmer auprès de votre courtier.
            </p>
            <p className="flex flex-wrap gap-x-2">
              <Link to="/mentions-legales" className="hover:text-foreground">Mentions légales</Link>·
              <Link to="/cgu" className="hover:text-foreground">CGU</Link>·
              <Link to="/cgv" className="hover:text-foreground">CGV</Link>·
              <Link to="/confidentialite" className="hover:text-foreground">Confidentialité</Link>
            </p>
          </div>
        </footer>
        <Suspense fallback={null}><Toaster position="bottom-right" richColors /></Suspense>
      </div>
    </AssistantPanelProvider>
  );
}
