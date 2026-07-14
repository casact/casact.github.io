#!/usr/bin/env python3
"""Regenerate the "Metrics" section of docs/projects.md, plus the homepage
contribution heatmap, from live GitHub data.

Python + matplotlib port of casact/meta's git_metrics/core_metrics.Rmd
(https://github.com/casact/meta/blob/master/git_metrics/core_metrics.Rmd).

Matplotlib charts are written to docs/_static/images/metrics/; the
contribution heatmap is hand-built inline SVG instead (see
build_heatmap_svg), so its cells can carry native tooltips and respond to
CSS :hover - both are impossible for a chart embedded via <img>, which
sandboxes the SVG from the page entirely. The markdown between the
``<!-- METRICS:START/END -->`` markers in docs/projects.md and the
``<!-- HEATMAP:START/END -->`` markers in docs/index.md is replaced with
freshly generated tables and figures. Run as part of
.github/workflows/deploy-docs.yml (on push, daily at 06:00 UTC, and on
manual dispatch).
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github_api import (  # noqa: E402
    fetch_closed_issues,
    fetch_commits,
    fetch_org_repos,
    fetch_pull_requests,
    parse_date,
)

ACCOUNT_ESTABLISHED = date(2019, 8, 1)

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "docs" / "_static" / "images" / "metrics"
PROJECTS_MD = REPO_ROOT / "docs" / "projects.md"
INDEX_MD = REPO_ROOT / "docs" / "index.md"
FONTS_DIR = Path(__file__).resolve().parent / "fonts"

NAVY = "#002D72"
TEXT = "#1c2531"
AXIS_LINE = "#8a8a8a"

FONT_BODY = "Source Sans 3"
FONT_HEADING = "Montserrat"

# Same blues used across the site (docs/_static/css/custom.css: --cas-navy,
# --cas-blue-light) for the contribution heatmap. The lightest stop is
# deliberately not near-white, so active-but-quiet days stay visible against
# the page background; zero-activity days use HEATMAP_GREY instead, same as
# GitHub's own empty cells.
HEATMAP_GREY = "#ebedf0"

# Same typefaces as the site's own CSS (docs/_static/css/custom.css). These
# are static weight instances of the variable Google Fonts files, since
# matplotlib/freetype can't select a variable font's weight axis on its own.
for _font_path in (FONTS_DIR / "SourceSans3-Regular.ttf", FONTS_DIR / "Montserrat-Bold.ttf"):
    fm.fontManager.addfont(str(_font_path))

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": AXIS_LINE,
        "axes.linewidth": 1,
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.axisbelow": True,
        "font.family": FONT_BODY,
        "font.size": 11,
        "axes.labelcolor": TEXT,
        "text.color": TEXT,
        "xtick.color": TEXT,
        "ytick.color": TEXT,
        # Sphinx embeds these via <img>, which sandboxes the SVG from the
        # page's own stylesheet/fonts - a font-family reference alone won't
        # resolve there, so bake the glyphs in as vector outlines instead.
        # Still crisp at any zoom/DPI, unlike a raster PNG.
        "svg.fonttype": "path",
    }
)

SAVEFIG_KWARGS = {"transparent": True}


def style_axes(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(
        title, fontfamily=FONT_HEADING, fontweight="bold", fontsize=13, color=NAVY, loc="center", pad=12
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)


def save_barh(
    path: Path, labels: list[str], values: list[int], title: str, xlabel: str, ylabel: str
) -> None:
    height = max(5, len(labels) * 0.22)
    fig, ax = plt.subplots(figsize=(7, height))
    ax.barh(labels, values, color=NAVY)
    style_axes(ax, title, xlabel, ylabel)
    fig.tight_layout()
    fig.savefig(path, **SAVEFIG_KWARGS)
    plt.close(fig)


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _heatmap_tooltip(d: date, count: int) -> str:
    when = f"{d.strftime('%B')} {_ordinal(d.day)}"
    if count == 0:
        return f"No contributions on {when}."
    unit = "contribution" if count == 1 else "contributions"
    return f"{count} {unit} on {when}."


HEATMAP_BUCKET_COLORS = ["#bfe3f0", "#74d2e7", "#1c6ea8", "#002D72"]


def build_heatmap_svg(commits_by_date: dict, weeks: int = 53) -> tuple[str, int]:
    """A GitHub-style contribution calendar as hand-built inline SVG.

    This is embedded directly in docs/index.md rather than saved as a file
    and loaded via <img>, because <img>-embedded SVGs are sandboxed from the
    page's CSS/JS entirely - neither :hover styling nor a native per-cell
    <title> tooltip (GitHub's "n contributions on <date>") works otherwise.

    Returns (svg_markup, total_contributions_in_window).
    """
    end = date.today()
    start = end - timedelta(weeks=weeks)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # snap back to a Sunday

    cell, gap = 11, 3
    pitch = cell + gap
    left_pad, top_pad, bottom_pad = 28, 20, 24

    days = []
    month_ticks: dict[int, str] = {}
    for i in range((end - start).days + 1):
        d = start + timedelta(days=i)
        week_idx = (d - start).days // 7
        dow = (d.weekday() + 1) % 7  # Sunday=0 .. Saturday=6
        count = commits_by_date.get(d, 0)
        days.append((d, week_idx, dow, count))
        if d.day <= 7 and dow == 0:
            month_ticks[week_idx] = d.strftime("%b")
    num_weeks = max(w for _, w, _, _ in days) + 1
    total = sum(c for _, _, _, c in days)

    nonzero = sorted(c for _, _, _, c in days if c > 0)
    vmax = max(1, nonzero[int(len(nonzero) * 0.95)] if nonzero else 1)

    def color_for(count: int) -> str:
        if count <= 0:
            return HEATMAP_GREY
        frac = count / vmax
        if frac <= 0.25:
            return HEATMAP_BUCKET_COLORS[0]
        if frac <= 0.5:
            return HEATMAP_BUCKET_COLORS[1]
        if frac <= 0.75:
            return HEATMAP_BUCKET_COLORS[2]
        return HEATMAP_BUCKET_COLORS[3]

    width = left_pad + num_weeks * pitch
    height = top_pad + 7 * pitch + bottom_pad

    parts = [
        f'<svg class="cas-heatmap-svg" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="Contribution activity calendar">'
    ]

    for week_idx, label in month_ticks.items():
        x = left_pad + week_idx * pitch
        parts.append(f'<text x="{x}" y="{top_pad - 8}" class="cas-heatmap-label">{label}</text>')

    for dow, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = top_pad + dow * pitch + cell - 1
        parts.append(
            f'<text x="{left_pad - 6}" y="{y}" text-anchor="end" '
            f'class="cas-heatmap-label">{label}</text>'
        )

    for d, week_idx, dow, count in days:
        x = left_pad + week_idx * pitch
        y = top_pad + dow * pitch
        parts.append(
            f'<rect class="cas-heatmap-cell" x="{x}" y="{y}" width="{cell}" height="{cell}" '
            f'rx="2" ry="2" fill="{color_for(count)}"><title>{_heatmap_tooltip(d, count)}'
            f"</title></rect>"
        )

    # "Less -> More" legend, bottom-right, like GitHub's own heatmap.
    legend_colors = [HEATMAP_GREY] + HEATMAP_BUCKET_COLORS
    legend_y = top_pad + 7 * pitch + 10
    legend_x0 = width - len(legend_colors) * pitch - 32
    parts.append(
        f'<text x="{legend_x0 - 6}" y="{legend_y + cell - 1}" text-anchor="end" '
        f'class="cas-heatmap-label">Less</text>'
    )
    for i, color in enumerate(legend_colors):
        x = legend_x0 + i * pitch
        parts.append(
            f'<rect x="{x}" y="{legend_y}" width="{cell}" height="{cell}" '
            f'rx="2" ry="2" fill="{color}"></rect>'
        )
    parts.append(
        f'<text x="{legend_x0 + len(legend_colors) * pitch + 4}" y="{legend_y + cell - 1}" '
        f'class="cas-heatmap-label">More</text>'
    )
    parts.append("</svg>")
    return "".join(parts), total


def replace_between_markers(path: Path, start_marker: str, end_marker: str, generated: str) -> None:
    text = path.read_text()
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker)
    script_name = Path(__file__).name
    new_text = (
        text[:start]
        + f"\n<!-- Generated by scripts/{script_name} - do not edit by hand. -->\n\n"
        + generated
        + "\n\n"
        + text[end:]
    )
    path.write_text(new_text)


def html_table(headers: list[str], rows: list[tuple]) -> str:
    head = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
    body = "\n".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return (
        '<table class="cas-repo-table">\n<thead>\n'
        + head
        + "\n</thead>\n<tbody>\n"
        + body
        + "\n</tbody>\n</table>"
    )


def image_md(alt: str, filename: str) -> str:
    return f"![{alt}](/_static/images/metrics/{filename})"


def rubric(title: str) -> str:
    return f"```{{rubric}} {title}\n```"


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()

    print("Fetching repositories...", file=sys.stderr)
    repos = fetch_org_repos()
    repo_count = len(repos)
    for r in repos:
        r["_created"] = parse_date(r["created_at"])

    # -- Chart: cumulative repo count over time --------------------------
    running = 0
    by_date: dict[date, int] = {}
    for r in sorted(repos, key=lambda r: r["_created"]):
        running += 1
        if r["_created"] > ACCOUNT_ESTABLISHED:
            by_date[r["_created"]] = running
    xs = sorted(by_date)
    ys = [by_date[d] for d in xs]
    xs.append(today)
    ys.append(repo_count)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.step(xs, ys, where="post", color=NAVY, linewidth=2)
    ax.set_ylim(bottom=0)
    style_axes(ax, "Cumulative repository count", "Date", "Number of repositories")
    fig.tight_layout()
    fig.savefig(IMAGES_DIR / "repo_growth.svg", **SAVEFIG_KWARGS)
    plt.close(fig)

    # -- Chart: repo count by predominant language ------------------------
    lang_counts = Counter(r["language"] for r in repos if r.get("language"))
    items = sorted(lang_counts.items(), key=lambda kv: kv[1])
    save_barh(
        IMAGES_DIR / "by_language.svg",
        [k for k, _ in items],
        [v for _, v in items],
        "Repositories by language",
        "Count",
        "Language",
    )

    # -- Chart: stars per repo ----------------------------------------------
    # GitHub's REST API aliases `watchers_count` to the star count these
    # days (real "watching" activity isn't exposed in this endpoint), so
    # label this as stars rather than watchers.
    starred = sorted(
        ((r["name"], r.get("stargazers_count", 0)) for r in repos if r.get("stargazers_count", 0) > 0),
        key=lambda kv: kv[1],
    )
    save_barh(
        IMAGES_DIR / "stars.svg",
        [k for k, _ in starred],
        [v for _, v in starred],
        "Stars by repository",
        "Stars",
        "Repository",
    )

    # -- Chart: forks per repo ---------------------------------------------
    forked = sorted(
        ((r["name"], r.get("forks_count", 0)) for r in repos if r.get("forks_count", 0) > 0),
        key=lambda kv: kv[1],
    )
    save_barh(
        IMAGES_DIR / "forks.svg",
        [k for k, _ in forked],
        [v for _, v in forked],
        "Forks by repository",
        "Forks",
        "Repository",
    )

    # -- Commits ------------------------------------------------------------
    print("Fetching commits for all repos (this can take a while)...", file=sys.stderr)
    all_commits = []  # (repo, author, date)
    for r in repos:
        name = r["name"]
        commits = fetch_commits(name)
        for c in commits:
            author = c["author"]["login"] if c.get("author") else None
            commit_date = parse_date(c["commit"]["author"]["date"])
            all_commits.append((name, author, commit_date))
        print(f"  {name}: {len(commits)} commits", file=sys.stderr)

    total_commits = len(all_commits)

    commits_by_repo = Counter(c[0] for c in all_commits)
    top_repos = commits_by_repo.most_common(10)

    commits_by_date = Counter(c[2] for c in all_commits)
    cum = 0
    cum_by_date = {}
    for d in sorted(commits_by_date):
        cum += commits_by_date[d]
        cum_by_date[d] = cum
    xs2 = [d for d in sorted(cum_by_date) if d > ACCOUNT_ESTABLISHED]
    ys2 = [cum_by_date[d] for d in xs2]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(xs2, ys2, color=NAVY, linewidth=1.5)
    style_axes(ax, "Cumulative commits over time", "Date", "Cumulative commits")
    fig.tight_layout()
    fig.savefig(IMAGES_DIR / "cumulative_commits.svg", **SAVEFIG_KWARGS)
    plt.close(fig)

    heatmap_svg, heatmap_total = build_heatmap_svg(commits_by_date)
    heatmap_unit = "contribution" if heatmap_total == 1 else "contributions"
    replace_between_markers(
        INDEX_MD,
        "<!-- HEATMAP:START -->",
        "<!-- HEATMAP:END -->",
        "```{raw} html\n"
        '<div class="cas-heatmap-card">\n'
        f'<p class="cas-heatmap-title">{heatmap_total:,} {heatmap_unit} in the last year</p>\n'
        f"{heatmap_svg}\n"
        "</div>\n"
        "```",
    )

    author_counts = Counter(c[1] for c in all_commits if c[1])
    top_committers = author_counts.most_common(10)

    author_repos: dict[str, set] = {}
    for name, author, _ in all_commits:
        if author:
            author_repos.setdefault(author, set()).add(name)
    multi_repo = sorted(
        ((a, len(rs)) for a, rs in author_repos.items() if len(rs) > 1),
        key=lambda kv: -kv[1],
    )[:10]

    # -- Pull requests --------------------------------------------------------
    print("Fetching pull requests for all repos...", file=sys.stderr)
    all_prs = []  # (repo, created_date)
    for r in repos:
        name = r["name"]
        prs = fetch_pull_requests(name)
        for pr in prs:
            all_prs.append((name, parse_date(pr["created_at"])))
        print(f"  {name}: {len(prs)} pull requests", file=sys.stderr)

    total_prs = len(all_prs)

    prs_by_repo = Counter(p[0] for p in all_prs)
    top_pr_repos = prs_by_repo.most_common(10)

    prs_by_date = Counter(p[1] for p in all_prs)
    cum = 0
    cum_prs_by_date = {}
    for d in sorted(prs_by_date):
        cum += prs_by_date[d]
        cum_prs_by_date[d] = cum
    xs3 = [d for d in sorted(cum_prs_by_date) if d > ACCOUNT_ESTABLISHED]
    ys3 = [cum_prs_by_date[d] for d in xs3]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(xs3, ys3, color=NAVY, linewidth=1.5)
    style_axes(ax, "Cumulative pull requests over time", "Date", "Cumulative pull requests")
    fig.tight_layout()
    fig.savefig(IMAGES_DIR / "cumulative_prs.svg", **SAVEFIG_KWARGS)
    plt.close(fig)

    # -- Issues closed --------------------------------------------------------
    print("Fetching closed issues for all repos...", file=sys.stderr)
    all_closed_issues = []  # (repo, closed_date)
    for r in repos:
        name = r["name"]
        issues = fetch_closed_issues(name)
        for issue in issues:
            closed_at = issue.get("closed_at")
            if closed_at:
                all_closed_issues.append((name, parse_date(closed_at)))
        print(f"  {name}: {len(issues)} closed issues", file=sys.stderr)

    total_closed_issues = len(all_closed_issues)

    closed_issues_by_repo = Counter(i[0] for i in all_closed_issues)
    top_issue_repos = closed_issues_by_repo.most_common(10)

    closed_issues_by_date = Counter(i[1] for i in all_closed_issues)
    cum = 0
    cum_issues_by_date = {}
    for d in sorted(closed_issues_by_date):
        cum += closed_issues_by_date[d]
        cum_issues_by_date[d] = cum
    xs4 = [d for d in sorted(cum_issues_by_date) if d > ACCOUNT_ESTABLISHED]
    ys4 = [cum_issues_by_date[d] for d in xs4]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(xs4, ys4, color=NAVY, linewidth=1.5)
    style_axes(ax, "Cumulative issues closed over time", "Date", "Cumulative issues closed")
    fig.tight_layout()
    fig.savefig(IMAGES_DIR / "cumulative_issues_closed.svg", **SAVEFIG_KWARGS)
    plt.close(fig)

    # -- Render markdown ------------------------------------------------------
    def fmt(n: int) -> str:
        return f"{n:,}"

    blocks = [
        "Aggregate metrics on the CAS GitHub organization's repositories and "
        "contributors, generated directly from the GitHub API by "
        "[`scripts/generate_metrics.py`]"
        "(https://github.com/casact/casact.github.io/blob/main/scripts/generate_metrics.py) "
        "(a Python port of the `meta` repo's "
        "[`core_metrics.Rmd`](https://github.com/casact/meta/blob/master/git_metrics/core_metrics.Rmd)). "
        f"Last updated {today.isoformat()}.",
        rubric("Repos"),
        'A repository - typically called a "repo" for short - is the unit of '
        "measure for a single project. A repo may contain more than one file, "
        "and in fact, most repos contain multiple files.",
        rubric("By date"),
        f"As of {today.isoformat()}, there are {repo_count} repositories in the "
        "organization. The count begins at ten repos as of the account's "
        "creation in August 2019, since several pre-existing repos were "
        "transferred in from other owners at that time.",
        image_md("Cumulative repository count over time", "repo_growth.svg"),
        rubric("By language"),
        "Where a repo has a predominant language, GitHub identifies it. Of the "
        "repos with a single predominant language, the count by language is:",
        image_md("Repository count by predominant language", "by_language.svg"),
        rubric("Stars"),
        image_md("Stars per repo", "stars.svg"),
        rubric("Forks"),
        image_md("Forks per repo", "forks.svg"),
        rubric("Contributions"),
        rubric("Commits"),
        f"There have been {fmt(total_commits)} commits in total. The top ten "
        "repos by number of commits are:",
        "```{raw} html\n"
        + html_table(["Repo", "Total commits"], [(n, fmt(c)) for n, c in top_repos])
        + "\n```",
        "The cumulative growth of commits over time has been:",
        image_md("Cumulative commits over time", "cumulative_commits.svg"),
        rubric("Committers"),
        "The ten most frequent contributors across all repos are:",
        "```{raw} html\n"
        + html_table(["Author", "Commits"], [(a, fmt(c)) for a, c in top_committers])
        + "\n```",
        "Authors who have worked across multiple repositories:",
        "```{raw} html\n"
        + html_table(["Author", "Repos contributed to"], multi_repo)
        + "\n```",
        rubric("Pull requests"),
        "Pull requests take place when a GitHub user submits an improvement or "
        "correction to be considered by the maintainer of a repo. There have "
        f"been {fmt(total_prs)} pull requests in total. The top ten repos by "
        "number of pull requests are:",
        "```{raw} html\n"
        + html_table(["Repo", "Total pull requests"], [(n, fmt(c)) for n, c in top_pr_repos])
        + "\n```",
        "The cumulative growth of pull requests over time has been:",
        image_md("Cumulative pull requests over time", "cumulative_prs.svg"),
        rubric("Issues closed"),
        f"There have been {fmt(total_closed_issues)} issues closed in total. "
        "The top ten repos by number of issues closed are:",
        "```{raw} html\n"
        + html_table(["Repo", "Issues closed"], [(n, fmt(c)) for n, c in top_issue_repos])
        + "\n```",
        "The cumulative growth of issues closed over time has been:",
        image_md("Cumulative issues closed over time", "cumulative_issues_closed.svg"),
    ]
    generated = "\n\n".join(blocks)

    replace_between_markers(PROJECTS_MD, "<!-- METRICS:START -->", "<!-- METRICS:END -->", generated)
    print(
        f"Updated {PROJECTS_MD.name} and {INDEX_MD.name}: "
        f"{total_commits} commits, {total_prs} pull requests, and "
        f"{total_closed_issues} issues closed across {repo_count} repos.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
