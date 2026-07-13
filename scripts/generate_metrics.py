#!/usr/bin/env python3
"""Regenerate the "Metrics" section of docs/projects.md, plus the homepage
contribution heatmap, from live GitHub data.

Python + matplotlib port of casact/meta's git_metrics/core_metrics.Rmd
(https://github.com/casact/meta/blob/master/git_metrics/core_metrics.Rmd).

Charts are written to docs/_static/images/metrics/. The markdown between
the ``<!-- METRICS:START/END -->`` markers in docs/projects.md and the
``<!-- HEATMAP:START/END -->`` markers in docs/index.md is replaced with
freshly generated tables and figures. Intended to be run daily (and on
every push) by .github/workflows/update-metrics.yml.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github_api import fetch_commits, fetch_org_repos, parse_date  # noqa: E402

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
# --cas-blue-light) for the contribution heatmap gradient.
HEATMAP_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "cas_blues", ["#eaf7fb", "#74d2e7", "#1c6ea8", "#002D72"]
)

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


def save_heatmap(path: Path, commits_by_date: dict, weeks: int = 53) -> None:
    """A GitHub-style contribution calendar, colored with the site's blues."""
    end = date.today()
    start = end - timedelta(weeks=weeks)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # snap back to a Sunday

    xs, ys, counts = [], [], []
    month_ticks: dict[int, str] = {}
    for i in range((end - start).days + 1):
        d = start + timedelta(days=i)
        week_idx = (d - start).days // 7
        dow = (d.weekday() + 1) % 7  # Sunday=0 .. Saturday=6
        xs.append(week_idx)
        ys.append(dow)
        counts.append(commits_by_date.get(d, 0))
        if d.day <= 7 and dow == 0:
            month_ticks[week_idx] = d.strftime("%b")
    num_weeks = max(xs) + 1

    nonzero = sorted(c for c in counts if c > 0)
    vmax = max(1, nonzero[int(len(nonzero) * 0.95)] if nonzero else 1)
    norm = mcolors.Normalize(vmin=0, vmax=vmax, clip=True)

    fig, ax = plt.subplots(figsize=(max(7, 0.16 * num_weeks), 2.8))
    ax.scatter(xs, ys, c=counts, cmap=HEATMAP_CMAP, norm=norm, marker="s", s=38, linewidths=0)

    # "Less -> More" legend, bottom-right, like GitHub's own heatmap.
    legend_vals = [0, vmax * 0.25, vmax * 0.5, vmax * 0.75, vmax]
    legend_x0 = num_weeks - len(legend_vals)
    legend_y = 7.4
    ax.scatter(
        [legend_x0 + i for i in range(len(legend_vals))],
        [legend_y] * len(legend_vals),
        c=legend_vals,
        cmap=HEATMAP_CMAP,
        norm=norm,
        marker="s",
        s=38,
        linewidths=0,
    )
    ax.text(legend_x0 - 1, legend_y, "Less", ha="right", va="center", fontsize=9, color=TEXT)
    ax.text(
        legend_x0 + len(legend_vals), legend_y, "More", ha="left", va="center", fontsize=9, color=TEXT
    )

    ax.set_ylim(-1, 8.2)
    ax.set_xlim(-1, num_weeks)
    ax.invert_yaxis()
    ax.set_yticks([1, 3, 5])
    ax.set_yticklabels(["Mon", "Wed", "Fri"])
    ax.set_xticks(list(month_ticks.keys()))
    ax.set_xticklabels(list(month_ticks.values()))
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(
        "Contribution activity",
        fontfamily=FONT_HEADING,
        fontweight="bold",
        fontsize=13,
        color=NAVY,
        loc="center",
        pad=12,
    )
    fig.tight_layout()
    fig.savefig(path, **SAVEFIG_KWARGS)
    plt.close(fig)


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

    # -- Chart: watchers per repo ------------------------------------------
    watched = sorted(
        ((r["name"], r.get("watchers_count", 0)) for r in repos if r.get("watchers_count", 0) > 0),
        key=lambda kv: kv[1],
    )
    save_barh(
        IMAGES_DIR / "watchers.svg",
        [k for k, _ in watched],
        [v for _, v in watched],
        "Watchers by repository",
        "Watchers",
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

    save_heatmap(IMAGES_DIR / "heatmap.svg", commits_by_date)
    replace_between_markers(
        INDEX_MD,
        "<!-- HEATMAP:START -->",
        "<!-- HEATMAP:END -->",
        image_md(
            "CAS GitHub organization contribution activity over the past year", "heatmap.svg"
        ),
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
        rubric("Watchers"),
        image_md("Watchers per repo", "watchers.svg"),
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
        "correction to be considered by the maintainer of a repo. Metrics "
        "coming soon.",
    ]
    generated = "\n\n".join(blocks)

    replace_between_markers(PROJECTS_MD, "<!-- METRICS:START -->", "<!-- METRICS:END -->", generated)
    print(
        f"Updated {PROJECTS_MD.name} and {INDEX_MD.name}: "
        f"{total_commits} commits across {repo_count} repos.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
