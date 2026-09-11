# casact.github.io

This repository governs the development of the [CAS GitHub homepage](https://casact.github.io).

## Setting a project's area of practice

The [Projects](https://casact.github.io/projects.html) table is generated from
the GitHub API, but which area of actuarial work a project belongs to is a
judgement rather than a fact the API knows. Those live in
[`docs/_data/repo_areas.csv`](docs/_data/repo_areas.csv), one line per
repository:

```csv
repo,area
chainladder-python,Reserving
mg-credibility,Credibility and experience rating
claim_sim,
```

Leave the area empty for a project nobody has classified yet; it still appears
in the table, just without an area. The generator warns about repositories with
no entry and about entries naming a repository that is no longer in the
organization, but it never fails the build over either, so a rename upstream
cannot take the site down.

The column is picked up on the next deploy. To see it locally, run the listing
generator (needs a `GITHUB_TOKEN` for the API):

```bash
pip install ".[repos]"
GITHUB_TOKEN=... python scripts/generate_repo_listings.py
```

## Building the site locally

```bash
pip install .
sphinx-build -b html docs _build/html
```

The repo listings on the homepage and the Projects page, and everything on the
Activities page, are generated from the GitHub API by `scripts/` and refreshed
daily by the deploy workflow. Anything between a `START` / `END` marker pair in
`docs/*.md` is machine-written; edit the generator or the data file instead.
