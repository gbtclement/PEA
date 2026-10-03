import type { ReactNode } from "react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { SidebarNav } from "./Sidebar";

type Props = { open: boolean; onOpenChange: (open: boolean) => void; footer?: ReactNode; account?: ReactNode; admin: boolean };

/** Menu en tiroir du téléphone (chargé au premier appui sur ☰). */
export function MobileDrawer({ open, onOpenChange, footer, account, admin }: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="gap-0 overflow-y-auto p-0 pt-14 data-[side=left]:w-72">
        <SheetTitle className="sr-only">Menu</SheetTitle>
        <SidebarNav admin={admin} account={account} onNavigate={() => onOpenChange(false)} />
        {footer && <div className="border-t border-border px-6 py-4">{footer}</div>}
      </SheetContent>
    </Sheet>
  );
}
