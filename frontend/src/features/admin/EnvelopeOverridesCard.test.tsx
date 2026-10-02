import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { EnvelopeOverridesCard } from "./EnvelopeOverridesCard";

afterEach(() => vi.unstubAllGlobals());

const envelopes = (pea: string, peaPme: string, override: string | null = null) => [
  { code: "pea", status: pea, source: override ? "manual" : "auto", override },
  { code: "pea_pme", status: peaPme, source: "auto", override: null },
];
const GECINA = { id: 4, yahoo_ticker: "GFC.PA", symbol: "GFC", name: "Gecina", kind: "stock", market: "Euronext Paris",
  country: "FR", sector: "Real Estate", envelopes: envelopes("a_verifier", "a_verifier"), price: 90, change_pct: 0, as_of: null };

test("choisit l'enveloppe puis corrige le statut d'un titre", async () => {
  const fetchMock = mockFetch((url) => {
    if (url.includes("overridden=true")) return { body: { items: [], total: 0 } };
    if (url.includes("/envelopes/")) return { body: { ...GECINA, envelopes: envelopes("a_verifier", "eligible") } };
    return { body: { items: [GECINA], total: 1 } };
  });
  renderWithProviders(<EnvelopeOverridesCard />);
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Enveloppe à corriger" }), "pea_pme");
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher un titre" }), "gec");
  await userEvent.selectOptions(await screen.findByRole("combobox", { name: "PEA-PME : statut de Gecina" }), "eligible");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/securities/4/envelopes/pea_pme",
    expect.objectContaining({ method: "PATCH", body: JSON.stringify({ override: "eligible" }) })));
});

test("liste les corrections de l'enveloppe choisie", async () => {
  const corrected = { ...GECINA, envelopes: envelopes("non_eligible", "non_eligible", "non_eligible") };
  mockFetch((url) => url.includes("overridden=true") ? { body: { items: [corrected], total: 1 } } : { body: { items: [], total: 0 } });
  renderWithProviders(<EnvelopeOverridesCard />);
  expect(await screen.findByText("Gecina")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Enveloppe à corriger" }), "pea_pme");
  await waitFor(() => expect(screen.queryByText("Gecina")).not.toBeInTheDocument()); // pas de correction PEA-PME
});
