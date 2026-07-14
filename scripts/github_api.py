"""Shared GitHub API helpers for the scripts/generate_*.py data-refresh scripts."""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import date, datetime

import requests

ORG = "casact"
MAX_RETRIES = 5

SESSION = requests.Session()
SESSION.headers["Accept"] = "application/vnd.github+json"
SESSION.headers["X-GitHub-Api-Version"] = "2022-11-28"

TOKEN = os.environ.get("GITHUB_TOKEN")
if TOKEN:
    SESSION.headers["Authorization"] = f"Bearer {TOKEN}"

# GitHub's own linguist language colors:
# https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml
LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "R": "#198CE7",
    "TeX": "#3D6117",
    "HTML": "#e34c26",
    "Jupyter Notebook": "#DA5B0B",
    "Makefile": "#427819",
    "Stan": "#b2011d",
}
DEFAULT_LANGUAGE_COLOR = "#8a8a8a"


def _request_with_retries(method: str, url: str, **kwargs) -> requests.Response:
    """Issue a request, retrying transient failures (rate limits, 5xx, network
    blips) with backoff. GitHub Actions triggers this script on every push,
    so transient hiccups are common enough to be worth absorbing here rather
    than failing the whole workflow run.
    """
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = SESSION.request(method, url, timeout=30, **kwargs)
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            wait = 2**attempt * 5
            print(f"  {exc!r}, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue

        if resp.status_code == 409:
            return resp
        if resp.status_code in (403, 429):
            if resp.headers.get("X-RateLimit-Remaining") == "0":
                wait = max(1, int(resp.headers.get("X-RateLimit-Reset", 0)) - time.time()) + 2
            else:
                wait = int(resp.headers.get("Retry-After", 2**attempt * 10))
            print(
                f"  rate limited (status {resp.status_code}), waiting {wait:.0f}s "
                f"before retry {attempt + 1}/{MAX_RETRIES}...",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            wait = 2**attempt * 5
            print(
                f"  server error {resp.status_code}, retrying in {wait}s...", file=sys.stderr
            )
            time.sleep(wait)
            continue
        return resp

    if last_exc:
        raise last_exc
    resp.raise_for_status()
    return resp


def api_get_paginated(url: str) -> list:
    """GET all pages of a REST list endpoint. Returns [] for an empty repo (409)."""
    results = []
    page = 1
    while True:
        resp = _request_with_retries("GET", url, params={"per_page": 100, "page": page})
        if resp.status_code == 409:
            return []
        resp.raise_for_status()
        batch = resp.json()
        results.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return results


def fetch_org_repos(org: str = ORG) -> list:
    return api_get_paginated(f"https://api.github.com/orgs/{org}/repos")


def fetch_commits(repo_name: str, org: str = ORG) -> list:
    return api_get_paginated(f"https://api.github.com/repos/{org}/{repo_name}/commits")


def fetch_pull_requests(repo_name: str, org: str = ORG) -> list:
    """All pull requests (open, closed, and merged) for a repo."""
    return api_get_paginated(f"https://api.github.com/repos/{org}/{repo_name}/pulls?state=all")


def fetch_closed_issues(repo_name: str, org: str = ORG) -> list:
    """Closed issues for a repo, excluding pull requests.

    GitHub's issues endpoint also returns pull requests (a PR is internally
    just an issue with extra data), each carrying a `pull_request` key that
    plain issues don't have - filter those out to get true issues only.
    """
    items = api_get_paginated(f"https://api.github.com/repos/{org}/{repo_name}/issues?state=closed")
    return [i for i in items if "pull_request" not in i]


def parse_date(timestamp: str) -> date:
    return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").date()


def graphql(query: str, variables: dict | None = None) -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required for GraphQL requests")
    resp = _request_with_retries(
        "POST",
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables or {}},
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL error: {payload['errors']}")
    return payload["data"]


PINNED_REPOS_QUERY = """
query($login: String!) {
  organization(login: $login) {
    pinnedItems(first: 6, types: [REPOSITORY]) {
      nodes {
        ... on Repository {
          name
          description
          url
          stargazerCount
          forkCount
          primaryLanguage { name color }
        }
      }
    }
  }
}
"""


def fetch_pinned_repos(org: str = ORG) -> list[dict]:
    """Return the org's pinned repos as dicts shaped like the REST repo objects
    used elsewhere in these scripts (name, description, html_url, language,
    stargazers_count, forks_count).

    Uses the GraphQL API (requires GITHUB_TOKEN) since pinned repos aren't
    exposed by the REST API. Falls back to scraping the org's public profile
    page - which renders the same pinned-repo cards - when no token is
    available, so this still works for local, tokenless runs.
    """
    if TOKEN:
        data = graphql(PINNED_REPOS_QUERY, {"login": org})
        nodes = data["organization"]["pinnedItems"]["nodes"]
        return [
            {
                "name": n["name"],
                "description": n.get("description"),
                "html_url": n["url"],
                "language": (n.get("primaryLanguage") or {}).get("name"),
                "stargazers_count": n["stargazerCount"],
                "forks_count": n["forkCount"],
            }
            for n in nodes
        ]
    return _scrape_pinned_repos(org)


def _scrape_pinned_repos(org: str) -> list[dict]:
    # This is a plain HTML page, not the REST API, so it needs browser-like
    # headers rather than the session's default `application/vnd.github+json`.
    resp = _request_with_retries(
        "GET",
        f"https://github.com/{org}",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"},
    )
    resp.raise_for_status()
    html = resp.text

    repos = []
    for block in html.split("pinned-item-list-item js-pinned-item-list-item")[1:]:
        name_m = re.search(rf'href="/{re.escape(org)}/([^"]+)"', block)
        if not name_m:
            continue
        name = name_m.group(1)
        desc_m = re.search(
            r'<p class="pinned-item-desc[^"]*"[^>]*>\s*(.*?)\s*</p>', block, re.S
        )
        description = re.sub(r"\s+", " ", desc_m.group(1)).strip() if desc_m else None
        lang_m = re.search(r'itemprop="programmingLanguage">([^<]+)', block)
        language = lang_m.group(1) if lang_m else None
        stars_m = re.search(r'/stargazers"[^>]*>\s*<svg[^>]*>.*?</svg>\s*([\d,]+)', block, re.S)
        forks_m = re.search(r'/forks"[^>]*>\s*<svg[^>]*>.*?</svg>\s*([\d,]+)', block, re.S)
        stars = int(stars_m.group(1).replace(",", "")) if stars_m else 0
        forks = int(forks_m.group(1).replace(",", "")) if forks_m else 0
        repos.append(
            {
                "name": name,
                "description": description,
                "html_url": f"https://github.com/{org}/{name}",
                "language": language,
                "stargazers_count": stars,
                "forks_count": forks,
            }
        )
    return repos


REPO_ICON_SVG = (
    '<svg aria-hidden="true" viewBox="0 0 16 16" width="{size}" height="{size}" '
    'class="cas-repo-icon"><path fill="currentColor" d="M2 2.5A2.5 2.5 0 0 1 4.5 '
    "0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 "
    "0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 "
    "2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25"
    ".25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087"
    'a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"></path></svg>'
)


def repo_icon(size: int = 16) -> str:
    return REPO_ICON_SVG.format(size=size)
