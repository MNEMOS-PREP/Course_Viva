/**
 * M20 — Course Viva · routes.
 *
 * Spec: plan_in_depth/M20_Course_Viva.md §8 (UI)
 *
 * The URL is the folder tree: /library/<campus>/<branch>/<year>/<code>. The
 * year is in the path because a course id is its curriculum and its code, and
 * a link a student keeps should still open the course they meant after a newer
 * curriculum is read. Static paths (search, coverage, import, questions) outrank a campus.
 */

import { Route } from "react-router-dom";

import { CampusPage } from "./components/CampusPage";
import { CoursePage } from "./components/CoursePage";
import { CoveragePage } from "./components/CoveragePage";
import { ImportPage } from "./components/ImportPage";
import { LibraryHome } from "./components/LibraryHome";
import { ProgrammePage } from "./components/ProgrammePage";
import { QuestionReview } from "./components/QuestionReview";
import { SearchPage } from "./components/SearchPage";
import { MyVivas } from "./components/MyVivas";
import { VivaProgress } from "./components/VivaProgress";
import { VivaReport } from "./components/VivaReport";
import { VivaRoom } from "./components/VivaRoom";

export const m20Routes = (
  <Route key="m20">
    {/* The viva (phase 2): /viva, a room, its report. `viva` is a noun no
        other module's screens use. */}
    <Route path="/viva" element={<MyVivas />} />
    {/* The student's progress over their vivas: what to work on. */}
    <Route path="/viva/progress" element={<VivaProgress />} />
    <Route path="/viva/:vivaId" element={<VivaRoom />} />
    <Route path="/viva/:vivaId/report" element={<VivaReport />} />
    <Route path="/library" element={<LibraryHome />} />
    <Route path="/library/search" element={<SearchPage />} />
    <Route path="/library/coverage" element={<CoveragePage />} />
    <Route path="/library/import" element={<ImportPage />} />
    {/* The placement cell reviews a material's viva questions (FR-20.14). */}
    <Route path="/library/questions/:materialId" element={<QuestionReview />} />
    <Route path="/library/:campusId" element={<CampusPage />} />
    <Route path="/library/:campusId/:programmeId" element={<ProgrammePage />} />
    <Route path="/library/:campusId/:programmeId/:year/:code" element={<CoursePage />} />
  </Route>
);
