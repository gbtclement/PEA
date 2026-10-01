import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import type { AssistantStatus } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { useAssistantStatus, useConversation } from "./api";
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
  const status = useAssistantStatus();
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

  if (status.isPending) return <Skeleton className="h-40 w-full" />;
  if (status.data && !status.data.available) return <Unavailable status={status.data} />;
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
      {status.data && (
        <p className="text-center text-xs text-muted-foreground">
          Modèle : {status.data.model} · ce mois-ci : {usd(status.data.spent_usd)} $ sur {usd(status.data.limit_usd)} $
        </p>
      )}
      <p className="text-center text-xs text-muted-foreground">
        Vos questions sont envoyées à Anthropic (États-Unis) pour y répondre.{" "}
        <Link className="underline" to="/confidentialite">En savoir plus</Link>
      </p>
      <p className="text-center text-xs text-muted-foreground">Outil d'aide à la décision : ceci n'est pas un conseil en investissement.</p>
    </div>
  );
}

const usd = (value: number) => value.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const UNAVAILABLE = {
  premium: {
    title: "Réservé aux membres Premium",
    text: "L'assistant IA fait partie de l'offre Premium. L'abonnement arrivera bientôt ; en attendant, l'administrateur peut activer Premium sur votre compte.",
  },
  not_configured: {
    title: "Assistant pas encore configuré",
    text: "La clé Claude n'est pas encore renseignée sur le serveur. L'administrateur doit l'ajouter dans le fichier .env (ANTHROPIC_API_KEY).",
  },
  limit_reached: { title: "Limite du mois atteinte", text: "" },
} as const;

function Unavailable({ status }: { status: AssistantStatus }) {
  const copy = UNAVAILABLE[status.reason ?? "premium"];
  return (
    <div className="rounded-xl border border-dashed border-border bg-white p-6 text-sm">
      <p className="font-medium">{copy.title}</p>
      <p className="mt-1 text-muted-foreground">
        {status.reason === "limit_reached"
          ? `Vous avez utilisé ${usd(status.spent_usd)} $ sur ${usd(status.limit_usd)} $ ce mois-ci. L'assistant sera de nouveau disponible le 1er du mois prochain.`
          : copy.text}
      </p>
    </div>
  );
}
