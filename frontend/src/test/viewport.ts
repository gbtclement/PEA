// jsdom n'a pas de matchMedia : largeur d'écran simulée, modifiable dans un test (rotation, téléphone).
let viewportWidth = 1200;
const listeners = new Set<() => void>();

export function setViewportWidth(px: number): void {
  viewportWidth = px;
  listeners.forEach((notify) => notify());
}

Object.defineProperty(window, "matchMedia", {
  configurable: true,
  value: (query: string) => {
    const max = Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Infinity);
    const min = Number(/min-width:\s*(\d+)px/.exec(query)?.[1] ?? 0);
    return {
      get matches() { return viewportWidth <= max && viewportWidth >= min; },
      media: query,
      onchange: null,
      addEventListener: (_: string, cb: () => void) => listeners.add(cb),
      removeEventListener: (_: string, cb: () => void) => listeners.delete(cb),
      addListener: (cb: () => void) => listeners.add(cb),
      removeListener: (cb: () => void) => listeners.delete(cb),
      dispatchEvent: () => true,
    };
  },
});
