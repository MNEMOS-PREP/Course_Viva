"""Sync the catalogue from the university's own pages (spec §6.1, FR-20.2).

    python -m backend_M20_Course_Viva.jobs.sync_catalogue            # fetch, parse, write
    python -m backend_M20_Course_Viva.jobs.sync_catalogue --no-pdfs  # skeleton only, fast

Writes `packages/catalogue/amrita.json`, which the API loads at start. Nothing
in it is typed by us (spec Trap 2):

1. `amrita.edu/academics/curriculum/` — the Engineering › B.Tech and the
   Artificial Intelligence sections: every programme, its regulation years and
   each year's curriculum/syllabus PDFs.
2. Each programme's own page (`/program/<slug>/`) — "Programs offered at the
   following campus": the campus matrix. Programme pages are found from the
   site's menu by name, so a programme the university adds is picked up.
3. Each programme's latest single-PDF curriculum (the 2019+ layout) — its
   semesters, courses, elective baskets and syllabi (`curriculum_pdf.py`).

Every programme and curriculum keeps its source URL; the file keeps the fetch
time. One request a second; robots.txt allows /program/ and the PDFs. A PDF
that will not parse leaves its curriculum `listed` with the PDF linked, never
half-filled (EC-20.2). A link whose label is not a document name (the 2023
Robotics & AI entry "&" points at a 2017 Mechanical PDF) is dropped and
reported (EC-20.3).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup

SITE = "https://www.amrita.edu"
CURRICULUM_PAGE = f"{SITE}/academics/curriculum/"
INSTITUTION = {"id": "amrita", "name": "Amrita Vishwa Vidyapeetham", "display": "Amrita University"}
#: The campuses in scope (the user's call, 2026-10-21). Others found on the
#: programme pages are kept per programme as `also_at`, not dropped silently.
CAMPUSES = ("Amritapuri", "Coimbatore", "Bengaluru", "Chennai", "Amaravati")
KNOWN_CAMPUSES = CAMPUSES + ("Nagercoil", "Haridwar", "Faridabad", "Mysuru", "Kochi")
#: The sections in scope: Engineering's B.Tech and the AI school.
SECTIONS = (("Engineering", "B.Tech"), ("Artificial Intelligence", None))
AGENT = "Mozilla/5.0 (MNEMOS-PREP course catalogue; local, polite)"
PAUSE_SECONDS = 1.0
ACC = "wp-block-ub-content-toggle-accordion"
#: Children of B.Tech that are not programmes.
NOT_PROGRAMMES = re.compile(r"^(regulations|introduction of minor)", re.I)
SINGLE_PDF = re.compile(r"curriculum\s*(and|&)\s*syllabus", re.I)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "packages" / "catalogue" / "amrita.json"
CACHE = ROOT / "Backend" / ".cache" / "sync"


# ── fetching ──────────────────────────────────────────────────────────────


def fetch(url: str, cache: Path, *, binary: bool = False) -> bytes:
    """GET with a polite pause, cached on disk so a re-run is quick."""
    cache.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[-1])[-150:]
    path = cache / name
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    path.write_bytes(data)
    time.sleep(PAUSE_SECONDS)
    return data


def soup_of(url: str, cache: Path) -> BeautifulSoup:
    return BeautifulSoup(fetch(url, cache).decode("utf-8", "replace"), "html.parser")


# ── names ─────────────────────────────────────────────────────────────────

_DEGREE = re.compile(r"^\s*b\.?\s*tech\.?\s*(in\s+)?", re.I)
_TRAIL_ABBR = re.compile(r"\s*[–-]\s*[A-Z][A-Za-z&() ]*$|\s*\((?:[A-Z&]{2,6})\)\s*$")
_STOP = {"and", "in", "of", "the", "b", "tech", "btech"}


def clean_name(raw: str) -> str:
    """ "B. Tech. in Mechanical Engineering" -> "Mechanical Engineering"."""
    name = " ".join(raw.replace(" ", " ").split())
    name = _DEGREE.sub("", name)
    name = _TRAIL_ABBR.sub("", name).strip(" .–-")
    return name


def tokens(name: str) -> set[str]:
    text = clean_name(name).casefold().replace("&", " and ").replace("(ai)", " ")
    text = text.replace("sciences", "science")
    return {t for t in re.findall(r"[a-z0-9]+", text) if t not in _STOP}


def best_match(name: str, candidates: dict[str, str]) -> str | None:
    """The candidate whose words best match (Jaccard), if every word of the
    shorter appears in the longer: "Automation and Robotics" finds
    "Automation & Robotics Engineering"; "Computer Science and Engineering"
    finds itself, not its "(Artificial Intelligence)" variant."""
    mine = tokens(name)
    scored = []
    for key, value in candidates.items():
        theirs = tokens(key)
        if not mine or not theirs:
            continue
        shorter, longer = sorted((mine, theirs), key=len)
        if not shorter <= longer:
            continue
        scored.append((len(mine & theirs) / len(mine | theirs), value))
    return max(scored)[1] if scored else None


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


# ── the curriculum page ───────────────────────────────────────────────────


def _title(acc) -> str:
    wrap = acc.find("div", class_=f"{ACC}-title-wrap", recursive=False)
    p = wrap.find(class_=f"{ACC}-title") if wrap else None
    return " ".join(p.get_text(" ", strip=True).split()) if p else ""


def _region(acc):
    return acc.find("div", class_=f"{ACC}-content-wrap", recursive=False)


def _children(region) -> list:
    return [
        el
        for el in region.find_all("div", class_=ACC)
        if (parent := el.find_parent("div", class_=ACC)) is not None and _region(parent) is region
    ]


def _node(acc) -> dict:
    region = _region(acc)
    out: dict = {"title": _title(acc)}
    if region is None:
        return out
    kids = _children(region)
    if kids:
        out["children"] = [_node(k) for k in kids]
    else:
        out["links"] = [
            {"label": " ".join(a.get_text(" ", strip=True).split()), "url": a["href"]}
            for a in region.find_all("a", href=True)
        ]
    return out


def read_curriculum_page(soup: BeautifulSoup) -> tuple[list[dict], list[str]]:
    """Programmes in the sections in scope, each with its curricula by year."""
    tops = [
        _node(a)
        for a in soup.find_all("div", class_=ACC)
        if a.find_parent("div", class_=ACC) is None
    ]
    warnings: list[str] = []
    programmes: dict[str, dict] = {}
    for section, degree in SECTIONS:
        top = next((t for t in tops if t["title"].strip().casefold() == section.casefold()), None)
        if top is None:
            warnings.append(f"section {section!r} not found on the curriculum page")
            continue
        holder = top
        if degree:
            holder = next(
                (
                    c
                    for c in top.get("children", [])
                    if c["title"].replace(" ", "").rstrip(".").casefold()
                    == degree.replace(".", "").casefold().replace(" ", "")
                    or c["title"].casefold().startswith(degree.casefold())
                ),
                None,
            )
            if holder is None:
                warnings.append(f"{section} › {degree} not found")
                continue
        for child in holder.get("children", []):
            if NOT_PROGRAMMES.match(child["title"]):
                continue
            name = clean_name(child["title"])
            entry = programmes.setdefault(
                slugify(name), {"name": name, "school": section, "curricula": [], "titles": []}
            )
            entry["titles"].append(child["title"])
            for year_node in child.get("children", []):
                match = re.search(r"(19|20)\d\d", year_node["title"])
                if not match:
                    continue
                docs = []
                for link in year_node.get("links", []):
                    if not re.search(r"[A-Za-z]{3}", link["label"]):
                        warnings.append(
                            f"{name} {match.group(0)}: dropped a link labelled {link['label']!r} "
                            f"({link['url'].rsplit('/', 1)[-1]})"
                        )
                        continue
                    docs.append(link)
                if docs and not any(c["year"] == int(match.group(0)) for c in entry["curricula"]):
                    entry["curricula"].append({"year": int(match.group(0)), "documents": docs})
    return list(programmes.values()), warnings


def programme_pages(soup: BeautifulSoup) -> dict[str, str]:
    """Programme name -> its /program/ page, from the site's own menu."""
    pages: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        label = " ".join(a.get_text(" ", strip=True).split())
        if "/program/" in href and re.search(r"b\.?\s*tech", label, re.I):
            pages.setdefault(label, href if href.startswith("http") else SITE + href)
    return pages


def offered_at(soup: BeautifulSoup) -> list[str]:
    for tag in soup.find_all(["nav", "header", "footer"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    match = re.search(r"offered at the following campus(.*?)(?:Navigation|Overview)", text)
    if not match:
        return []
    return [c for c in KNOWN_CAMPUSES if re.search(rf"\b{c}\b", match.group(1))]


# ── the short name ────────────────────────────────────────────────────────


#: Course-code prefixes every branch shares (first-year sciences, humanities):
#: they never name a department.
COMMON_PREFIXES = {
    "MAT", "ENG", "CIR", "SSK", "HUM", "PHY", "CHY", "AVP", "FNA", "ADM", "CUL", "ENV",
    "SPR", "EVS",
}  # fmt: skip
#: "… – AID (AA&RS)", "… (RAI)", "… (CSE)": the university's own abbreviation.
_OFFICIAL = re.compile(r"[–-]\s*([A-Z]{2,5}(?:\s*\([A-Z&]{2,8}\))?)\s*$|\(([A-Z]{2,5})\)\s*$")


def official_short(*titles: str | None) -> str | None:
    for title in titles:
        if title and (m := _OFFICIAL.search(" ".join(title.split()))):
            return m.group(1) or m.group(2)
    return None


def code_prefix(curriculum: dict | None) -> str | None:
    """The department's own course-code prefix (CSE in 23CSE201, AIE, ECE)."""
    if not curriculum or not curriculum.get("semesters"):
        return None
    prefixes = Counter(
        c["code"][2:5] for s in curriculum["semesters"] for c in s["courses"] if c.get("code")
    )
    return next((p for p, _ in prefixes.most_common() if p not in COMMON_PREFIXES), None)


def _parts(name: str) -> tuple[str, str | None]:
    """ "AI (AI) and Data Science (Quantum Technologies)" -> (main, "Quantum Technologies")."""
    main = name.replace("(AI)", " ")
    match = re.search(r"\(([^)]*)\)\s*$", main)
    paren = match.group(1) if match else None
    main = main[: match.start()] if match else main
    return " ".join(main.split()), paren


def initials(text: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z]+", text) if w.casefold() not in _STOP]
    return "".join(w[0].upper() for w in words)[:6] or "PRG"


def assign_shorts(programmes: list[dict]) -> None:
    """A short name per branch, unique, from the university's own usage:

    1. an abbreviation printed in its title on the site ("AID (AA&RS)", "RAI");
    2. else its department's course-code prefix, if no other branch's courses
       carry it (CSE, AIE, ECE — what students see on every course code);
    3. else its family's base and the variant's initials — the base taken from
       the family root or an official sibling: "AID (QT)", "CSE (QC)".
    """
    prefixes = Counter(code_prefix(p["parsed"]) for p in programmes if code_prefix(p["parsed"]))
    for p in programmes:
        prefix = code_prefix(p["parsed"])
        p["short"] = official_short(*p["titles"]) or (
            prefix if prefix and prefixes[prefix] == 1 else None
        )
    taken = Counter(p["short"] for p in programmes if p["short"])
    bases: dict[str, str] = {}
    for root_first in (True, False):  # a family root's short beats a variant's
        for p in programmes:
            main, paren = _parts(p["name"])
            if p["short"] and taken[p["short"]] == 1 and (paren is None) == root_first:
                bases.setdefault(main.casefold(), p["short"].split(" (")[0])
    for p in programmes:
        if p["short"] and taken[p["short"]] == 1:
            continue
        main, paren = _parts(p["name"])
        base = bases.get(main.casefold()) or initials(main)
        p["short"] = f"{base} ({initials(paren)})" if paren else base


# ── assembling ───────────────────────────────────────────────────────────


def parse_latest(entry: dict, cache: Path, warnings: list[str], parse_pdfs: bool) -> None:
    """Parse each programme's newest single-PDF curriculum; list the rest."""
    from .curriculum_pdf import read_curriculum

    for curriculum in entry["curricula"]:
        curriculum["status"] = "listed"
    if not parse_pdfs:
        return
    for curriculum in sorted(entry["curricula"], key=lambda c: -c["year"]):
        doc = next((d for d in curriculum["documents"] if SINGLE_PDF.search(d["label"])), None)
        if doc is None or not doc["url"].casefold().endswith(".pdf"):
            continue
        try:
            pdf = cache / "pdfs" / doc["url"].rsplit("/", 1)[-1]
            pdf.parent.mkdir(parents=True, exist_ok=True)
            if not pdf.exists():
                pdf.write_bytes(fetch(doc["url"], cache / "raw", binary=True))
            parsed, notes = read_curriculum(pdf)
        except Exception as exc:  # noqa: BLE001 - recorded, and the curriculum stays listed
            curriculum["status"] = "failed"
            curriculum["warnings"] = [f"could not parse {doc['url']}: {exc}"]
            warnings.append(f"{entry['name']} {curriculum['year']}: {exc}")
            continue
        courses = sum(len(s["courses"]) for s in parsed["semesters"])
        if courses == 0:
            curriculum["status"] = "failed"
            curriculum["warnings"] = ["no course rows found; this PDF's layout is not read yet"]
            continue
        curriculum.update(parsed)
        curriculum["status"] = "parsed"
        curriculum["parsed_from"] = doc["url"]
        curriculum["warnings"] = notes[:40]
        return  # the newest parsed one is enough for now; older years stay listed


def build(parse_pdfs: bool = True, cache: Path = CACHE) -> tuple[dict, list[str]]:
    page = soup_of(CURRICULUM_PAGE, cache)
    programmes, warnings = read_curriculum_page(page)
    pages = programme_pages(page)
    out_programmes = []
    for entry in sorted(programmes, key=lambda p: p["name"]):
        url = best_match(entry["name"], pages)
        campuses: list[str] = []
        if url:
            try:
                campuses = offered_at(soup_of(url, cache))
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{entry['name']}: programme page failed: {exc}")
        else:
            warnings.append(f"{entry['name']}: no programme page found on the site's menu")
        parse_latest(entry, cache, warnings, parse_pdfs)
        menu_titles = [label for label, href in pages.items() if href == url]
        out_programmes.append(
            {
                # From the name alone, so an id survives a change of short name.
                "id": "btech-" + slugify(entry["name"])[:60],
                "degree": "B.Tech",
                "name": entry["name"],
                "short": None,
                "school": entry["school"],
                "source_url": url,
                "campuses": [c.casefold() for c in campuses if c in CAMPUSES],
                "also_at": [c for c in campuses if c not in CAMPUSES],
                "curricula": sorted(entry["curricula"], key=lambda c: -c["year"]),
                "titles": entry["titles"] + menu_titles,
                "parsed": next(
                    (c for c in entry["curricula"] if c.get("status") == "parsed"), None
                ),
            }
        )
    assign_shorts(out_programmes)
    for p in out_programmes:
        del p["titles"], p["parsed"]
    catalogue = {
        "institution": INSTITUTION,
        "campuses": [{"id": c.casefold(), "name": c} for c in CAMPUSES],
        "programmes": out_programmes,
        "sources": {"curriculum_page": CURRICULUM_PAGE},
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    return catalogue, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync the course catalogue from amrita.edu")
    parser.add_argument("--no-pdfs", action="store_true", help="skip parsing curriculum PDFs")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    catalogue, warnings = build(parse_pdfs=not args.no_pdfs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(catalogue, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for p in catalogue["programmes"]:
        parsed = next((c for c in p["curricula"] if c.get("status") == "parsed"), None)
        detail = (
            f"{parsed['year']}: {sum(len(s['courses']) for s in parsed['semesters'])} courses in "
            f"{len(parsed['semesters'])} semesters, {len(parsed.get('warnings', []))} notes"
            if parsed
            else "no parsed curriculum"
        )
        print(
            f"{p['short']:6} {p['name'][:60]:60} "
            f"campuses={','.join(p['campuses']) or '-':40} {detail}"
        )
    for w in warnings:
        print(f"  ! {w}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
