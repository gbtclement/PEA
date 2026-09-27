import { Outlet } from "react-router";
import { Toaster } from "sonner";
import { AssistantPanelProvider } from "@/features/assistant/AssistantPanel";
import { MarketStatus } from "./MarketStatus";
import { Sidebar } from "./Sidebar";

export function Layout() {
  return (
    <AssistantPanelProvider>
      <div className="min-h-screen min-w-[1280px] bg-background text-foreground">
        <Sidebar footer={<MarketStatus />} />
        <main className="ml-60 px-8 py-6">
          <div className="mx-auto max-w-[1400px]">
            <Outlet />
          </div>
        </main>
        <Toaster position="bottom-right" richColors />
      </div>
    </AssistantPanelProvider>
  );
}
