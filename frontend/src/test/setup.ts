import "@testing-library/jest-dom/vitest";

// jsdom ne calcule aucune mise en page : on donne une taille aux éléments pour que les listes virtualisées s'affichent.
Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, get: () => 800 });
Object.defineProperty(HTMLElement.prototype, "offsetWidth", { configurable: true, get: () => 1200 });
import "./viewport";

// jsdom n'a pas d'IntersectionObserver : par défaut, tout élément observé est tout de suite visible.
class VisibleObserver {
  private callback: IntersectionObserverCallback;
  constructor(callback: IntersectionObserverCallback) { this.callback = callback; }
  observe(target: Element) {
    this.callback([{ isIntersecting: true, target } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
  }
  unobserve() {}
  disconnect() {}
  takeRecords() { return []; }
}
Object.defineProperty(window, "IntersectionObserver", { configurable: true, writable: true, value: VisibleObserver });
