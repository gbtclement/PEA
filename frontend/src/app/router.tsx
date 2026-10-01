import { createBrowserRouter, type RouteObject } from "react-router";
import { RequireAdmin } from "@/features/auth/RequireAdmin";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { LegalPage } from "@/features/legal/LegalPage";
import { ScreenerPage } from "@/features/screener/ScreenerPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { Layout } from "./Layout";
import { NotFoundPage } from "./NotFoundPage";

export const routes: RouteObject[] = [
  // Écrans de compte : plein écran, hors de la mise en page de l'application
  // Inscription et connexion partagent une route parente : la page reste montée et le panneau glisse
  { lazy: async () => ({ Component: (await import("@/features/auth/AuthPage")).AuthRoute }),
    children: [{ path: "/inscription" }, { path: "/connexion" }] },
  { path: "/verifier-email", lazy: async () => ({ Component: (await import("@/features/auth/VerifyEmailPage")).VerifyEmailPage }) },
  { path: "/mot-de-passe-oublie", lazy: async () => ({ Component: (await import("@/features/auth/ForgotPasswordPage")).ForgotPasswordPage }) },
  { path: "/finaliser-inscription", lazy: async () => ({ Component: (await import("@/features/auth/FinishSignUpPage")).FinishSignUpPage }) },
  { path: "/reinitialiser", lazy: async () => ({ Component: (await import("@/features/auth/ResetPasswordPage")).ResetPasswordPage }) },
  { path: "/accepter-cgu", lazy: async () => ({ Component: (await import("@/features/auth/AcceptTermsPage")).AcceptTermsPage }) },
  { path: "/ce-n-etait-pas-moi", lazy: async () => ({ Component: (await import("@/features/auth/NotMePage")).NotMePage }) },
  {
    path: "/",
    element: <Layout />,
    children: [
      // Pages publiques : lisibles sans compte (et par les moteurs de recherche)
      { index: true, lazy: async () => ({ Component: (await import("@/features/home/HomePage")).HomePage }) },
      { path: "explorer", element: <ScreenerPage kind="stock" title="Explorer" description="Toutes les actions européennes avec leur score, leurs performances et leur éligibilité au PEA." /> },
      { path: "etf", element: <ScreenerPage kind="etf" title="ETF" description="Les ETF éligibles au PEA, classés par score technique." /> },
      { path: "titres/:id", lazy: async () => ({ Component: (await import("@/features/security/SecurityPage")).SecurityPage }) },
      { path: "cgu", element: <LegalPage kind="cgu" /> },
      { path: "confidentialite", element: <LegalPage kind="confidentialite" /> },
      { path: "mentions-legales", element: <LegalPage kind="mentions-legales" /> },
      // Pages personnelles : connexion obligatoire
      {
        element: <RequireAuth />,
        children: [
          { path: "previsions", lazy: async () => ({ Component: (await import("@/features/forecasts/ForecastsPage")).ForecastsPage }) },
          { path: "portefeuille", lazy: async () => ({ Component: (await import("@/features/portfolio/PortfolioPage")).PortfolioPage }) },
          { path: "assistant", lazy: async () => ({ Component: (await import("@/features/assistant/AssistantPage")).AssistantPage }) },
          { path: "reglages", element: <SettingsPage /> },
          {
            element: <RequireAdmin />,
            children: [{ path: "admin", lazy: async () => ({ Component: (await import("@/features/admin/AdminPage")).AdminPage }) }],
          },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
