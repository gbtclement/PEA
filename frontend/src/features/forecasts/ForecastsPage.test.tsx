import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, PREMIUM_ME, mockFetch, renderWithProviders, setViewportWidth } from "@/test/utils";
import { ForecastsPage } from "./ForecastsPage";

let chosen: string[] = ["pea"];
afterEach(() => { vi.unstubAllGlobals(); chosen = ["pea"]; });

const h = (expected: number, rank: number, reliability = "elevee") => ({ expected_return: expected, prob_up: 0.56, reliability, rank });
const security = (id: number, name: string, envelopes: string[] = ["pea"], price = 100) => ({
  id, name, symbol: name.slice(0, 3).toUpperCase(), market: "Euronext Paris", envelopes, price, change_pct: 1.2,
});
const LIST = {
  as_of: "2026-09-25",
  round_trip_cost: 0.0096,
  rows: [
    { security: security(2, "Airbus", ["pea"], 150), signals: [{ key: "trend_strong", label: "Tendance haussière forte", bullish: true }],
      horizons: { "1d": null, "1w": h(0.009, 1), "1m": h(0.004, 2, "moyenne") } },
    { security: security(1, "LVMH", ["pea"], 600), signals: [{ key: "high_52w", label: "Plus haut sur 1 an", bullish: true }],
      horizons: { "1d": h(0.002, 1), "1w": h(0.004, 2), "1m": h(0.02, 1) } },
    { security: security(3, "Étranger", []), signals: [{ key: "surge_week", label: "Forte hausse sur 1 semaine", bullish: false }],
      horizons: { "1d": null, "1w": h(-0.01, 3, "faible"), "1m": null } },
  ],
};
const stat = (n: number, mean: number, hit: number, reliability = "moyenne") => ({ n, mean, median: mean, hit_rate: hit, mean_excess: mean, beat_index: 0.5, hit_after_fees: hit - 0.1, reliability });
const SIGNALS = {
  as_of: "2026-09-25", computed_at: "2026-09-27T05:00:00Z", round_trip_cost: 0.0096,
  baseline: { "1d": stat(700000, 0.0005, 0.49), "1w": stat(719055, 0.0012, 0.509), "1m": stat(650000, 0.009, 0.53) },
  signals: [
    { key: "surge_week", label: "Forte hausse sur 1 semaine", description: "Au moins +15 %…", bullish: false,
      horizons: { "1d": stat(10000, -0.003, 0.46), "1w": stat(10548, -0.0118, 0.424), "1m": null } },
    { key: "high_52w", label: "Plus haut sur 1 an", description: "Plus haut des 12 derniers mois.", bullish: true,
      horizons: { "1d": stat(33000, 0.001, 0.51), "1w": stat(32616, 0.003, 0.52, "faible"), "1m": stat(30000, 0.012, 0.55) } },
  ],
};
const backtest = (mean: number, baseline: number) => ({ days: 231, picks: 2310, hit_rate: 0.589, hit_after_fees: 0.532, mean_return: mean,
  mean_after_fees: mean - 0.0096, mean_excess: mean - 0.001, baseline_mean: baseline, edge: mean - baseline });
const TRACK = {
  cutoff: "2025-10-01", round_trip_cost: 0.0096,
  simulated: { "1d": backtest(0.0015, 0.0005), "1w": backtest(0.006, 0.0025), "1m": backtest(0.0169, 0.0107) },
  real: { "1d": null, "1w": null, "1m": null },
};

function renderPage(route = "/previsions", { empty = false, me = PREMIUM_ME as object } = {}) {
  const fetchMock = mockFetch((url) => {
    if (url === "/api/me") return { body: me };
    if (url === "/api/settings/envelopes") return { body: { envelopes: chosen } };
    if (url.startsWith("/api/forecasts/signals")) return { body: empty ? { ...SIGNALS, as_of: null, signals: [] } : SIGNALS };
    if (url.startsWith("/api/forecasts/track-record")) return { body: TRACK };
    return { body: empty ? { as_of: null, round_trip_cost: null, rows: [] } : LIST };
  });
  renderWithProviders(<ForecastsPage />, { route });
  return fetchMock;
}

const rowNames = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);

test("titre, avertissement et noindex", async () => {
  renderPage();
  expect(screen.getByRole("heading", { level: 1, name: "Prévisions court terme" })).toBeInTheDocument();
  expect(screen.getByRole("note")).toHaveTextContent(/pas des certitudes ni des conseils/);
  await waitFor(() => expect(document.head.querySelector('meta[name="robots"]')?.getAttribute("content")).toBe("noindex, nofollow"));
  expect(await screen.findByText(/Données du 25\/09\/2026/)).toBeInTheDocument();
});

test("premier calcul en cours", async () => {
  renderPage("/previsions", { empty: true });
  expect(await screen.findByText(/premier calcul en cours/i)).toBeInTheDocument();
});

test("prédictions triées par 1 semaine, puis par 1 mois, filtre des enveloppes", async () => {
  renderPage();
  await screen.findByText("Airbus");
  expect(rowNames()[0]).toMatch(/^Airbus/);
  expect(rowNames()).toHaveLength(2);  // « Mes enveloppes uniquement » coché par défaut
  expect(screen.getAllByText("+0,90 %").length).toBeGreaterThan(0);
  expect(screen.getAllByText("56 % de hausse").length).toBeGreaterThan(0);

  await userEvent.click(screen.getByRole("button", { name: /^1 mois/ }));
  expect(rowNames()[0]).toMatch(/^LVMH/);

  await userEvent.click(screen.getByRole("checkbox", { name: "Mes enveloppes uniquement" }));
  expect(rowNames()).toHaveLength(3);
  await userEvent.click(screen.getByRole("button", { name: /^1 semaine/ }));  // le sens s'applique à l'horizon trié
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Sens" }), "baisse");
  expect(rowNames()).toEqual([expect.stringMatching(/^Étranger/)]);
});

test("statistiques des signaux : référence en tête et choix de l'horizon", async () => {
  renderPage("/previsions?vue=statistiques");
  const table = await screen.findByRole("table", { name: "Statistiques des signaux" });
  const rows = within(table).getAllByRole("row");
  expect(rows[1]).toHaveTextContent("Toutes les actions (référence)");
  expect(within(table).getByText("42 %")).toBeInTheDocument();  // surge_week à 1 semaine
  await userEvent.click(screen.getByRole("button", { name: "1 jour" }));
  expect(within(table).getByText("46 %")).toBeInTheDocument();
  expect(within(table).queryByText("42 %")).not.toBeInTheDocument();
});

test("bulletin : test sur l'année écoulée et suivi réel encore vide", async () => {
  renderPage("/previsions?vue=bulletin");
  expect(await screen.findAllByRole("heading", { level: 3, name: "1 mois" })).toHaveLength(2);  // test passé + suivi réel
  expect(screen.getAllByText(/a fait mieux que la moyenne des actions/)).toHaveLength(3);
  expect(screen.getByText(/Après frais, le gain moyen reste positif/)).toBeInTheDocument();  // seul l'horizon 1 mois
  expect(screen.getAllByText(/Pas encore de prédiction vérifiée/).length).toBe(3);
});

test("bulletin : verdict quand le gain est déjà négatif avant frais, et comparaison du suivi réel", async () => {
  const real = { picks: 40, hit_rate: 0.45, hit_after_fees: 0.3, mean_return: -0.004, mean_after_fees: -0.0136,
                 baseline_mean: -0.001, edge: -0.003, first_day: "2026-09-28" };
  mockFetch((url) => {
    if (url.startsWith("/api/forecasts/track-record")) return { body: { ...TRACK, real: { "1d": null, "1w": real, "1m": null } } };
    return { body: LIST };
  });
  renderWithProviders(<ForecastsPage />, { route: "/previsions?vue=bulletin" });
  expect(await screen.findByText(/n'a pas fait mieux que la moyenne des titres suivis/)).toBeInTheDocument();
  expect(screen.getByText(/gain moyen était déjà négatif avant frais/)).toBeInTheDocument();
  expect(screen.getByText("Moyenne des titres suivis")).toBeInTheDocument();
  expect(screen.getByText(/entreprises disparues/)).toBeInTheDocument();
});

test("prédictions : chaque clic inverse le sens, le tri ne disparaît jamais", async () => {
  renderPage();
  await screen.findByText("Airbus");
  const month = () => screen.getByRole("button", { name: /^1 mois/ });
  await userEvent.click(month());
  expect(rowNames().map((n) => n?.slice(0, 4))).toEqual(["LVMH", "Airb"]);
  expect(screen.getByRole("columnheader", { name: /1 mois/ })).toHaveAttribute("aria-sort", "descending");
  await userEvent.click(month());
  expect(rowNames().map((n) => n?.slice(0, 4))).toEqual(["Airb", "LVMH"]);
  expect(screen.getByRole("columnheader", { name: /1 mois/ })).toHaveAttribute("aria-sort", "ascending");
  await userEvent.click(month());
  expect(rowNames().map((n) => n?.slice(0, 4))).toEqual(["LVMH", "Airb"]);
});

test("prédictions : tri par cours", async () => {
  renderPage();
  await screen.findByText("Airbus");
  await userEvent.click(screen.getByRole("button", { name: "Cours" }));
  expect(rowNames().map((n) => n?.slice(0, 4))).toEqual(["LVMH", "Airb"]);
});

const statNames = async () => {
  const table = await screen.findByRole("table", { name: "Statistiques des signaux" });
  return within(table).getAllByRole("row").slice(2).map((r) => within(r).getAllByRole("rowheader")[0].textContent?.slice(2, 12));
};

test("statistiques : recliquer inverse le sens, Signal et Fiabilité se trient aussi", async () => {
  renderPage("/previsions?vue=statistiques");
  expect(await statNames()).toEqual(["Plus haut ", "Forte haus"]);  // gain moyen décroissant par défaut
  await userEvent.click(screen.getByRole("button", { name: /Gain moyen/ }));
  expect(await statNames()).toEqual(["Forte haus", "Plus haut "]);
  expect(screen.getByRole("columnheader", { name: /Gain moyen/ })).toHaveAttribute("aria-sort", "ascending");
  await userEvent.click(screen.getByRole("button", { name: "Signal" }));
  expect(await statNames()).toEqual(["Forte haus", "Plus haut "]);  // ordre alphabétique d'abord
  await userEvent.click(screen.getByRole("button", { name: "Fiabilité" }));
  expect(await statNames()).toEqual(["Forte haus", "Plus haut "]);  // moyenne avant faible
  await userEvent.click(screen.getByRole("button", { name: "Fiabilité" }));
  expect(await statNames()).toEqual(["Plus haut ", "Forte haus"]);
});

test("membre gratuit : la page s'ouvre sur le bulletin et les prédictions sont réservées", async () => {
  const fetchMock = renderPage("/previsions", { me: ME });
  expect(await screen.findByRole("button", { name: "Bulletin de notes", current: "page" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Prédictions" }));
  expect(await screen.findByText("Réservé aux membres Premium")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => String(url) === "/api/forecasts")).toBe(false);
});

test("« Mes enveloppes uniquement » est coché par défaut quand l'utilisateur en a choisi", async () => {
  chosen = ["pea"];
  renderPage();
  const box = await screen.findByRole("checkbox", { name: "Mes enveloppes uniquement" });
  expect(box).toBeChecked();
  expect(screen.queryByText("Étranger")).not.toBeInTheDocument();
  await userEvent.click(box);
  expect(await screen.findByText("Étranger")).toBeInTheDocument();
});

test("sans enveloppe choisie, pas de case et tous les titres", async () => {
  chosen = [];
  renderPage();
  expect(await screen.findByText("Étranger")).toBeInTheDocument();
  expect(screen.queryByRole("checkbox", { name: "Mes enveloppes uniquement" })).not.toBeInTheDocument();
});

test("sur téléphone, une carte par prédiction avec les trois horizons", async () => {
  setViewportWidth(390);
  try {
    renderPage();
    const card = await screen.findByRole("link", { name: /LVMH/ });
    expect(screen.queryByRole("columnheader")).not.toBeInTheDocument();
    expect(within(card).getByText("1 semaine")).toBeInTheDocument();
  } finally {
    setViewportWidth(1200);
  }
});

test("sur téléphone, un choix de tri remplace les en-têtes de colonnes", async () => {
  setViewportWidth(390);
  try {
    renderPage();
    const sort = await screen.findByRole("combobox", { name: "Trier par" });
    await userEvent.selectOptions(sort, "1m");
    expect(sort).toHaveValue("1m");
    expect(screen.getByRole("combobox", { name: "Sens" })).toHaveTextContent("Hausse et baisse (1 mois)");
  } finally {
    setViewportWidth(1200);
  }
});
