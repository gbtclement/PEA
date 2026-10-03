import type { ReactNode } from "react";
import { Radar } from "lucide-react";
import { Link } from "react-router";
import { AuthFooter } from "./AuthFooter";
import { SITE_NAME } from "@/seo/schema";

/** Logo cliquable en haut des écrans de compte. */
export function AuthBrand() {
  return (
    <nav aria-label="Navigation principale" className="px-4 py-4 sm:px-8">
      <Link to="/" className="inline-flex items-center gap-2 text-sm font-semibold">
        <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Radar className="size-4" aria-hidden /></span>
        {SITE_NAME}
      </Link>
    </nav>
  );
}

/** Cadre des écrans de compte secondaires (code, mot de passe…) : même fond que la connexion, carte centrée. */
export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-background via-background to-primary/10 text-foreground">
      <AuthBrand />
      <main className="flex flex-1 items-center justify-center px-4 py-6">
        <div className="w-full max-w-[480px] space-y-4 rounded-2xl bg-white p-5 shadow-xl sm:p-8">
          <h1 className="text-2xl font-semibold">{title}</h1>
          {children}
        </div>
      </main>
      <AuthFooter />
    </div>
  );
}
