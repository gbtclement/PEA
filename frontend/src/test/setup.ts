import "@testing-library/jest-dom/vitest";

// jsdom ne calcule aucune mise en page : on donne une taille aux éléments pour que les listes virtualisées s'affichent.
Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, get: () => 800 });
Object.defineProperty(HTMLElement.prototype, "offsetWidth", { configurable: true, get: () => 1200 });
