import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamSSE } from "@/lib/api/client";
import { createConversation } from "./api";

export type PendingTurn = { user: string; text: string; tools: string[]; error: string | null; interrupted: boolean };

type Options = { conversationId: number | null; securityId?: number; onConversationCreated: (id: number) => void };

/** Envoie une question et affiche la réponse au fil du flux, jusqu'à ce que la version enregistrée soit rechargée. */
export function useChat({ conversationId, securityId, onConversationCreated }: Options) {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [streaming, setStreaming] = useState(false);
  const controller = useRef<AbortController | null>(null);

  async function send(content: string) {
    setPending({ user: content, text: "", tools: [], error: null, interrupted: false });
    setStreaming(true);
    const abort = new AbortController();
    controller.current = abort;
    let id = conversationId;
    try {
      if (id === null) {
        id = (await createConversation(securityId)).id;
        onConversationCreated(id);
      } else {
        await queryClient.invalidateQueries({ queryKey: ["conversation", id] });  // efface une réponse interrompue affichée localement
      }
      await streamSSE(`/api/assistant/conversations/${id}/messages`, { content }, (event) => {
        if (event.type === "text") setPending((p) => p && { ...p, text: p.text + event.text });
        else if (event.type === "tool") setPending((p) => p && { ...p, tools: [...p.tools, event.label] });
        else if (event.type === "error") setPending((p) => p && { ...p, error: event.message, interrupted: true });
      }, abort.signal);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["conversation", id] }),
        queryClient.invalidateQueries({ queryKey: ["conversations"] }),
      ]);
      setPending(null);
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === "AbortError";
      setPending((p) => p && { ...p, interrupted: true, error: aborted ? null : (err as Error).message });
    } finally {
      setStreaming(false);
      controller.current = null;
    }
  }

  return { pending, streaming, send, stop: () => controller.current?.abort() };
}
