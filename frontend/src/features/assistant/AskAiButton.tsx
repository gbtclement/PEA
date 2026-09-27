import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAssistantPanel } from "./AssistantPanel";

export function AskAiButton({ security, label = false }: { security: { id: number; name: string }; label?: boolean }) {
  const { open } = useAssistantPanel();
  return (
    <Button
      type="button"
      variant={label ? "outline" : "ghost"}
      size={label ? "sm" : "icon"}
      aria-label={`Demander à l'IA à propos de ${security.name}`}
      title="Demander à l'IA"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        open(security);
      }}
    >
      <Sparkles className="size-4 text-primary" />
      {label && <span>Demander à l'IA</span>}
    </Button>
  );
}
