import { Radar } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthFooter } from "./AuthFooter";
import { SignInForm } from "./SignInForm";
import { SignUpForm } from "./SignUpForm";

type Mode = "inscription" | "connexion";

const PANEL = {
  inscription: { title: "Déjà un compte ?", text: "Retrouvez votre portefeuille, vos favoris et vos alertes.", action: "Se connecter" },
  connexion: { title: "Pas encore de compte ?", text: "Créez votre compte gratuit pour suivre votre PEA en quelques minutes.", action: "S'inscrire" },
};

export function AuthPage({ mode }: { mode: Mode }) {
  const signUp = mode === "inscription";
  usePageMeta({
    title: signUp ? "Créer un compte" : "Se connecter",
    description: "Créez votre compte PEA Radar ou connectez-vous pour suivre votre portefeuille PEA.",
  });
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const other = signUp ? "/connexion" : "/inscription";
  const panel = PANEL[mode];

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-background via-background to-primary/10 text-foreground">
      <nav aria-label="Navigation principale" className="px-4 py-4 sm:px-8">
        <Link to="/" className="inline-flex items-center gap-2 text-sm font-semibold">
          <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Radar className="size-4" aria-hidden /></span>
          PEA Radar
        </Link>
      </nav>
      <main className="flex flex-1 items-center justify-center px-4 py-6">
        <div className="relative w-full max-w-[960px] overflow-hidden rounded-2xl bg-white shadow-xl md:h-[600px]">
          {/* Panneau indigo : bandeau en haut sur mobile, moitié qui glisse sur grand écran */}
          <aside className={cn("auth-panel relative z-20 flex flex-col justify-center gap-4 bg-primary p-8 text-primary-foreground",
                               "md:absolute md:inset-y-0 md:w-1/2", signUp ? "md:translate-x-full" : "md:translate-x-0")}>
            <p className="text-2xl font-semibold">{panel.title}</p>
            <p className="text-sm text-primary-foreground/80">{panel.text}</p>
            <MiniChart />
            <Button variant="outline" className="w-fit border-white/60 bg-transparent text-white hover:bg-white/10 hover:text-white"
                    onClick={() => navigate({ pathname: other, search: params.toString() ? `?${params}` : "" })}>
              {panel.action}
            </Button>
          </aside>
          <div className="grid md:h-full md:grid-cols-2">
            <section aria-hidden={!signUp} inert={!signUp} className={cn("auth-form p-8 md:col-start-1 md:row-start-1", !signUp && "hidden md:block md:opacity-0")}>
              {signUp && <SignUpForm />}
            </section>
            <section aria-hidden={signUp} inert={signUp} className={cn("auth-form p-8 md:col-start-2 md:row-start-1", signUp && "hidden md:block md:opacity-0")}>
              {!signUp && <SignInForm />}
            </section>
          </div>
        </div>
      </main>
      <AuthFooter />
    </div>
  );
}

/** Courbe de cours stylisée, décorative. */
function MiniChart() {
  return (
    <svg viewBox="0 0 200 60" className="h-16 w-full max-w-xs text-white/70" aria-hidden>
      <polyline fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                points="0,50 25,44 45,47 70,32 95,36 120,22 145,26 170,12 200,8" />
    </svg>
  );
}
