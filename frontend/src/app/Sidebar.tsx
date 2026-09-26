import type { ReactNode } from "react";
import { NavLink } from "react-router";
import { House, Layers, Radar, Search, Settings, Sparkles, Wallet } from "lucide-react";
import { cn } from "@/lib/utils";

export const NAV_ITEMS = [
  { to: "/", label: "Accueil", icon: House, end: true },
  { to: "/explorer", label: "Explorer", icon: Search, end: false },
  { to: "/etf", label: "ETF", icon: Layers, end: false },
  { to: "/portefeuille", label: "Portefeuille", icon: Wallet, end: false },
  { to: "/assistant", label: "Assistant IA", icon: Sparkles, end: false },
  { to: "/reglages", label: "Réglages", icon: Settings, end: false },
];

export function Sidebar({ footer }: { footer?: ReactNode }) {
  return (
    <aside className="fixed inset-y-0 left-0 flex w-60 flex-col border-r border-border bg-white">
      <div className="flex items-center gap-2.5 px-6 py-5">
        <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Radar className="size-4" aria-hidden />
        </div>
        <span className="text-lg font-semibold tracking-tight">PEA Radar</span>
      </div>
      <nav aria-label="Navigation principale" className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>
      {footer && <div className="border-t border-border px-6 py-4">{footer}</div>}
    </aside>
  );
}
