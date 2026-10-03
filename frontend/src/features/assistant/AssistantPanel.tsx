import { createContext, lazy, Suspense, useContext, useState, type ReactNode } from "react";

// Panneau (et bibliothèque des fenêtres) chargé au premier clic sur ✨ : rien de plus au premier affichage des pages.
const AssistantSheet = lazy(async () => ({ default: (await import("./AssistantSheet")).AssistantSheet }));

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
      {security && (
        <Suspense fallback={null}>
          <AssistantSheet open={isOpen} onOpenChange={setOpen} security={security} conversationId={conversationId}
                          onConversationCreated={setConversationId} />
        </Suspense>
      )}
    </PanelContext.Provider>
  );
}
