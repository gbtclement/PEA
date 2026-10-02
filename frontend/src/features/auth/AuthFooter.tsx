import { Link } from "react-router";
import { SITE_NAME } from "@/seo/schema";

/** Liens légaux communs à tous les écrans de compte. */
export function AuthFooter() {
  return (
    <footer className="space-y-1 px-4 py-6 text-center text-xs text-muted-foreground">
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
        <Link to="/mentions-legales" className="hover:text-foreground">Mentions légales</Link>
        <Link to="/cgu" className="hover:text-foreground">CGU</Link>
        <Link to="/cgv" className="hover:text-foreground">CGV</Link>
        <Link to="/confidentialite" className="hover:text-foreground">Confidentialité</Link>
        <a href="/guide/" className="hover:text-foreground">Guide</a>
      </div>
      <p>{SITE_NAME} est un outil d'aide à la décision, pas un conseil en investissement.</p>
    </footer>
  );
}
