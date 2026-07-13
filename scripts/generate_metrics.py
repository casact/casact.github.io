#!/usr/bin/env python3
"""Regenerate the "Metrics" section of docs/projects.md from live GitHub data.

Python + matplotlib port of casact/meta's git_metrics/core_metrics.Rmd
(https://github.com/casact/meta/blob/master/git_metrics/core_metrics.Rmd).

Charts are written to docs/_static/images/metrics/, and the markdown
between the ``<!-- METRICS:START -->`` / ``<!-- METRICS:END -->`` markers
in docs/projects.md is replaced with freshly generated tables and figures.
Intended to be run daily by .github/workflows/update-metrics.yml.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github_api import fetch_commits, fetch_org_repos, parse_date  # noqa: E402

ACCOUNT_ESTABLISHED = date(2019, 8, 1)

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "docs" / "_static" / "images" / "metrics"
PROJECTS_MD = REPO_ROOT / "docs" / "projects.md"
FONTS_DIR = Path(__file__).resolve().parent / "fonts"

NAVY = "#002D72"
TEXT = "#1c2531"
GRID = "#e0e0e0"

FONT_BODY = "Source Sans 3"
FONT_HEADING = "Montserrat"

# Same typefaces as the site's own CSS (docs/_static/css/custom.css). These
# are static weight instances of the variable Google Fonts files, since
# matplotlib/freetype can't select a variable font's weight axis on its own.
for _font_path in (FONTS_DIR / "SourceSans3-Regular.ttf", FONTS_DIR / "Montserrat-Bold.ttf"):
    fm.fontManager.addfont(str(_font_path))

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": GRID,
        "axes.grid": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linewidth": 1,
        "axes.axisbelow": True,
        "font.family": FONT_BODY,
        "font.size": 11,
        "axes.labelcolor": TEXT,
        "text.color": TEXT,
        "xtick.color": TEXT,
        "ytick.color": TEXT,
    }
)


def style_axes(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(
        title, fontfamily=FONT_HEADING, fontweight="bold", fontsize=13, color=NAVY, loc="left", pad=12
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
    fig.savefig(path, dpi=150)
    plt.close(fig)


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
    fig.savefig(IMAGES_DIR / "repo_growth.png", dpi=150)
    plt.close(fig)

    # -- Chart: repo count by predominant language ------------------------
    lang_counts = Counter(r["language"] for r in repos if r.get("language"))
    items = sorted(lang_counts.items(), key=lambda kv: kv[1])
    save_barh(
        IMAGES_DIR / "by_language.png",
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
        IMAGES_DIR / "watchers.png",
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
        IMAGES_DIR / "forks.png",
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
    fig.savefig(IMAGES_DIR / "cumulative_commits.png", dpi=150)
    plt.close(fig)

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
        image_md("Cumulative repository count over time", "repo_growth.png"),
        rubric("By language"),
        "Where a repo has a predominant language, GitHub identifies it. Of the "
        "repos with a single predominant language, the count by language is:",
        image_md("Repository count by predominant language", "by_language.png"),
        rubric("Watchers"),
        image_md("Watchers per repo", "watchers.png"),
        rubric("Forks"),
        image_md("Forks per repo", "forks.png"),
        rubric("Contributions"),
        rubric("Commits"),
        f"There have been {fmt(total_commits)} commits in total. The top ten "
        "repos by number of commits are:",
        "```{raw} html\n"
        + html_table(["Repo", "Total commits"], [(n, fmt(c)) for n, c in top_repos])
        + "\n```",
        "The cumulative growth of commits over time has been:",
        image_md("Cumulative commits over time", "cumulative_commits.png"),
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

    text = PROJECTS_MD.read_text()
    start_marker = "<!-- METRICS:START -->"
    end_marker = "<!-- METRICS:END -->"
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker)
    new_text = (
        text[:start]
        + "\n<!-- Generated by scripts/generate_metrics.py - do not edit by hand. -->\n\n"
        + generated
        + "\n\n"
        + text[end:]
    )
    PROJECTS_MD.write_text(new_text)
    print(
        f"Updated {PROJECTS_MD}: {total_commits} commits across {repo_count} repos.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
