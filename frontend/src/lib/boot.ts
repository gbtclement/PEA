/**
 * Démarre l'application après le premier affichage du résumé préparé par l'API (pages publiques) :
 * le visiteur voit tout de suite le contenu, et React le remplace une image plus tard.
 * Sans résumé (#root vide), l'application démarre aussitôt.
 */
export function afterServerPaint(root: HTMLElement, start: () => void): void {
  if (!root.hasChildNodes()) {
    start();
    return;
  }
  // Une image d'écran pour peindre, puis le démarrage dans la tâche suivante
  requestAnimationFrame(() => setTimeout(start, 0));
}
