import { createContext, lazy, Suspense, useContext, useState, type ReactNode } from "react";
import { Link } from "react-router";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

// Le chat (et react-markdown) n'est chargé qu'à la première ouverture du panneau.
const ChatView = lazy(async () => ({ default: (await import("./ChatView")).ChatView }));

type PanelSecurity = { id: number; name: string };
const PanelContext = createContext<{ open: (security: PanelSecurity) => void }>({ open: () => {} });

export const useAssistantPanel = () => useContext(PanelContext);

export function AssistantPanelProvider({ children }: { children: ReactNode }) {
  const [security, setSecurity] = useState<PanelSecurity | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isOpen, setOpen] = useState(false);
  function open(next: PanelSecurity) {
    if (next.id !== security?.id) setConversationId(null);  // autre titre : nouvelle conversation
    setSecurity(next);
    setOpen(true);
  }
  return (
    <PanelContext.Provider value={{ open }}>
      {children}
      <Sheet open={isOpen} onOpenChange={setOpen}>
        <SheetContent side="right" className="flex w-[520px] flex-col gap-3 sm:max-w-[520px] max-sm:data-[side=right]:w-full">
          <SheetHeader>
            <SheetTitle>Assistant IA — {security?.name}</SheetTitle>
            <SheetDescription>
              Claude a accès aux données de ce titre et à votre portefeuille.{" "}
              {conversationId !== null && (
                <Link to={`/assistant?c=${conversationId}`} onClick={() => setOpen(false)} className="text-primary">
                  Ouvrir dans la page Assistant
                </Link>
              )}
            </SheetDescription>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col px-4 pb-4">
            {security && (
              <Suspense fallback={null}>
                <ChatView key={security.id} compact conversationId={conversationId} securityId={security.id}
                          securityName={security.name} onConversationCreated={setConversationId} />
              </Suspense>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </PanelContext.Provider>
  );
}
