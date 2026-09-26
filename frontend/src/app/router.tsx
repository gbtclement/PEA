import { createBrowserRouter, type RouteObject } from "react-router";
import { ComingSoon } from "@/components/ComingSoon";
import { ExplorerPage } from "@/features/explorer/ExplorerPage";
import { Layout } from "./Layout";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, lazy: async () => ({ Component: (await import("@/features/home/HomePage")).HomePage }) },
      { path: "explorer", element: <ExplorerPage /> },
      { path: "etf", element: <ComingSoon title="ETF" description="Le classement des ETF éligibles PEA arrive au lot 2." /> },
      { path: "portefeuille", element: <ComingSoon title="Portefeuille" description="Le suivi de votre PEA arrive au lot 3." /> },
      { path: "assistant", element: <ComingSoon title="Assistant IA" description="L'assistant IA arrive au lot 4." /> },
      { path: "reglages", element: <ComingSoon title="Réglages" description="Les réglages arrivent au lot 2." /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
