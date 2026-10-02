import { usePageMeta } from "@/seo/usePageMeta";
import { CGU, CGV, LEGAL_UPDATED, NOTICE, PRIVACY } from "./content";
import { SITE_NAME } from "@/seo/schema";

type Kind = "cgu" | "cgv" | "confidentialite" | "mentions-legales";

const PAGES: Record<Kind, { title: string; description: string; Body: () => React.JSX.Element }> = {
  cgu: { title: "Conditions générales d'utilisation", description: `Les règles d'utilisation de ${SITE_NAME}.`, Body: CGU },
  cgv: { title: "Conditions générales de vente", description: `Les conditions de l'abonnement ${SITE_NAME} Premium.`, Body: CGV },
  confidentialite: { title: "Politique de confidentialité", description: `Comment ${SITE_NAME} protège vos données personnelles.`, Body: PRIVACY },
  "mentions-legales": { title: "Mentions légales", description: `Éditeur et hébergeur de ${SITE_NAME}.`, Body: NOTICE },
};

export function LegalPage({ kind }: { kind: Kind }) {
  const { title, description, Body } = PAGES[kind];
  usePageMeta({ title, description });
  return (
    <article className="max-w-3xl space-y-6 text-sm leading-relaxed">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-muted-foreground">Dernière mise à jour : {LEGAL_UPDATED}</p>
      </header>
      <p role="note" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
        Brouillon : les passages entre crochets restent à compléter, et une relecture par un professionnel est conseillée avant
        l'ouverture publique.
      </p>
      <Body />
    </article>
  );
}
