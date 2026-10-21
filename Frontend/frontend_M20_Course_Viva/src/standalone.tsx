/**
 * M20 running alone on :5220.
 *
 * Same routes and components as the shell mounts — this file only supplies the
 * providers the shell would otherwise own.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ensureSession } from "@ai/core";

import { m20Routes } from "./routes";
import { AppShell } from "./ui/AppShell";
// One stylesheet, on purpose: theme.css imports @ai/core/styles.css itself so
// Tailwind sees a single entry graph and generates utilities from both.
import "./ui/theme.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
});

// Standalone, this is where the library is filled: the placement cell imports
// folders, so with nobody signed in it signs in as the placement cell. The
// header's "Viewing as" switch, or ?as=student, shows what a student sees.
// NOT in `routes.tsx`: inside Platform_Shell the session is whoever signed in.
// The dev session, honoured by the backend only under AI_AUTH_MODE=dev.
ensureSession({ role: "placement_officer", subject: "m20-curator", name: "Placement cell" });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell>
          <Routes>
            {m20Routes}
            <Route path="*" element={<Navigate to="/library" replace />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
