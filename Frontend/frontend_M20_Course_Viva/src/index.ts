/**
 * M20 — Course Viva · public surface.
 *
 * Anything not exported here is private to this module. Platform_Shell mounts
 * `m20Routes` (phase 4); the viva screens (/viva) are among them.
 */

export { m20Routes } from "./routes";
export { M20_NAV } from "./nav";
export { AppShell } from "./ui/AppShell";
export { useCourse, useSearch, useTree } from "./api";
export type { CourseView, Material, SearchResult, Tree } from "./types";
