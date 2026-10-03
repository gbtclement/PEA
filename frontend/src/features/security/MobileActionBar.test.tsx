import { render, screen } from "@testing-library/react";
import { MobileActionBar } from "./MobileActionBar";

test("barre d'actions fixée en bas, masquée sur ordinateur", () => {
  render(<MobileActionBar><button type="button">Alerte</button></MobileActionBar>);
  const bar = screen.getByRole("toolbar", { name: "Actions sur ce titre" });
  expect(bar).toHaveClass("fixed", "bottom-0", "md:hidden");
  expect(screen.getByRole("button", { name: "Alerte" })).toBeInTheDocument();
});
