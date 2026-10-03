import { useSyncExternalStore } from "react";

const QUERY = "(max-width: 767px)";

/** Téléphone (moins de 768 px) : listes en cartes, fenêtres plein écran. Suit la rotation de l'écran. */
export function useIsMobile(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const mql = window.matchMedia(QUERY);
      mql.addEventListener("change", notify);
      return () => mql.removeEventListener("change", notify);
    },
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}
