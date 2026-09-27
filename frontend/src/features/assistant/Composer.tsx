import { useState } from "react";
import { Button } from "@/components/ui/button";

type Props = { onSend: (text: string) => void; onStop: () => void; streaming: boolean };

export function Composer({ onSend, onStop, streaming }: Props) {
  const [text, setText] = useState("");
  function submit() {
    const value = text.trim();
    if (!value || streaming) return;
    setText("");
    onSend(value);
  }
  return (
    <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <textarea
        aria-label="Votre question"
        rows={2}
        maxLength={4000}
        value={text}
        placeholder="Posez votre question… (Entrée pour envoyer, Maj+Entrée pour aller à la ligne)"
        className="min-h-[44px] flex-1 resize-none rounded-lg border border-input bg-white px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
      />
      {streaming
        ? <Button type="button" variant="outline" onClick={onStop}>Arrêter</Button>
        : <Button type="submit" disabled={!text.trim()}>Envoyer</Button>}
    </form>
  );
}
