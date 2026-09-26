import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { OrderDialog } from "./OrderDialog";

afterEach(() => vi.unstubAllGlobals());
const LVMH = { id: 1, name: "LVMH", symbol: "MC" };

function postBody(fetchMock: ReturnType<typeof mockFetch>, url = "/api/orders") {
  const call = fetchMock.mock.calls.find(([u, init]) => u === url && init?.method !== undefined)!;
  return JSON.parse(call[1]!.body as string);
}

test("préremplit le titre, estime les frais et enregistre l'achat", async () => {
  const fetchMock = mockFetch((url) => {
    if (url.startsWith("/api/fees/estimate")) return { body: { amount: 400, fee: 1.92, rate: 0.0048 } };
    return { status: 201, body: { id: 7 } };
  });
  const onOpenChange = vi.fn();
  renderWithProviders(<OrderDialog open onOpenChange={onOpenChange} security={LVMH} price={40} />);
  expect(screen.getByText("LVMH")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Quantité"), "10");
  await waitFor(() => expect(screen.getByLabelText("Frais (€)")).toHaveValue("1,92"));
  expect(screen.getByText(/400,00 €/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  expect(postBody(fetchMock)).toMatchObject({ security_id: 1, side: "buy", quantity: 10, unit_price: 40, fee: null });
});

test("frais saisis à la main envoyés tels quels", async () => {
  const fetchMock = mockFetch((url) => url.startsWith("/api/fees") ? { body: { amount: 400, fee: 1.92, rate: 0.0048 } } : { status: 201, body: { id: 7 } });
  renderWithProviders(<OrderDialog open onOpenChange={() => {}} security={LVMH} price={40} />);
  await userEvent.type(screen.getByLabelText("Quantité"), "10");
  const fee = screen.getByLabelText("Frais (€)");
  await userEvent.clear(fee);
  await userEvent.type(fee, "0");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/orders" && init?.method === "POST")).toBe(true));
  expect(postBody(fetchMock).fee).toBe(0);
});

test("affiche le refus du serveur (vente trop grande)", async () => {
  mockFetch((url) => url.startsWith("/api/fees") ? { body: { amount: 60, fee: 0.29, rate: 0.0048 } }
    : { status: 422, body: { detail: "Vente impossible : vous ne détenez que 3 titre(s) LVMH au 02/03/2026 (vente de 5)." } });
  renderWithProviders(<OrderDialog open onOpenChange={() => {}} security={LVMH} price={12} />);
  await userEvent.selectOptions(screen.getByLabelText("Sens"), "sell");
  await userEvent.type(screen.getByLabelText("Quantité"), "5");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("vous ne détenez que 3");
});

test("recherche un titre quand aucun n'est prérempli", async () => {
  mockFetch((url) => url.startsWith("/api/securities")
    ? { body: { items: [{ id: 2, name: "TotalEnergies", symbol: "TTE", market: "Euronext Paris" }], total: 1 } }
    : { body: { amount: 0, fee: 0, rate: 0 } });
  renderWithProviders(<OrderDialog open onOpenChange={() => {}} />);
  expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher un titre" }), "tot");
  await userEvent.click(await screen.findByRole("button", { name: /TotalEnergies/ }));
  expect(screen.getByRole("button", { name: "Changer" })).toBeInTheDocument();
});

test("modification : préremplit l'ordre, garde ses frais et envoie un PUT", async () => {
  const fetchMock = mockFetch(() => ({ body: { id: 3 } }));
  const order = { id: 3, security_id: 1, symbol: "MC", name: "LVMH", trade_date: "2026-03-02", side: "buy", quantity: 10,
    unit_price: 50, fee: 2.4, amount: 500, note: null };
  renderWithProviders(<OrderDialog open onOpenChange={() => {}} order={order} />);
  expect(screen.getByText("Modifier l'ordre")).toBeInTheDocument();
  expect(screen.getByLabelText("Frais (€)")).toHaveValue("2,40");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/orders/3" && init?.method === "PUT")).toBe(true));
  expect(postBody(fetchMock, "/api/orders/3")).toMatchObject({ trade_date: "2026-03-02", quantity: 10, fee: 2.4 });
});

test("modification : changer la quantité recalcule les frais", async () => {
  const fetchMock = mockFetch((url) => url.startsWith("/api/fees/estimate") ? { body: { amount: 5000, fee: 6, rate: 0.0012 } } : { body: { id: 3 } });
  const order = { id: 3, security_id: 1, symbol: "MC", name: "LVMH", trade_date: "2026-03-02", side: "buy", quantity: 10,
    unit_price: 50, fee: 2.4, amount: 500, note: null };
  renderWithProviders(<OrderDialog open onOpenChange={() => {}} order={order} />);
  const quantity = screen.getByLabelText("Quantité");
  await userEvent.clear(quantity);
  await userEvent.type(quantity, "100");
  await waitFor(() => expect(screen.getByLabelText("Frais (€)")).toHaveValue("6,00"));
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/orders/3" && init?.method === "PUT")).toBe(true));
  expect(postBody(fetchMock, "/api/orders/3")).toMatchObject({ quantity: 100, fee: null });
});

test("vider des frais saisis à la main revient à l'estimation automatique", async () => {
  mockFetch((url) => url.startsWith("/api/fees") ? { body: { amount: 400, fee: 1.92, rate: 0.0048 } } : { status: 201, body: { id: 7 } });
  renderWithProviders(<OrderDialog open onOpenChange={() => {}} security={LVMH} price={40} />);
  await userEvent.type(screen.getByLabelText("Quantité"), "10");
  const fee = screen.getByLabelText("Frais (€)");
  await userEvent.clear(fee);
  await userEvent.type(fee, "5");
  expect(screen.getByText(/frais saisis à la main/)).toBeInTheDocument();
  await userEvent.clear(fee);
  await userEvent.tab();
  await waitFor(() => expect(fee).toHaveValue("1,92"));
  expect(screen.getByText(/frais estimés automatiquement/)).toBeInTheDocument();
});
