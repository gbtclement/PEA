import { isExternalSuite, loginPath, safeNext } from "./redirect";

test.each([
  [null, "/"], ["", "/"], ["/portefeuille", "/portefeuille"], ["/titres/12?vue=1", "/titres/12?vue=1"],
  ["//evil.com", "/"], ["https://evil.com", "/"], ["/\\evil.com", "/"], ["javascript:alert(1)", "/"],
])("safeNext(%s) = %s", (value, expected) => {
  expect(safeNext(value)).toBe(expected);
});

test("loginPath garde la page demandée", () => {
  expect(loginPath({ pathname: "/portefeuille", search: "?onglet=ordres" })).toBe("/connexion?suite=%2Fportefeuille%3Fonglet%3Dordres");
});

test("une suite hors de l'application est ouverte par une navigation complète", () => {
  expect(isExternalSuite("/documentation/")).toBe(true);
  expect(isExternalSuite("/guide/#/premiers-pas")).toBe(true);
  expect(isExternalSuite("/portefeuille")).toBe(false);
  expect(isExternalSuite("/documentation-bis")).toBe(false);
});
