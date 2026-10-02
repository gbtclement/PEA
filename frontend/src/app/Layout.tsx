import { Link, Navigate, Outlet, useLocation } from "react-router";
import { Toaster } from "sonner";
import { AssistantPanelProvider } from "@/features/assistant/AssistantPanel";
import { useMe } from "@/features/auth/useMe";
import { AccountMenu } from "./AccountMenu";
import { MarketStatus } from "./MarketStatus";
import { Sidebar } from "./Sidebar";
import { SignUpBanner } from "./SignUpBanner";
import { SITE_NAME } from "@/seo/schema";

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
      <div className="min-h-screen min-w-[1024px] bg-background text-foreground">
        <Sidebar footer={<MarketStatus />} account={<AccountMenu />} admin={me?.role === "admin"} />
        <main className="ml-60 px-8 py-6">
          <div className="mx-auto max-w-[1400px]">
            <SignUpBanner />
            <Outlet />
          </div>
        </main>
        <footer className="ml-60 px-8 pb-6">
          <div className="mx-auto max-w-[1400px] space-y-1 border-t border-border pt-4 text-xs text-muted-foreground">
            <p>
              {SITE_NAME} est un outil d'aide à la décision et d'apprentissage, pas un conseil en investissement. Cours Yahoo Finance
              en différé ; compatibilité PEA déduite du pays du siège, à confirmer auprès de votre courtier.
            </p>
            <p className="flex flex-wrap gap-x-2">
              <Link to="/mentions-legales" className="hover:text-foreground">Mentions légales</Link>·
              <Link to="/cgu" className="hover:text-foreground">CGU</Link>·
              <Link to="/cgv" className="hover:text-foreground">CGV</Link>·
              <Link to="/confidentialite" className="hover:text-foreground">Confidentialité</Link>
            </p>
          </div>
        </footer>
        <Toaster position="bottom-right" richColors />
      </div>
    </AssistantPanelProvider>
  );
}
