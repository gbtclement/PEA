import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { renderWithProviders } from "@/test/utils";
import { MobileHeader } from "./MobileHeader";

function renderHeader(route = "/") {
  return renderWithProviders(
    <Routes>
      <Route path="*" element={<><MobileHeader footer={<p>Europe : ouverte</p>} account={<p>Compte</p>} /><p>page</p></>} />
    </Routes>,
    { route },
  );
}

test("le menu s'ouvre en tiroir avec les liens, l'état des places et le guide", async () => {
  renderHeader();
  expect(screen.queryByRole("navigation", { name: "Navigation principale" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
  const nav = await screen.findByRole("navigation", { name: "Navigation principale" });
  expect(nav).toHaveTextContent("Explorer");
  expect(screen.getByText("Europe : ouverte")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Guide" })).toHaveAttribute("href", "/guide/");
});

test("le tiroir se ferme quand on change de page", async () => {
  renderHeader();
  await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
  await userEvent.click(await screen.findByRole("link", { name: "Explorer" }));
  expect(screen.queryByRole("navigation", { name: "Navigation principale" })).not.toBeInTheDocument();
});

test("Échap ferme le tiroir", async () => {
  renderHeader();
  await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
  await screen.findByRole("navigation", { name: "Navigation principale" });
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("navigation", { name: "Navigation principale" })).not.toBeInTheDocument();
});
