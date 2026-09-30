import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { safeNext } from "./redirect";
import { useAuthConfig } from "./useAuthConfig";

/** « Continuer avec Google » puis le séparateur « ou » ; rien si Google n'est pas configuré. */
export function GoogleButton({ suite, remember }: { suite: string | null; remember: boolean }) {
  const config = useAuthConfig();
  if (!config?.google) return null;
  const query = new URLSearchParams({ suite: safeNext(suite), remember: remember ? "1" : "0" });
  return (
    <>
      <a href={`/api/auth/google/start?${query}`} className={cn(buttonVariants({ variant: "outline" }), "w-full gap-2 bg-white")}>
        <GoogleLogo />
        Continuer avec Google
      </a>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />ou<span className="h-px flex-1 bg-border" />
      </div>
    </>
  );
}

function GoogleLogo() {
  return (
    <svg viewBox="0 0 48 48" className="size-4" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.5 5.8c4.4-4 6.8-10 6.8-17.2z" />
      <path fill="#FBBC05" d="M10.6 28.6A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.8-4.6l-7.9-6.1A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.7l8-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.2 0-11.5-4.1-13.4-9.9l-8 6.1C6.6 42.6 14.6 48 24 48z" />
    </svg>
  );
}
