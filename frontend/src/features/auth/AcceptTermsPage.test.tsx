import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ME, mockFetch } from "@/test/utils";
import { routes } from "@/app/router";

vi.mock("@/components/charts/EChart", () => ({ EChart: () => null }));
afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("un compte aux CGU périmées est envoyé vers /accepter-cgu, puis ramené", async () => {
  let accepted = false;
  const fetchMock = mockFetch((url) => {
    if (url === "/api/me/accept-terms") { accepted = true; return { body: { ...ME, terms_outdated: false } }; }
    if (url === "/api/me") return { body: { ...ME, terms_outdated: !accepted } };
    if (url === "/api/status") return { body: { market_open: false, jobs: [] } };  // barre latérale, avant la redirection
    return { body: url.startsWith("/api/orders") ? [] : {} };
  });
  const router = renderAt("/portefeuille");
  expect(await screen.findByRole("heading", { level: 1, name: "Nos conditions ont changé" }, { timeout: 5000 })).toBeInTheDocument();
  expect(router.state.location.search).toBe("?suite=%2Fportefeuille");
  const accept = screen.getByRole("button", { name: "Accepter et continuer" });
  expect(accept).toBeDisabled();
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(accept);
  await waitFor(() => expect(router.state.location.pathname).toBe("/portefeuille"));
  expect(fetchMock).toHaveBeenCalledWith("/api/me/accept-terms", expect.objectContaining({ method: "POST" }));
});

test("liens vers les CGU et la politique de confidentialité", async () => {
  mockFetch((url) => ({ body: url === "/api/me" ? { ...ME, terms_outdated: true } : {} }));
  renderAt("/accepter-cgu");
  const label = (await screen.findByRole("checkbox")).closest("label")!;  // le pied de page a aussi un lien « CGU »
  expect(within(label).getByRole("link", { name: "CGU" })).toHaveAttribute("href", "/cgu");
  expect(within(label).getByRole("link", { name: "politique de confidentialité" })).toHaveAttribute("href", "/confidentialite");
});

test("CGU périmées : les pages légales restent lisibles", async () => {
  mockFetch((url) => ({ body: url === "/api/me" ? { ...ME, terms_outdated: true }
    : url === "/api/status" ? { market_open: false, jobs: [] } : {} }));
  const router = renderAt("/cgu");
  expect(await screen.findByRole("heading", { level: 1, name: "Conditions générales d'utilisation" })).toBeInTheDocument();
  await screen.findByText("Moi Dupont");  // compte chargé : la redirection aurait eu lieu
  expect(router.state.location.pathname).toBe("/cgu");
});

test("refuser les CGU : exporter ses données ou supprimer son compte reste possible", async () => {
  mockFetch((url) => ({ body: url === "/api/me" ? { ...ME, terms_outdated: true } : null }));
  renderAt("/accepter-cgu");
  expect(await screen.findByRole("button", { name: "Exporter mes données" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Supprimer mon compte" })).toBeInTheDocument();
});
