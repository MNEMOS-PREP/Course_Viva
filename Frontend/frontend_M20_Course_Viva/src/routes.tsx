/**
 * M20 — Course Viva · routes.
 *
 * Spec: plan_in_depth/M20_Course_Viva.md §8 (UI)
 *
 * The URL is the folder tree: /library/<campus>/<branch>/<year>/<code>. The
 * year is in the path because a course id is its curriculum and its code, and
 * a link a student keeps should still open the course they meant after a newer
 * curriculum is read. Static paths (search, coverage, import) outrank a campus.
 */

import { Route } from "react-router-dom";

import { CampusPage } from "./components/CampusPage";
import { CoursePage } from "./components/CoursePage";
import { CoveragePage } from "./components/CoveragePage";
import { ImportPage } from "./components/ImportPage";
import { LibraryHome } from "./components/LibraryHome";
import { ProgrammePage } from "./components/ProgrammePage";
import { SearchPage } from "./components/SearchPage";

export const m20Routes = (
  <Route key="m20">
    <Route path="/library" element={<LibraryHome />} />
    <Route path="/library/search" element={<SearchPage />} />
    <Route path="/library/coverage" element={<CoveragePage />} />
    <Route path="/library/import" element={<ImportPage />} />
    <Route path="/library/:campusId" element={<CampusPage />} />
    <Route path="/library/:campusId/:programmeId" element={<ProgrammePage />} />
    <Route path="/library/:campusId/:programmeId/:year/:code" element={<CoursePage />} />
  </Route>
);
