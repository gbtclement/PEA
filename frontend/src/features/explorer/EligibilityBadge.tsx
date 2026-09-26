import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STYLES: Record<string, { label: string; className: string }> = {
  eligible: { label: "Éligible PEA", className: "border-green-200 bg-green-50 text-green-700" },
  a_verifier: { label: "À vérifier", className: "border-amber-200 bg-amber-50 text-amber-700" },
  non_eligible: { label: "Non éligible", className: "border-zinc-200 bg-zinc-50 text-zinc-500" },
};

export function EligibilityBadge({ status }: { status: string }) {
  const style = STYLES[status] ?? STYLES.a_verifier;
  return <Badge variant="outline" className={cn("font-medium", style.className)}>{style.label}</Badge>;
}
