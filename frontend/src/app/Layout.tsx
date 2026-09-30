import { Outlet } from "react-router";
import { Toaster } from "sonner";
import { AssistantPanelProvider } from "@/features/assistant/AssistantPanel";
import { AccountMenu } from "./AccountMenu";
import { MarketStatus } from "./MarketStatus";
import { Sidebar } from "./Sidebar";
import { SignUpBanner } from "./SignUpBanner";

export function Layout() {
  return (
    <AssistantPanelProvider>
      <div className="min-h-screen min-w-[1024px] bg-background text-foreground">
        <Sidebar footer={<MarketStatus />} account={<AccountMenu />} />
        <main className="ml-60 px-8 py-6">
          <div className="mx-auto max-w-[1400px]">
            <SignUpBanner />
            <Outlet />
          </div>
        </main>
        <footer className="ml-60 px-8 pb-6">
          <p className="mx-auto max-w-[1400px] border-t border-border pt-4 text-xs text-muted-foreground">
            PEA Radar est un outil d'aide à la décision et d'apprentissage, pas un conseil en investissement. Cours Yahoo Finance
            en différé ; éligibilité PEA déduite du pays du siège, à confirmer auprès de votre banque.
          </p>
        </footer>
        <Toaster position="bottom-right" richColors />
      </div>
    </AssistantPanelProvider>
  );
}
