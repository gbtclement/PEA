import { act, renderHook } from "@testing-library/react";
import { setViewportWidth } from "@/test/utils";
import { useIsMobile } from "./useIsMobile";

afterEach(() => setViewportWidth(1200));

test("vrai sous 768 px, et suit la rotation de l'écran", () => {
  setViewportWidth(390);
  const { result } = renderHook(() => useIsMobile());
  expect(result.current).toBe(true);
  act(() => setViewportWidth(1024));
  expect(result.current).toBe(false);
});
