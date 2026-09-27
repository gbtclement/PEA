import { createBrowserRouter, type RouteObject } from "react-router";
import { ScreenerPage } from "@/features/screener/ScreenerPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { Layout } from "./Layout";
import { NotFoundPage } from "./NotFoundPage";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, lazy: async () => ({ Component: (await import("@/features/home/HomePage")).HomePage }) },
      { path: "explorer", element: <ScreenerPage kind="stock" title="Explorer" description="Toutes les actions européennes avec leur score, leurs performances et leur éligibilité au PEA." /> },
      { path: "etf", element: <ScreenerPage kind="etf" title="ETF" description="Les ETF éligibles au PEA, classés par score technique." /> },
      { path: "portefeuille", lazy: async () => ({ Component: (await import("@/features/portfolio/PortfolioPage")).PortfolioPage }) },
      { path: "assistant", lazy: async () => ({ Component: (await import("@/features/assistant/AssistantPage")).AssistantPage }) },
      { path: "titres/:id", lazy: async () => ({ Component: (await import("@/features/security/SecurityPage")).SecurityPage }) },
      { path: "reglages", element: <SettingsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
