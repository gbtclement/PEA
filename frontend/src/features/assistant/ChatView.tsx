import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useAssistantSettings, useConversation } from "./api";
import { ChatMessages } from "./ChatMessages";
import { Composer } from "./Composer";
import { GENERAL_SUGGESTIONS, SECURITY_SUGGESTIONS } from "./suggestions";
import { useChat } from "./useChat";

type Props = {
  conversationId: number | null;
  securityId?: number;
  securityName?: string;
  onConversationCreated: (id: number) => void;
  compact?: boolean;
};

export function ChatView({ conversationId, securityId, securityName, onConversationCreated, compact }: Props) {
  const settings = useAssistantSettings();
  // Garde l'id créé pendant l'envoi, même si le parent ne le renvoie pas tout de suite.
  const [currentId, setCurrentId] = useState(conversationId);
  const conversation = useConversation(currentId);
  const chat = useChat({
    conversationId: currentId,
    securityId,
    onConversationCreated: (id) => {
      setCurrentId(id);
      onConversationCreated(id);
    },
  });
  const bottom = useRef<HTMLDivElement>(null);
  const messages = conversation.data?.messages ?? [];
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, chat.pending?.text]);

  if (settings.isPending) return <Skeleton className="h-40 w-full" />;
  if (!settings.data?.configured) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-white p-6 text-sm">
        <p className="font-medium">L'assistant a besoin de votre clé API Claude.</p>
        <p className="mt-1 text-muted-foreground">
          Créez-la sur console.anthropic.com puis collez-la dans les Réglages. Elle reste chiffrée sur votre ordinateur.
        </p>
        <Link to="/reglages" className="mt-3 inline-block font-medium text-primary">Ouvrir les Réglages</Link>
      </div>
    );
  }
  const empty = messages.length === 0 && !chat.pending;
  const suggestions = securityId ? SECURITY_SUGGESTIONS : GENERAL_SUGGESTIONS;
  return (
    <div className={cn("flex min-h-0 flex-1 flex-col gap-4", compact ? "h-full" : "h-[calc(100vh-13rem)]")}>
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {empty ? (
          <div className="space-y-3 py-6">
            <p className="text-sm text-muted-foreground">
              {securityName ? `Posez une question sur ${securityName} :` : "Posez une question sur les marchés, un titre ou votre portefeuille :"}
            </p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button key={s} type="button" onClick={() => chat.send(s)}
                        className="rounded-full border border-border bg-white px-3 py-1.5 text-sm hover:border-primary hover:text-primary">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ChatMessages messages={messages} pending={chat.pending} streaming={chat.streaming} />
        )}
        <div ref={bottom} />
      </div>
      <Composer onSend={chat.send} onStop={chat.stop} streaming={chat.streaming} />
      <p className="text-center text-xs text-muted-foreground">Outil d'aide à la décision : ceci n'est pas un conseil en investissement.</p>
    </div>
  );
}
