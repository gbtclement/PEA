import { ApiError, apiSend } from "./client";
import { mockFetch } from "@/test/utils";

afterEach(() => vi.unstubAllGlobals());

test("apiSend POST envoie le corps JSON", async () => {
  const fetchMock = mockFetch(() => ({ status: 201, body: { id: 1 } }));
  expect(await apiSend("POST", "/api/orders", { a: 1 })).toEqual({ id: 1 });
  expect(fetchMock).toHaveBeenCalledWith("/api/orders", expect.objectContaining({ method: "POST", body: '{"a":1}' }));
});

test("apiSend remonte le message d'erreur de l'API", async () => {
  mockFetch(() => ({ status: 422, body: { detail: "Vente impossible : vous ne détenez que 3 titre(s)." } }));
  await expect(apiSend("POST", "/api/orders", {})).rejects.toEqual(
    expect.objectContaining({ status: 422, message: "Vente impossible : vous ne détenez que 3 titre(s)." }));
});

test("apiSend garde un message générique pour les erreurs de validation", async () => {
  mockFetch(() => ({ status: 422, body: { detail: [{ msg: "x" }] } }));
  await expect(apiSend("POST", "/api/orders", {})).rejects.toEqual(
    expect.objectContaining({ status: 422, message: "Erreur 422 sur /api/orders" }));
  await expect(apiSend("POST", "/api/orders", {})).rejects.toBeInstanceOf(ApiError);
});

test("apiSend envoie le jeton CSRF lu dans le cookie", async () => {
  document.cookie = "cotalyx_csrf=jeton-123; path=/";
  const fetchMock = mockFetch(() => ({ body: { ok: true } }));
  await apiSend("POST", "/api/test", {});
  expect(new Headers(fetchMock.mock.calls[0][1]!.headers).get("X-CSRF-Token")).toBe("jeton-123");
  document.cookie = "cotalyx_csrf=; max-age=0; path=/";
});

test("les erreurs de l'API gardent leur code et leur message", async () => {
  mockFetch(() => ({ status: 401, body: { detail: { code: "invalid_credentials", message: "Adresse mail ou mot de passe incorrect." } } }));
  await expect(apiSend("POST", "/api/auth/login", {})).rejects.toMatchObject({
    status: 401, code: "invalid_credentials", message: "Adresse mail ou mot de passe incorrect.",
  });
});
