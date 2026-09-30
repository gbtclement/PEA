import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { PremiumCard } from "./PremiumCard";

test("explique ce qui est réservé et mène à /premium", () => {
  renderWithProviders(<PremiumCard feature="La liste des prévisions" />);
  expect(screen.getByText("Réservé aux membres Premium")).toBeInTheDocument();
  expect(screen.getByText(/La liste des prévisions fait partie de l'offre Premium/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Découvrir Premium" })).toHaveAttribute("href", "/premium");
});
