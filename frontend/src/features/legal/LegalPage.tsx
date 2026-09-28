import { usePageMeta } from "@/seo/usePageMeta";

type Kind = "cgu" | "confidentialite" | "mentions-legales";

const PAGES: Record<Kind, { title: string; description: string }> = {
  cgu: { title: "Conditions générales d'utilisation", description: "Les règles d'utilisation de PEA Radar." },
  confidentialite: { title: "Politique de confidentialité", description: "Comment PEA Radar protège vos données personnelles." },
  "mentions-legales": { title: "Mentions légales", description: "Éditeur et hébergeur de PEA Radar." },
};

/** Pages légales provisoires : le texte définitif sera rédigé avant l'ouverture publique. */
export function LegalPage({ kind }: { kind: Kind }) {
  const page = PAGES[kind];
  usePageMeta({ title: page.title, description: page.description });
  return (
    <article className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold">{page.title}</h1>
      <p className="text-sm text-muted-foreground">Version provisoire : le texte complet sera publié avant l'ouverture du site.</p>
      {kind === "cgu" && (
        <p className="text-sm">
          PEA Radar est un outil d'aide à la décision et d'apprentissage, pas un conseil en investissement. Les informations
          affichées (cours différés, scores, prévisions, éligibilité au PEA) peuvent être incomplètes ou inexactes : vérifiez-les
          auprès de votre banque avant tout ordre.
        </p>
      )}
    </article>
  );
}
