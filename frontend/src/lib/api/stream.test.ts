import { sseResponse } from "@/test/utils";
import { ApiError, streamSSE, type ChatEvent } from "./client";

afterEach(() => vi.unstubAllGlobals());

test("lit les événements même coupés au milieu d'un paquet", async () => {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
    sseResponse([{ type: "text", text: "Bon" }, { type: "text", text: "jour" }], { split: true }));
  vi.stubGlobal("fetch", fetchMock);
  const seen: ChatEvent[] = [];
  await streamSSE("/api/x", { content: "a" }, (e) => seen.push(e));
  expect(seen).toEqual([{ type: "text", text: "Bon" }, { type: "text", text: "jour" }]);
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", body: JSON.stringify({ content: "a" }) });
});

test("renvoie le message du serveur en cas de refus", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Aucune clé API Claude n'est configurée." }), { status: 409 })));
  await expect(streamSSE("/api/x", {}, () => {})).rejects.toEqual(new ApiError(409, "Aucune clé API Claude n'est configurée."));
});
