import { ApiError } from "@/lib/api/client";
import { createQueryClient } from "./queryClient";

test("une réponse 403 terms_outdated fait relire le compte, pour rediriger vers /accepter-cgu", async () => {
  const client = createQueryClient();
  client.setQueryData(["me"], { terms_outdated: false });
  await client.fetchQuery({ queryKey: ["orders"], queryFn: () => Promise.reject(new ApiError(403, "CGU", "terms_outdated")) })
    .catch(() => undefined);
  expect(client.getQueryState(["me"])?.isInvalidated).toBe(true);
});

test("une autre erreur ne touche pas au compte", async () => {
  const client = createQueryClient();
  client.setQueryData(["me"], { terms_outdated: false });
  await client.fetchQuery({ queryKey: ["orders"], queryFn: () => Promise.reject(new ApiError(500, "boum")) }).catch(() => undefined);
  expect(client.getQueryState(["me"])?.isInvalidated).toBe(false);
});
