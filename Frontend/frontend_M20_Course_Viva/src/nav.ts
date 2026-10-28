/** A module owns its own chrome; the package owns the vocabulary. */
export interface NavItem {
  to: string;
  label: string;
}

/** Nav for M20 running standalone. The platform shell supplies its own. */
export const M20_NAV: NavItem[] = [
  { to: "/library", label: "Course library" },
  { to: "/library/search", label: "Search" },
  { to: "/library/coverage", label: "Coverage" },
  { to: "/viva", label: "My vivas" },
];
