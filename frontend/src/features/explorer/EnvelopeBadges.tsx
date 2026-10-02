import { Badge } from "@/components/ui/badge";
import { ENVELOPE_LABELS } from "@/lib/envelopes";

/** Enveloppes où le titre est éligible (déduction automatique). Rien n'est affiché pour « à vérifier » ou « non éligible ». */
export function EnvelopeBadges({ codes }: { codes: string[] }) {
  return (
    <>
      {codes.map((code) => (
        <Badge key={code} variant="outline" className="border-green-200 bg-green-50 font-medium text-green-700">
          {ENVELOPE_LABELS[code] ?? code}
        </Badge>
      ))}
    </>
  );
}
