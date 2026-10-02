/** Enveloppes d'investissement : mêmes codes que le registre du backend (services/envelopes/rules.py). */
export const ENVELOPE_LABELS: Record<string, string> = { pea: "PEA", pea_pme: "PEA-PME", cto: "Compte-titres" };
export const RULE_ENVELOPES = ["pea", "pea_pme"] as const;
export const STATUS_LABELS: Record<string, string> = { eligible: "Éligible", a_verifier: "À vérifier", non_eligible: "Non éligible" };

/** Enveloppes qui filtrent les titres : aucune si rien n'est choisi ou si le compte-titres (tout titre) est coché. */
export function filteringEnvelopes(codes: string[]): string[] {
  if (codes.includes("cto")) return [];
  return RULE_ENVELOPES.filter((code) => codes.includes(code));
}
