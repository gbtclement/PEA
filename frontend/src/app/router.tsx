import { createBrowserRouter, type RouteObject } from "react-router";
import { ComingSoon } from "@/components/ComingSoon";
import { ScreenerPage } from "@/features/screener/ScreenerPage";
import { Layout } from "./Layout";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, lazy: async () => ({ Component: (await import("@/features/home/HomePage")).HomePage }) },
      { path: "explorer", element: <ScreenerPage kind="stock" title="Explorer" description="Toutes les actions européennes avec leur score, leurs performances et leur éligibilité au PEA." /> },
      { path: "etf", element: <ScreenerPage kind="etf" title="ETF" description="Les ETF éligibles au PEA, classés par score technique." /> },
      { path: "portefeuille", element: <ComingSoon title="Portefeuille" description="Le suivi de votre PEA arrive au lot 3." /> },
      { path: "assistant", element: <ComingSoon title="Assistant IA" description="L'assistant IA arrive au lot 4." /> },
      { path: "reglages", element: <ComingSoon title="Réglages" description="Les réglages arrivent au lot 2." /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
