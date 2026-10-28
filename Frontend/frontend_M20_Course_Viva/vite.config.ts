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
/** M11, the voice engine (PORTS.txt 8111): the examiner's voice and face. */
const VOICE_TARGET = process.env.VITE_VOICE_BASE ?? "http://127.0.0.1:8111";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  optimizeDeps: {
    // @ai/core ships TypeScript source rather than a build, so Vite must
    // transform it instead of pre-bundling it as an opaque dependency.
    exclude: ["@ai/core"],
    // The examiner's 3D head (Core's TalkingHead) loads this renderer, which
    // imports jszip — CommonJS, so it works only pre-bundled. With @ai/core
    // excluded nothing tells Vite the renderer is used: it was served raw,
    // the import failed ("jszip does not provide an export named 'default'")
    // and every head fell back to its photograph, silently (2026-10-28).
    include: ["@myned-ai/gsplat-flame-avatar-renderer"],
  },
  server: {
    port: 5220,
    strictPort: true,
    // One origin for the browser, so CORS never comes up.
    proxy: {
      // The viva's examiner speaks and listens through M11 (Core's voice
      // client asks for /v1/voice/... on this origin). First: the first key
      // that matches wins, and "/v1" would answer it from M20.
      "/v1/voice": { target: VOICE_TARGET, changeOrigin: true },
      "/v1": { target: API_TARGET, changeOrigin: true },
      "/health": { target: API_TARGET, changeOrigin: true },
    },
  },
  preview: { port: 5220, strictPort: true },
});
