import { formatCompactEur, formatDate, formatPct, formatPrice, formatRatioPct } from "./format";

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

test("formatRatioPct convertit une fraction", () => {
  expect(formatRatioPct(0.0328)).toMatch(/^3,28\s%$/u);
  expect(formatRatioPct(null)).toBe("—");
});

test("formatCompactEur", () => {
  expect(formatCompactEur(195_600_000_000)).toMatch(/^195,6\sMd\s€$/u);
  expect(formatCompactEur(undefined)).toBe("—");
});

test("formatDate", () => {
  expect(formatDate("2026-09-25")).toBe("25/09/2026");
});
