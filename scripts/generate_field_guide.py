#!/usr/bin/env python3
"""Render the Field Guide page from its curated data file.

Unlike the other generators in this directory, this one talks to no API: it
reads ``docs/_data/field_guide.csv`` and writes the tables on
``docs/field-guide.md`` between the ``<!-- FIELD-GUIDE:START -->`` and
``<!-- FIELD-GUIDE:END -->`` markers. Adding a tool to the site therefore
means adding one row to the CSV, which is the whole point - a reviewer can
read the diff without reading any HTML. The rendered page is plain markdown
tables for the same reason: it reads correctly on GitHub as well as on the
built site, and docs/_static/js/field-guide.js layers the language dots and
the filters on top of it in the browser.

The CSV columns are:

``area``
    Functional area heading the tool is listed under. Areas appear on the
    page in the order they first appear in the file, and a tool may be
    listed under more than one area.
``tool``
    Display name.
``url``
    Where a reader should go first (CRAN, PyPI, project site, or repo).
``repo_url``
    Optional source repository, when ``url`` points somewhere else.
``language``
    Predominant language, spelled as GitHub spells it.
``cas_hosted``
    ``yes`` for repositories in https://github.com/casact, ``no`` otherwise.
``description``
    One sentence on what the tool does.

Run ``python scripts/generate_field_guide.py`` after editing the CSV; the
deploy workflow runs it again before building, so the published page cannot
drift from the data file.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_CSV = REPO_ROOT / "docs" / "_data" / "field_guide.csv"
PAGE_MD = REPO_ROOT / "docs" / "field-guide.md"

START_MARKER = "<!-- FIELD-GUIDE:START -->"
END_MARKER = "<!-- FIELD-GUIDE:END -->"

# Languages the data file may use. The Field Guide page renders them as
# plain text and docs/_static/js/field-guide.js attaches the colored dot at
# runtime, using the same linguist colors as the repo tables; this list only
# exists so a typo in the CSV fails the generator instead of quietly landing
# a language the filter cannot group.
KNOWN_LANGUAGES = {
    "Python",
    "R",
    "Julia",
    "Stan",
    "TeX",
    "HTML",
    "Jupyter Notebook",
    "Other",
}

# Text of the Home column, which doubles as the filter's hook: the script
# reads these strings back out of the rendered table.
CAS_HOME = "CAS GitHub"
COMMUNITY_HOME = "Third party"


def md_cell(text: str) -> str:
    """Escape the two characters that would break a markdown table cell."""
    return text.replace("\\", "\\\\").replace("|", "\\|")


def read_rows() -> list[dict]:
    with DATA_CSV.open(newline="", encoding="utf-8") as fh:
        rows = [
            {k: (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(fh)
        ]
    missing = [r for r in rows if not (r.get("area") and r.get("tool") and r.get("url"))]
    if missing:
        raise SystemExit(
            f"{DATA_CSV.name}: every row needs an area, a tool, and a url; "
            f"{len(missing)} row(s) do not."
        )
    unknown = sorted({r["language"] for r in rows} - set(KNOWN_LANGUAGES))
    if unknown:
        raise SystemExit(
            f"{DATA_CSV.name}: unrecognized language(s) {unknown}. Add the "
            "language and its linguist color to LANGUAGE_COLORS in "
            f"{Path(__file__).name}, or spell it as one of "
            f"{sorted(KNOWN_LANGUAGES)}."
        )
    return rows


def build_row(row: dict) -> str:
    tool = f'[{md_cell(row["tool"])}]({row["url"]})'
    if row["repo_url"]:
        tool += f' ([source]({row["repo_url"]}))'
    home = CAS_HOME if row["cas_hosted"] == "yes" else COMMUNITY_HOME
    return (
        f'| {tool} | {md_cell(row["language"])} | {home} '
        f'| {md_cell(row["description"])} |'
    )


def build_area_section(area: str, rows: list[dict]) -> str:
    return "\n".join(
        [
            f"## {area}",
            "",
            "| Tool | Language | Home | What it does |",
            "| --- | --- | --- | --- |",
        ]
        + [build_row(r) for r in rows]
    )


def build_page_body(rows: list[dict]) -> str:
    areas: list[str] = []
    for row in rows:
        if row["area"] not in areas:
            areas.append(row["area"])
    tool_count = len({(r["tool"], r["url"]) for r in rows})
    cas_count = sum(1 for r in rows if r["cas_hosted"] == "yes")
    intro = (
        f"{tool_count} tools across {len(areas)} areas of practice, "
        f"{cas_count} of the listings in the [casact GitHub "
        "organization](https://github.com/casact) and the rest third-party "
        "packages the working group finds useful, listed for convenience and "
        "not endorsed by the CAS. Tools that cover more than one area are "
        "listed under each."
    )
    sections = "\n\n".join(
        build_area_section(area, [r for r in rows if r["area"] == area])
        for area in areas
    )
    return intro + "\n\n" + sections


def replace_between_markers(path: Path, generated: str) -> None:
    text = path.read_text()
    start = text.index(START_MARKER) + len(START_MARKER)
    end = text.index(END_MARKER)
    path.write_text(
        text[:start]
        + "\n<!-- Generated by scripts/generate_field_guide.py from"
        " docs/_data/field_guide.csv - do not edit by hand. -->\n\n"
        + generated
        + "\n\n"
        + text[end:]
    )


def main() -> None:
    rows = read_rows()
    replace_between_markers(PAGE_MD, build_page_body(rows))
    areas = {r["area"] for r in rows}
    print(
        f"Updated {PAGE_MD.name}: {len(rows)} rows across {len(areas)} areas.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
