import { Sparkles } from "lucide-react";
import { useLocation, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { loginPath } from "@/features/auth/redirect";
import { useMe } from "@/features/auth/useMe";
import { useAssistantPanel } from "./AssistantPanel";

export function AskAiButton({ security, label = false }: { security: { id: number; name: string }; label?: boolean }) {
  const { open } = useAssistantPanel();
  const { me } = useMe();
  const navigate = useNavigate();
  const location = useLocation();
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
        // L'assistant est réservé aux comptes : un visiteur passe d'abord par la connexion.
        if (me === null) navigate(loginPath(location));
        else open(security);
      }}
    >
      <Sparkles className="size-4 text-primary" />
      {label && <span>Demander à l'IA</span>}
    </Button>
  );
}
