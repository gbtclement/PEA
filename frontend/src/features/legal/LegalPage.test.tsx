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
  expect(screen.getByText(/Dernière mise à jour : 1er octobre 2026/)).toBeInTheDocument();
});
