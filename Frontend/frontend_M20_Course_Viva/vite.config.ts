import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/**
 * M20 — Course Viva, on its reserved port 5220 (PORTS.txt).
 *
 * This repo holds one module, so this is the app. The platform shell mounts the
 * same `src/routes.tsx` (phase 4), so what you fix here is what students get.
 */
const API_TARGET = process.env.VITE_API_BASE ?? "http://127.0.0.1:8120";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  optimizeDeps: {
    // @ai/core ships TypeScript source rather than a build, so Vite must
    // transform it instead of pre-bundling it as an opaque dependency.
    exclude: ["@ai/core"],
  },
  server: {
    port: 5220,
    strictPort: true,
    // One origin for the browser, so CORS never comes up.
    proxy: {
      "/v1": { target: API_TARGET, changeOrigin: true },
      "/health": { target: API_TARGET, changeOrigin: true },
    },
  },
  preview: { port: 5220, strictPort: true },
});
