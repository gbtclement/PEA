import { lazy, Suspense } from "react";
import { Link } from "react-router";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

// Le chat (et react-markdown) n'est chargé qu'à la première ouverture du panneau.
const ChatView = lazy(async () => ({ default: (await import("./ChatView")).ChatView }));

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  security: { id: number; name: string } | null;
  conversationId: number | null;
  onConversationCreated: (id: number) => void;
};

/** Panneau latéral de l'assistant (chargé à la première ouverture, comme le chat qu'il contient). */
export function AssistantSheet({ open, onOpenChange, security, conversationId, onConversationCreated }: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-[520px] flex-col gap-3 sm:max-w-[520px] max-sm:data-[side=right]:w-full">
        <SheetHeader>
          <SheetTitle>Assistant IA — {security?.name}</SheetTitle>
          <SheetDescription>
            Claude a accès aux données de ce titre et à votre portefeuille.{" "}
            {conversationId !== null && (
              <Link to={`/assistant?c=${conversationId}`} onClick={() => onOpenChange(false)} className="text-primary">
                Ouvrir dans la page Assistant
              </Link>
            )}
          </SheetDescription>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col px-4 pb-4">
          {security && (
            <Suspense fallback={null}>
              <ChatView key={security.id} compact conversationId={conversationId} securityId={security.id}
                        securityName={security.name} onConversationCreated={onConversationCreated} />
            </Suspense>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
