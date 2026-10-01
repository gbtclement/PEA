import { Link, useLocation } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { useMe } from "@/features/auth/useMe";
import { cn } from "@/lib/utils";

const LEGAL_PAGES = ["/cgu", "/cgv", "/confidentialite", "/mentions-legales"];

/** Invitation discrète à créer un compte, pour les visiteurs seulement. */
export function SignUpBanner() {
  const { me } = useMe();
  const { pathname } = useLocation();
  if (me !== null || LEGAL_PAGES.includes(pathname)) return null;
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3">
      <p className="text-sm">Créez un compte gratuit pour suivre votre portefeuille, vos favoris et vos alertes.</p>
      <div className="flex items-center gap-3">
        <Link to="/connexion" className="text-sm font-medium text-primary">Se connecter</Link>
        <Link to="/inscription" className={cn(buttonVariants({ size: "sm" }))}>Créer un compte gratuit</Link>
      </div>
    </div>
  );
}
