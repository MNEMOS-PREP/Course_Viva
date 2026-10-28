/**
 * The app shell, standalone only: a thin top bar and a wide content area.
 * Inside Platform_Shell the shell's own chrome replaces this (phase 4).
 *
 * The "viewing as" switch is here because what the library shows depends on
 * who is looking — private and held material, the import screen — and a
 * curator checking what a student sees should not need a second browser.
 */

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import { ErrorNote, isStaff, signIn, useSession } from "@ai/core";
import type { Session } from "@ai/core";

import { useHealth } from "../api";
import { ROOT } from "./bits";

const VIEWERS: { label: string; session: Session }[] = [
  {
    label: "Student",
    session: { role: "student", subject: "m20-student", name: "A student" },
  },
  {
    label: "Placement cell",
    session: { role: "placement_officer", subject: "m20-curator", name: "Placement cell" },
  },
];

function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      return (localStorage.getItem("m20.theme") as "light" | "dark") || "light";
    } catch {
      return "light";
    }
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("m20.theme", theme);
    } catch {
      /* private mode: the choice lasts this page */
    }
  }, [theme]);

  return (
    <button
      type="button"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="rounded-md px-2 py-1 text-ink-soft transition-colors hover:bg-surface-sunken hover:text-ink"
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
    >
      <span aria-hidden className="text-sm">
        {theme === "dark" ? "☀" : "☾"}
      </span>
    </button>
  );
}

function ViewingAs() {
  const session = useSession();
  return (
    <div role="group" aria-label="Viewing as" className="flex items-center rounded-md border border-line p-0.5">
      {VIEWERS.map((viewer) => {
        const on = session?.role === viewer.session.role;
        return (
          <button
            key={viewer.label}
            type="button"
            aria-pressed={on}
            onClick={() => signIn(viewer.session)}
            className={`rounded px-2 py-0.5 text-xs font-medium transition-colors ${
              on ? "bg-brand-soft text-brand" : "text-ink-faint hover:text-ink-soft"
            }`}
          >
            {viewer.label}
          </button>
        );
      })}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const session = useSession();
  const health = useHealth();
  const nav = [
    { to: ROOT, label: "Library", end: true },
    { to: `${ROOT}/search`, label: "Search", end: false },
    { to: `${ROOT}/coverage`, label: "Coverage", end: false },
    { to: "/viva", label: "My vivas", end: false },
    ...(isStaff(session) ? [{ to: `${ROOT}/import`, label: "Import a folder", end: false }] : []),
  ];

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-5 py-2.5">
          <Link to={ROOT} className="flex shrink-0 items-center gap-2.5">
            <span
              aria-hidden
              className="grid h-6.5 w-6.5 place-items-center rounded-md bg-brand text-xs font-bold text-on-brand"
            >
              ai
            </span>
            <span className="text-sm font-semibold text-ink">Course Library</span>
          </Link>

          <nav aria-label="Main" className="flex flex-wrap items-center gap-0.5">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  [
                    "rounded-md px-2.5 py-1 text-sm transition-colors",
                    isActive
                      ? "bg-surface-sunken font-medium text-ink"
                      : "text-ink-soft hover:bg-surface-sunken hover:text-ink",
                  ].join(" ")
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <ViewingAs />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8 md:px-8 md:py-10">
        {health.isError && (
          <div className="mb-8">
            <ErrorNote
              message="The library's server is not answering, so nothing below can load."
              detail="Start it with start_viva.bat (port 8120)."
              onRetry={() => health.refetch()}
            />
          </div>
        )}
        {children}
      </main>

      <footer className="border-t border-line px-5 py-5 md:px-8">
        <p className="mx-auto max-w-6xl text-xs text-ink-faint">
          Courses come from the curricula on amrita.edu; material is added by students and the
          placement cell, and is never public outside this platform.
          {health.data?.catalogue_fetched_at &&
            ` Catalogue read ${new Date(health.data.catalogue_fetched_at).toLocaleDateString()}.`}
        </p>
      </footer>
    </div>
  );
}
