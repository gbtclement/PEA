import { Star } from "lucide-react";
import { useLocation, useNavigate } from "react-router";
import { loginPath } from "@/features/auth/redirect";
import { useMe } from "@/features/auth/useMe";
import { useToggleFavorite } from "@/features/favorites/useToggleFavorite";
import { cn } from "@/lib/utils";

export function FavoriteButton({ securityId, isFavorite }: { securityId: number; isFavorite: boolean }) {
  const toggle = useToggleFavorite();
  const { me } = useMe();
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <button
      type="button"
      aria-pressed={isFavorite}
      aria-label={isFavorite ? "Retirer des favoris" : "Ajouter aux favoris"}
      onClick={(event) => {
        event.stopPropagation();
        // Les favoris sont personnels : un visiteur passe d'abord par la connexion.
        if (me === null) {
          navigate(loginPath(location));
          return;
        }
        toggle.mutate({ securityId, favorite: !isFavorite });
      }}
      className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-amber-500"
    >
      <Star className={cn("size-4", isFavorite && "fill-amber-400 text-amber-500")} />
    </button>
  );
}
