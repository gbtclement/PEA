import { loginPath, safeNext } from "./redirect";

test.each([
  [null, "/"], ["", "/"], ["/portefeuille", "/portefeuille"], ["/titres/12?vue=1", "/titres/12?vue=1"],
  ["//evil.com", "/"], ["https://evil.com", "/"], ["/\\evil.com", "/"], ["javascript:alert(1)", "/"],
])("safeNext(%s) = %s", (value, expected) => {
  expect(safeNext(value)).toBe(expected);
});

test("loginPath garde la page demandée", () => {
  expect(loginPath({ pathname: "/portefeuille", search: "?onglet=ordres" })).toBe("/connexion?suite=%2Fportefeuille%3Fonglet%3Dordres");
});
