import type { MessageOut } from "@/lib/api/client";
import { Markdown } from "./Markdown";
import { TOOL_NAMES } from "./suggestions";
import type { PendingTurn } from "./useChat";

function UserBubble({ text }: { text: string }) {
  return (
    <div className="ml-auto w-fit max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-primary-foreground">
      {text}
    </div>
  );
}

type AssistantProps = { text: string; tools: string[]; interrupted: boolean; error: string | null; loading?: boolean };

function AssistantBubble({ text, tools, interrupted, error, loading }: AssistantProps) {
  return (
    <div className="max-w-[92%] space-y-2">
      {tools.length > 0 && <p className="text-xs text-muted-foreground">🔎 A consulté : {[...new Set(tools)].join(", ")}</p>}
      {text ? <Markdown text={text} /> : loading && <p className="animate-pulse text-sm text-muted-foreground">Réflexion en cours…</p>}
      {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-down">{error}</p>}
      {interrupted && <p className="text-xs italic text-muted-foreground">réponse interrompue</p>}
    </div>
  );
}

export function ChatMessages({ messages, pending, streaming }: { messages: MessageOut[]; pending: PendingTurn | null; streaming: boolean }) {
  return (
    <div className="space-y-4">
      {messages.map((m) => m.role === "user"
        ? <UserBubble key={m.id} text={m.content} />
        : <AssistantBubble key={m.id} text={m.content} tools={m.tools.map((t) => TOOL_NAMES[t] ?? t)} interrupted={m.interrupted} error={m.error} />)}
      {pending && (
        <>
          <UserBubble text={pending.user} />
          <AssistantBubble text={pending.text} tools={pending.tools} interrupted={pending.interrupted} error={pending.error} loading={streaming} />
        </>
      )}
    </div>
  );
}
