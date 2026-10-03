import { afterServerPaint } from "./boot";

describe("afterServerPaint", () => {
  afterEach(() => vi.useRealTimers());

  it("démarre tout de suite quand #root est vide", () => {
    const root = document.createElement("div");
    const start = vi.fn();
    afterServerPaint(root, start);
    expect(start).toHaveBeenCalledOnce();
  });

  it("laisse d'abord le navigateur peindre le résumé préparé par l'API", () => {
    vi.useFakeTimers();
    const root = document.createElement("div");
    root.append(document.createElement("h1"));
    const start = vi.fn();
    afterServerPaint(root, start);
    expect(start).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(start).toHaveBeenCalledOnce();
  });
});
