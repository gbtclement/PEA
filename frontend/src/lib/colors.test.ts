import { changeColor, scoreColor } from "./colors";

test("changeColor", () => {
  expect(changeColor(0)).toBe("rgb(228, 228, 231)");
  expect(changeColor(3)).toBe("rgb(22, 163, 74)");
  expect(changeColor(10)).toBe("rgb(22, 163, 74)");
  expect(changeColor(-3)).toBe("rgb(220, 38, 38)");
  expect(changeColor(null)).toBe("rgb(228, 228, 231)");
});

test("scoreColor", () => {
  expect(scoreColor(80)).toBe("#16a34a");
  expect(scoreColor(55)).toBe("#d97706");
  expect(scoreColor(30)).toBe("#dc2626");
  expect(scoreColor(null)).toBe("#a1a1aa");
});
