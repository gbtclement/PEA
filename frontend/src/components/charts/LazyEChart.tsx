import { lazy, Suspense, useRef, type ComponentProps } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { useInView } from "@/lib/useInView";

// ECharts pèse près de 200 Ko compressés : chargé seulement quand le graphique approche de l'écran.
const EChart = lazy(async () => ({ default: (await import("./EChart")).EChart }));

/** Graphique ECharts chargé à la demande ; l'emplacement garde sa taille (pas de décalage de la page). */
export function LazyEChart(props: ComponentProps<typeof EChart>) {
  const ref = useRef<HTMLDivElement>(null);
  const visible = useInView(ref);
  const placeholder = <Skeleton className={props.className} aria-hidden />;
  return (
    <div ref={ref}>
      {visible ? <Suspense fallback={placeholder}><EChart {...props} /></Suspense> : placeholder}
    </div>
  );
}
