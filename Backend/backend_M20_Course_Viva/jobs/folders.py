"""The folder tree from the command line (FR-20.6, FR-20.7).

    python -m backend_M20_Course_Viva.jobs.folders scaffold "<where>"
    python -m backend_M20_Course_Viva.jobs.folders import "<where>/Amrita University" --dry-run
    python -m backend_M20_Course_Viva.jobs.folders import "<where>/Amrita University"

`scaffold` creates Amrita University/<campus>/<branch>/Semester_<n>/<course>/
for every course the catalogue holds. `import` adds every file found there;
the dry run lists where each file goes and anything that cannot be placed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlmodel import Session

from .. import catalogue, db, importer


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold or import the library's folder tree")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scaffold", help="create the empty folder tree")
    s.add_argument("target", type=Path)
    i = sub.add_parser("import", help="import every file in a folder tree")
    i.add_argument("root", type=Path)
    i.add_argument("--dry-run", action="store_true")
    i.add_argument("--shared", action="store_true", help="do not record the campus folder")
    i.add_argument("--added-by", default="folder-import")
    args = parser.parse_args()

    db.init()
    with Session(db.engine) as session:
        catalogue.load_if_newer(session)
        if args.command == "scaffold":
            counts = importer.scaffold(session, args.target)
            print(f"created {counts} under {args.target}")
            return 0
        root: Path = args.root
        files = [p for p in root.rglob("*") if p.is_file()]
        # Paths relative to the folder ABOVE the root, so the campus folder is in them.
        relatives = {p.relative_to(root.parent).as_posix(): p for p in files}
        if args.dry_run:
            found = importer.plan(session, list(relatives))
            for placement in found.placed:
                print(f"  + {placement.path}  ->  {placement.course_id} [{placement.kind}]")
            for problem in found.problems:
                print(f"  ! {problem['path']}: {problem['reason']}")
            print(f"{len(found.placed)} would be added, {len(found.problems)} cannot be placed")
            return 0
        result = importer.run(
            session,
            {rel: path.read_bytes() for rel, path in relatives.items()},
            args.added_by,
            shared=args.shared,
        )
        for problem in result["problems"]:
            print(f"  ! {problem['path']}: {problem['reason']}")
        print(
            f"added {result['added']}, already there {result['already_there']}, "
            f"not placed {len(result['problems'])}"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
