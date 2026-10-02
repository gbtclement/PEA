import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { LegalPage } from "./LegalPage";

test.each([
  ["cgu", "Conditions générales d'utilisation", [/18 ans/, /pas un conseil en investissement/i, /Assistant IA/]],
  ["confidentialite", "Politique de confidentialité", [/Anthropic/, /Brevo/, /Cloudflare/, /3 ans/, /Exporter mes données/]],
  ["mentions-legales", "Mentions légales", [/Éditeur/, /Hébergeur/]],
] as const)("%s : texte complet, sections attendues", (kind, title, patterns) => {
  renderWithProviders(<LegalPage kind={kind} />);
  expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
  expect(screen.queryByText(/Version provisoire/)).toBeNull();
  for (const pattern of patterns) expect(screen.getAllByText(pattern).length).toBeGreaterThan(0);
  expect(screen.getByText(/Dernière mise à jour : 6 octobre 2026/)).toBeInTheDocument();
});

test("CGV : prix, résiliation, rétractation, pas un conseil", () => {
  renderWithProviders(<LegalPage kind="cgv" />);
  expect(screen.getByRole("heading", { level: 1, name: "Conditions générales de vente" })).toBeInTheDocument();
  expect(screen.getByText(/renonce expressément à son droit de rétractation/)).toBeInTheDocument();
  expect(screen.getByText(/effective à la fin de la période déjà payée/)).toBeInTheDocument();
  expect(screen.getByText(/pas un conseil en investissement/)).toBeInTheDocument();
});

test("confidentialité : Stripe sous-traitant, la carte n'est jamais vue", () => {
  renderWithProviders(<LegalPage kind="confidentialite" />);
  expect(screen.getAllByText(/Stripe/).length).toBeGreaterThan(0);
  expect(screen.getByText(/ne voit jamais votre numéro de carte/)).toBeInTheDocument();
});
