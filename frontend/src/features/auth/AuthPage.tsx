import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthBrand } from "./AuthCard";
import { AuthFooter } from "./AuthFooter";
import { SignInForm } from "./SignInForm";
import { SignUpForm } from "./SignUpForm";

type Mode = "inscription" | "connexion";

const PANEL = {
  inscription: { title: "Déjà un compte ?", text: "Retrouvez votre portefeuille, vos favoris et vos alertes.", action: "Se connecter" },
  connexion: { title: "Pas encore de compte ?", text: "Créez votre compte gratuit pour suivre votre PEA en quelques minutes.", action: "S'inscrire" },
};
const MODES: Mode[] = ["inscription", "connexion"];
const SWITCH_MS = 700; // durée du glissement du panneau (voir .auth-panel dans index.css)

/**
 * Route commune à /inscription et /connexion : la page reste montée d'une adresse à l'autre,
 * sinon React la recréerait déjà en place et le panneau ne glisserait pas.
 */
export function AuthRoute() {
  const { pathname } = useLocation();
  return <AuthPage mode={pathname.startsWith("/inscription") ? "inscription" : "connexion"} />;
}

export function AuthPage({ mode }: { mode: Mode }) {
  const signUp = mode === "inscription";
  usePageMeta({
    title: signUp ? "Créer un compte" : "Se connecter",
    description: "Créez votre compte PEA Radar ou connectez-vous pour suivre votre portefeuille PEA.",
  });
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const other = signUp ? "/connexion" : "/inscription";

  // Le formulaire qui part reste affiché le temps de s'effacer pendant que le panneau passe dessus.
  const [current, setCurrent] = useState(mode);
  const [leaving, setLeaving] = useState<Mode | null>(null);
  if (mode !== current) {
    setLeaving(current);
    setCurrent(mode);
  }
  useEffect(() => {
    if (!leaving) return;
    const timer = setTimeout(() => setLeaving(null), SWITCH_MS);
    return () => clearTimeout(timer);
  }, [leaving]);

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-background via-background to-primary/10 text-foreground">
      <AuthBrand />
      <main className="flex flex-1 items-center justify-center px-4 py-6">
        <div className="relative w-full max-w-[960px] overflow-hidden rounded-2xl bg-white shadow-xl md:h-[600px]">
          {/* Panneau indigo : bandeau en haut sur mobile, moitié qui glisse sur grand écran */}
          <aside className={cn("auth-panel relative z-20 flex flex-col justify-center gap-6 overflow-hidden bg-primary p-8 text-primary-foreground",
                               "md:absolute md:inset-y-0 md:w-1/2", signUp ? "md:translate-x-full" : "md:translate-x-0")}>
            <PanelGlow />
            <div className="relative grid">
              {MODES.map((m) => (
                <div key={m} aria-hidden={m !== mode} inert={m !== mode}
                     className={cn("auth-panel-text col-start-1 row-start-1 flex flex-col gap-3", m === mode && "is-active")}>
                  <p className="text-2xl font-semibold">{PANEL[m].title}</p>
                  <p className="max-w-xs text-sm text-primary-foreground/80">{PANEL[m].text}</p>
                  <Button variant="outline" className="mt-1 w-fit border-white/60 bg-transparent text-white hover:bg-white/10 hover:text-white"
                          onClick={() => navigate({ pathname: other, search: params.toString() ? `?${params}` : "" })}>
                    {PANEL[m].action}
                  </Button>
                </div>
              ))}
            </div>
            <PanelArt replay={mode} />
          </aside>
          <div className="grid md:h-full md:grid-cols-2">
            {MODES.map((m) => {
              const active = m === mode;
              return (
                <section key={m} aria-hidden={!active} inert={!active}
                         className={cn("auth-form p-8 md:row-start-1", m === "inscription" ? "auth-form-left md:col-start-1" : "auth-form-right md:col-start-2",
                                       active ? "is-active" : "max-md:hidden")}>
                  {(active || leaving === m) && (m === "inscription" ? <SignUpForm /> : <SignInForm />)}
                </section>
              );
            })}
          </div>
        </div>
      </main>
      <AuthFooter />
    </div>
  );
}

/** Halos lumineux décoratifs au fond du panneau. */
function PanelGlow() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      <div className="absolute -right-24 -top-24 size-72 rounded-full bg-white/10 blur-3xl" />
      <div className="absolute -bottom-32 -left-16 size-80 rounded-full bg-indigo-300/20 blur-3xl" />
    </div>
  );
}

/** Mini tableau de bord stylisé, décoratif : courbe qui se dessine, bougies, compteur d'ordres. */
function PanelArt({ replay }: { replay: Mode }) {
  const candles = [
    { x: 18, open: 70, close: 58, high: 52, low: 76 }, { x: 36, open: 60, close: 66, high: 55, low: 72 },
    { x: 54, open: 64, close: 50, high: 44, low: 68 }, { x: 72, open: 52, close: 42, high: 36, low: 56 },
    { x: 90, open: 44, close: 48, high: 38, low: 54 }, { x: 108, open: 46, close: 34, high: 28, low: 50 },
    { x: 126, open: 36, close: 26, high: 20, low: 40 },
  ];
  return (
    <div aria-hidden className="auth-art relative hidden w-full max-w-sm sm:block">
      <div className="rounded-xl border border-white/20 bg-white/10 p-4 shadow-2xl backdrop-blur-sm">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className="font-medium">Mon PEA</span>
          <span className="rounded-full bg-emerald-400/20 px-2 py-0.5 font-semibold text-emerald-200">+12,4 %</span>
        </div>
        <svg key={replay} viewBox="0 0 280 90" className="h-24 w-full">
          <defs>
            <linearGradient id="auth-area" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="white" stopOpacity="0.35" />
              <stop offset="100%" stopColor="white" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[22, 45, 68].map((y) => <line key={y} x1="0" x2="280" y1={y} y2={y} stroke="white" strokeOpacity="0.12" />)}
          {candles.map((c) => (
            <g key={c.x} className="auth-candle" style={{ animationDelay: `${c.x * 4}ms` }}>
              <line x1={c.x} x2={c.x} y1={c.high} y2={c.low} stroke="white" strokeOpacity="0.55" />
              <rect x={c.x - 4} width="8" y={Math.min(c.open, c.close)} height={Math.max(2, Math.abs(c.open - c.close))} rx="1.5"
                    className={c.close < c.open ? "fill-emerald-300" : "fill-rose-300"} />
            </g>
          ))}
          <path d="M140 40 C160 44 170 30 190 32 S220 18 240 20 S265 8 280 6 L280 90 L140 90 Z" fill="url(#auth-area)" className="auth-area" />
          <path d="M140 40 C160 44 170 30 190 32 S220 18 240 20 S265 8 280 6" fill="none" stroke="white" strokeWidth="2.5"
                strokeLinecap="round" pathLength={1} className="auth-line" />
          <circle cx="280" cy="6" r="4" className="auth-dot fill-white" />
        </svg>
        <div className="mt-3 flex items-center gap-3 text-xs">
          <span className="text-primary-foreground/80">Ordres 2026</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/15">
            <div className="auth-bar h-full w-2/3 rounded-full bg-white" />
          </div>
          <span className="font-semibold">8/12</span>
        </div>
      </div>
      <span className="auth-badge absolute -right-3 -top-3 rounded-full bg-white px-3 py-1 text-xs font-semibold text-primary shadow-lg">
        ✓ Éligible PEA
      </span>
    </div>
  );
}
