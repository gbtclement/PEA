import { useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useConversations, useDeleteConversation } from "./api";
import { ChatView } from "./ChatView";

const formatCost = (usd: number) => `≈ ${usd.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} $`;

export function AssistantPage() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("c") ? Number(params.get("c")) : null;
  const conversations = useConversations();
  const remove = useDeleteConversation();
  // Le chat suit l'adresse (liens, retour arrière), sauf quand l'adresse change parce qu'il vient lui-même
  // de créer la conversation : le recréer couperait la réponse en cours.
  const created = useRef<number | null>(null);
  const shown = useRef<number | null>(selected);
  if (selected !== shown.current && (created.current === null || selected !== created.current)) {
    shown.current = selected;
    created.current = null;
  }
  const [resets, setResets] = useState(0);
  const onCreated = (id: number) => {
    created.current = id;
    setParams({ c: String(id) }, { replace: true });
  };
  const select = (id: number | null) => {
    setResets((n) => n + 1);  // « Nouvelle conversation » repart de zéro même si l'adresse ne change pas
    setParams(id === null ? {} : { c: String(id) });
  };
  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Assistant IA</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Claude répond en s'appuyant sur les données de l'application (cours, scores, votre portefeuille) et sur l'actualité.
        </p>
      </header>
      <div className="grid grid-cols-[280px_1fr] gap-6">
        <Card className="h-[calc(100vh-11rem)] gap-0 overflow-y-auto p-3">
          <Button className="mb-3 w-full" onClick={() => select(null)}>+ Nouvelle conversation</Button>
          <ul className="space-y-1">
            {conversations.data?.map((c) => (
              <li key={c.id} className={cn("group flex items-center rounded-lg", c.id === selected ? "bg-accent" : "hover:bg-muted")}>
                <button type="button" onClick={() => select(c.id)} className="min-w-0 flex-1 px-3 py-2 text-left">
                  <p className="truncate text-sm font-medium">{c.title}</p>
                  <p className="text-xs text-muted-foreground">{new Date(c.updated_at).toLocaleDateString("fr-FR")} · {formatCost(c.cost_usd)}</p>
                </button>
                <button
                  type="button"
                  aria-label={`Supprimer la conversation ${c.title}`}
                  className="mr-2 rounded p-1 text-muted-foreground opacity-0 hover:text-down focus:opacity-100 group-hover:opacity-100"
                  onClick={() => {
                    if (window.confirm("Supprimer cette conversation ?")) {
                      remove.mutate(c.id, { onSuccess: () => { if (c.id === selected) select(null); } });
                    }
                  }}
                >
                  <Trash2 className="size-4" />
                </button>
              </li>
            ))}
            {conversations.data?.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">Aucune conversation pour l'instant.</li>}
          </ul>
        </Card>
        <Card className="p-5">
          <ChatView key={`${shown.current}-${resets}`} conversationId={shown.current ?? selected} onConversationCreated={onCreated} />
        </Card>
      </div>
    </section>
  );
}
