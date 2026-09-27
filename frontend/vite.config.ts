/// <reference types="vitest/config" />
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = process.env.VITE_API_PROXY ?? "http://localhost:8000";
// robots.txt, sitemap.xml et llms.txt sont générés par l'API, comme derrière nginx
const seoFile = { target: api, rewrite: (p: string) => `/api/seo${p}` };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    port: 5180,
    strictPort: true,
    proxy: { "/api": api, "/robots.txt": seoFile, "/sitemap.xml": seoFile, "/llms.txt": seoFile },
  },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"], exclude: ["e2e/**", "node_modules/**"], testTimeout: 15_000 },
});
