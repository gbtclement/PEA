/** Ouvre une page Stripe (paiement ou portail) : navigation complète hors de l'application. Remplacé dans les tests. */
export function redirectTo(url: string): void {
  window.location.assign(url);
}
