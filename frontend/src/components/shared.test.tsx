import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { FavoriteButton } from "./FavoriteButton";
import { ScoreGauge } from "./ScoreGauge";
import { Sparkline } from "./Sparkline";

afterEach(() => vi.unstubAllGlobals());

test("Sparkline trace une courbe verte si la série monte", () => {
  const { container } = render(<Sparkline values={[1, 3, 2, 4]} />);
  const line = container.querySelector("polyline")!;
  expect(line.getAttribute("points")!.split(" ")).toHaveLength(4);
  expect(line).toHaveAttribute("stroke", "#16a34a");
});

test("Sparkline vide ne dessine rien", () => {
  const { container } = render(<Sparkline values={[]} />);
  expect(container.querySelector("polyline")).toBeNull();
});

test("ScoreGauge affiche le score arrondi", () => {
  render(<ScoreGauge score={72.6} />);
  expect(screen.getByLabelText("Score 73 sur 100")).toHaveTextContent("73");
});

test("ScoreGauge sans score", () => {
  render(<ScoreGauge score={null} />);
  expect(screen.getByLabelText("Score indisponible")).toHaveTextContent("—");
});

test("FavoriteButton ajoute puis retire", async () => {
  const fetchMock = mockFetch(() => ({ status: 204, body: null }));
  const { rerender } = renderWithProviders(<FavoriteButton securityId={7} isFavorite={false} />);
  await userEvent.click(screen.getByRole("button", { name: "Ajouter aux favoris" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/favorites/7", expect.objectContaining({ method: "PUT" })));
  rerender(<FavoriteButton securityId={7} isFavorite />);
  await userEvent.click(screen.getByRole("button", { name: "Retirer des favoris" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/favorites/7", expect.objectContaining({ method: "DELETE" })));
});
