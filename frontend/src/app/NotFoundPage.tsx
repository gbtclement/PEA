import { Link } from "react-router";
import { DEFAULT_DESCRIPTION } from "@/seo/schema";
import { usePageMeta } from "@/seo/usePageMeta";

export function NotFoundPage() {
  usePageMeta({ title: "Page introuvable", description: DEFAULT_DESCRIPTION, noindex: true });
  return (
    <section className="py-20 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Page introuvable</h1>
      <p className="mt-2 text-sm text-muted-foreground">Cette adresse ne correspond à aucune page de PEA Radar.</p>
      <Link to="/" className="mt-4 inline-block text-sm font-medium text-primary">Retour à l'accueil</Link>
    </section>
  );
}
