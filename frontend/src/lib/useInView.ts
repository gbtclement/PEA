import { useEffect, useState, type RefObject } from "react";

/** Vrai dès que l'élément est entré (au moins une fois) dans l'écran, avec une marge : charger un graphique à la demande. */
export function useInView(ref: RefObject<Element | null>, rootMargin = "200px"): boolean {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element || seen) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setSeen(true);
        observer.disconnect();
      }
    }, { rootMargin });
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref, rootMargin, seen]);
  return seen;
}
