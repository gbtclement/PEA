import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { routes } from "./router";

test.each([
  ["/", "Accueil"],
  ["/portefeuille", "Portefeuille"],
  ["/assistant", "Assistant IA"],
])("la route %s affiche le titre %s", async (path, title) => {
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />);
  expect(await screen.findByRole("heading", { level: 1, name: title })).toBeInTheDocument();
});
