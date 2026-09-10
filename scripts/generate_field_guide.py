#!/usr/bin/env python3
"""Render the Field Guide page from its curated data file.

Unlike the other generators in this directory, this one talks to no API: it
reads ``docs/_data/field_guide.csv`` and writes the tables on
``docs/field-guide.md`` between the ``<!-- FIELD-GUIDE:START -->`` and
``<!-- FIELD-GUIDE:END -->`` markers. Adding a tool to the site therefore
means adding one row to the CSV, which is the whole point - a reviewer can
read the diff without reading any HTML.

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
import html
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_CSV = REPO_ROOT / "docs" / "_data" / "field_guide.csv"
PAGE_MD = REPO_ROOT / "docs" / "field-guide.md"

START_MARKER = "<!-- FIELD-GUIDE:START -->"
END_MARKER = "<!-- FIELD-GUIDE:END -->"

# GitHub's own linguist colors, kept in step with the map in github_api.py.
# Duplicated rather than imported so this script stays dependency-free and
# can run in the docs build job, which does not install ``requests``.
LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "R": "#198CE7",
    "Julia": "#a270ba",
    "Stan": "#b2011d",
    "TeX": "#3D6117",
    "HTML": "#e34c26",
    "Jupyter Notebook": "#DA5B0B",
}
DEFAULT_LANGUAGE_COLOR = "#8a8a8a"

# Chips offered in the filter bar, in display order: (group key, label).
LANGUAGE_GROUPS = [("r", "R"), ("python", "Python"), ("julia", "Julia"), ("other", "Other")]


def language_group(language: str) -> str:
    """Collapse a language into one of the filter groups."""
    key = language.strip().lower()
    return key if key in {"r", "python", "julia"} else "other"


def lang_cell(language: str) -> str:
    """A colored dot plus the language name, matching the repo tables."""
    language = language.strip()
    if not language or language == "Other":
        return '<span class="cas-repo-lang cas-fg-lang-none">&mdash;</span>'
    color = LANGUAGE_COLORS.get(language, DEFAULT_LANGUAGE_COLOR)
    return (
        f'<span class="cas-repo-lang"><span class="cas-lang-dot" '
        f'style="background-color:{color}"></span>{html.escape(language)}</span>'
    )


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
    return rows


def build_tool_cell(row: dict) -> str:
    name = html.escape(row["tool"])
    link = (
        f'<a href="{html.escape(row["url"], quote=True)}" target="_blank" '
        f'rel="noopener">{name}</a>'
    )
    badge = (
        ' <span class="cas-fg-badge" title="Hosted in the casact GitHub '
        'organization">CAS</span>'
        if row["cas_hosted"] == "yes"
        else ""
    )
    repo = ""
    if row["repo_url"]:
        repo = (
            f' <a class="cas-fg-repo-link" href="{html.escape(row["repo_url"], quote=True)}" '
            'target="_blank" rel="noopener" title="Source repository">source</a>'
        )
    return f'<td class="cas-repo-name cas-fg-tool">{link}{badge}{repo}</td>'


def build_row(row: dict) -> str:
    return (
        f'<tr data-lang="{language_group(row["language"])}" '
        f'data-cas="{"yes" if row["cas_hosted"] == "yes" else "no"}">\n'
        f"  {build_tool_cell(row)}\n"
        f'  <td class="cas-fg-lang">{lang_cell(row["language"])}</td>\n'
        f'  <td>{html.escape(row["description"])}</td>\n'
        "</tr>"
    )


def build_filter_bar(rows: list[dict]) -> str:
    chips = "\n".join(
        f'    <button type="button" class="cas-fg-chip" data-filter-lang="{key}">'
        f"{label}</button>"
        for key, label in LANGUAGE_GROUPS
    )
    cas_count = sum(1 for r in rows if r["cas_hosted"] == "yes")
    return (
        "```{raw} html\n"
        '<div class="cas-fg-filters" data-total="' + str(len(rows)) + '">\n'
        '  <div class="cas-fg-chiprow">\n'
        '    <span class="cas-fg-chiplabel">Language</span>\n'
        '    <button type="button" class="cas-fg-chip is-active" '
        'data-filter-lang="all">All</button>\n'
        f"{chips}\n"
        "  </div>\n"
        '  <div class="cas-fg-chiprow">\n'
        '    <span class="cas-fg-chiplabel">Home</span>\n'
        '    <button type="button" class="cas-fg-chip is-active" '
        'data-filter-cas="all">Everywhere</button>\n'
        '    <button type="button" class="cas-fg-chip" data-filter-cas="yes">'
        f"CAS GitHub ({cas_count})</button>\n"
        "  </div>\n"
        '  <p class="cas-fg-count" role="status" aria-live="polite"></p>\n'
        '  <p class="cas-fg-empty" hidden>Nothing is listed under that '
        "combination yet. That is usually a gap rather than a verdict, and a "
        'gap is a contributable thing.</p>\n'
        "</div>\n"
        "```"
    )


def build_area_section(area: str, rows: list[dict]) -> str:
    body = "\n".join(build_row(r) for r in rows)
    return (
        f"## {area}\n\n"
        "```{raw} html\n"
        '<div class="cas-repo-table-wrap cas-fg-table-wrap">\n'
        '<table class="cas-repo-table cas-fg-table">\n'
        "<thead>\n<tr>\n"
        "  <th>Tool</th>\n  <th>Language</th>\n  <th>What it does</th>\n"
        "</tr>\n</thead>\n<tbody>\n"
        f"{body}\n"
        "</tbody>\n</table>\n</div>\n"
        "```"
    )


def build_page_body(rows: list[dict]) -> str:
    areas: list[str] = []
    for row in rows:
        if row["area"] not in areas:
            areas.append(row["area"])
    tool_count = len({(r["tool"], r["url"]) for r in rows})
    intro = (
        f"{tool_count} tools across {len(areas)} areas of practice. Entries "
        "marked **CAS** live in the [casact GitHub "
        "organization](https://github.com/casact); the rest are third-party "
        "packages the working group finds useful, listed for convenience and "
        "not endorsed by the CAS. Several tools appear under more than one "
        "area, because several tools do more than one thing."
    )
    sections = "\n\n".join(
        build_area_section(area, [r for r in rows if r["area"] == area])
        for area in areas
    )
    return intro + "\n\n" + build_filter_bar(rows) + "\n\n" + sections


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
