import { formatPct, formatPrice } from "./format";

test("formatPrice utilise le format français", () => {
  expect(formatPrice(1234.5)).toMatch(/^1\s234,50$/u);
  expect(formatPrice(null)).toBe("—");
});

test("formatPct ajoute le signe", () => {
  expect(formatPct(2.07)).toMatch(/^\+2,07\s%$/u);
  expect(formatPct(-1.5)).toMatch(/^-1,50\s%$/u);
  expect(formatPct(0)).toMatch(/^0,00\s%$/u);
  expect(formatPct(undefined)).toBe("—");
});
