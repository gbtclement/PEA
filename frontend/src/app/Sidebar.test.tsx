import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { Sidebar } from "./Sidebar";

test("affiche les sept entrées de navigation", () => {
  render(<MemoryRouter><Sidebar /></MemoryRouter>);
  const nav = screen.getByRole("navigation", { name: "Navigation principale" });
  const labels = Array.from(nav.querySelectorAll("a")).map((a) => a.textContent);
  expect(labels).toEqual(["Accueil", "Explorer", "ETF", "Prévisions", "Portefeuille", "Assistant IA", "Réglages"]);
});

test("met en évidence la page courante", () => {
  render(<MemoryRouter initialEntries={["/explorer"]}><Sidebar /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "Explorer" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Accueil" })).not.toHaveAttribute("aria-current");
});

test("renvoie vers le guide, servi hors de l'application, mais pas vers la documentation admin", () => {
  render(<MemoryRouter><Sidebar /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "Guide" })).toHaveAttribute("href", "/guide/");
  expect(document.querySelector("a[href^='/documentation']")).toBeNull();
});

test("affiche le pied de barre fourni", () => {
  render(<MemoryRouter><Sidebar footer={<p>Bourse ouverte</p>} /></MemoryRouter>);
  expect(screen.getByText("Bourse ouverte")).toBeInTheDocument();
});
