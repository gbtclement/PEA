import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { EligibilityOverridesCard } from "./EligibilityOverridesCard";

afterEach(() => vi.unstubAllGlobals());

const GECINA = { id: 4, yahoo_ticker: "GFC.PA", symbol: "GFC", name: "Gecina", kind: "stock", market: "Euronext Paris",
  country: "FR", sector: "Real Estate", eligibility: "a_verifier", eligibility_source: "auto", eligibility_override: null,
  price: 90, change_pct: 0, as_of: null };

test("recherche un titre et corrige son éligibilité", async () => {
  const fetchMock = mockFetch((url) => {
    if (url.includes("overridden=true")) return { body: { items: [], total: 0 } };
    if (url.includes("/eligibility")) return { body: { ...GECINA, eligibility: "eligible", eligibility_source: "override", eligibility_override: "eligible" } };
    return { body: { items: [GECINA], total: 1 } };
  });
  renderWithProviders(<EligibilityOverridesCard />);
  await userEvent.type(await screen.findByRole("searchbox", { name: "Rechercher un titre" }), "gec");
  const select = await screen.findByRole("combobox", { name: "Éligibilité de Gecina" });
  await userEvent.selectOptions(select, "eligible");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/securities/4/eligibility",
    expect.objectContaining({ method: "PATCH", body: JSON.stringify({ override: "eligible" }) })));
});

test("liste les corrections existantes", async () => {
  mockFetch((url) => url.includes("overridden=true")
    ? { body: { items: [{ ...GECINA, eligibility: "eligible", eligibility_source: "override", eligibility_override: "eligible" }], total: 1 } }
    : { body: { items: [], total: 0 } });
  renderWithProviders(<EligibilityOverridesCard />);
  expect(await screen.findByText("Gecina")).toBeInTheDocument();
});
