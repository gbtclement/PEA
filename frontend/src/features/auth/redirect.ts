/** Chemin interne sûr pour revenir après la connexion ; tout le reste renvoie à l'accueil (pas de redirection ouverte). */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return "/";
  return value;
}

export function loginPath({ pathname, search }: { pathname: string; search: string }): string {
  return `/connexion?suite=${encodeURIComponent(pathname + search)}`;
}

/** Sites Docsify servis par nginx hors du routeur React : il faut une navigation complète pour les ouvrir. */
export function isExternalSuite(path: string): boolean {
  return /^\/(documentation|guide)\//.test(path);
}
