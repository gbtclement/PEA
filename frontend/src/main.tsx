import "./index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import { router } from "@/app/router";
import { afterServerPaint } from "@/lib/boot";
import { createQueryClient, seedFromPage } from "@/lib/queryClient";

const queryClient = createQueryClient();
seedFromPage(queryClient);  // pages publiques : données déjà dans le HTML

const root = document.getElementById("root")!;
afterServerPaint(root, () =>
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  ),
);
