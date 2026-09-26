import { Star } from "lucide-react";
import { useToggleFavorite } from "@/features/favorites/useToggleFavorite";
import { cn } from "@/lib/utils";

export function FavoriteButton({ securityId, isFavorite }: { securityId: number; isFavorite: boolean }) {
  const toggle = useToggleFavorite();
  return (
    <button
      type="button"
      aria-pressed={isFavorite}
      aria-label={isFavorite ? "Retirer des favoris" : "Ajouter aux favoris"}
      onClick={(event) => {
        event.stopPropagation();
        toggle.mutate({ securityId, favorite: !isFavorite });
      }}
      className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-amber-500"
    >
      <Star className={cn("size-4", isFavorite && "fill-amber-400 text-amber-500")} />
    </button>
  );
}
