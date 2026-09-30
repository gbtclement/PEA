import { Sparkles } from "lucide-react";
import { Link } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** À la place d'une fonction réservée à Premium (spec 2) : le serveur refuse de toute façon ces données (403). */
export function PremiumCard({ feature, compact = false }: { feature: string; compact?: boolean }) {
  return (
    <div role="note" className={cn("rounded-xl border border-dashed border-primary/40 bg-primary/5 text-sm", compact ? "p-4" : "p-6")}>
      <p className="flex items-center gap-2 font-medium">
        <Sparkles className="size-4 text-primary" aria-hidden />
        Réservé aux membres Premium
      </p>
      <p className="mt-1 text-muted-foreground">{feature} fait partie de l'offre Premium, avec l'assistant IA et les prévisions court terme.</p>
      <Link to="/premium" className={cn(buttonVariants({ size: "sm" }), "mt-3")}>Découvrir Premium</Link>
    </div>
  );
}
