import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { EnvelopesCard } from "./EnvelopesCard";

afterEach(() => vi.unstubAllGlobals());

function api(envelopes: string[]) {
  return mockFetch((url, init) => {
    if (url === "/api/me") return { body: ME };
    if (url === "/api/settings/envelopes") return { body: init?.method === "PUT" ? JSON.parse(String(init.body)) : { envelopes } };
    return { body: null };
  });
}

test("coche ses enveloppes et les enregistre", async () => {
  const fetchMock = api([]);
  renderWithProviders(<EnvelopesCard />);
  const pea = await screen.findByRole("checkbox", { name: /^PEA(?!-PME)/ });
  expect(pea).not.toBeChecked();
  expect(screen.getByText("Vous verrez tous les titres.")).toBeInTheDocument();
  await userEvent.click(pea);
  await userEvent.click(screen.getByRole("checkbox", { name: /PEA-PME/ }));
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer mes enveloppes" }));
  await waitFor(() => {
    const put = fetchMock.mock.calls.find(([url, init]) => url === "/api/settings/envelopes" && init?.method === "PUT");
    expect(JSON.parse(put![1]!.body as string)).toEqual({ envelopes: ["pea", "pea_pme"] });
  });
});

test("compte-titres coché : le texte dit que tous les titres restent visibles", async () => {
  api(["pea", "cto"]);
  renderWithProviders(<EnvelopesCard />);
  expect(await screen.findByRole("checkbox", { name: /Compte-titres/ })).toBeChecked();
  expect(screen.getByText("Vous verrez tous les titres.")).toBeInTheDocument();
});
