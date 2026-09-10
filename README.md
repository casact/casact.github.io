# casact.github.io

This repository governs the development of the [CAS GitHub homepage](https://casact.github.io).

## Adding a tool to the Field Guide

The [Field Guide](https://casact.github.io/field-guide.html) is the one page on
this site that is curated by hand rather than pulled from the GitHub API. Its
source of truth is [`docs/_data/field_guide.csv`](docs/_data/field_guide.csv),
one row per listing:

| column | what goes in it |
| --- | --- |
| `area` | Functional area to list the tool under. Areas appear in the order they first appear in the file. |
| `tool` | Display name. |
| `url` | Where a reader should go first: CRAN, PyPI, the project site, or the repo. |
| `repo_url` | Optional source repository, when `url` points somewhere else. |
| `language` | Predominant language, spelled the way GitHub spells it. |
| `cas_hosted` | `yes` for repositories in the casact organization, `no` otherwise. |
| `description` | One sentence on what the tool does. |

Add your row, then regenerate the page so the diff shows what readers will see:

```bash
python scripts/generate_field_guide.py
```

That script needs nothing but the standard library, and the deploy workflow runs
it again before building, so the published page cannot drift from the CSV.

## Building the site locally

```bash
pip install .
sphinx-build -b html docs _build/html
```

The repo listings on the homepage and the Projects page, and everything on the
Activities page, are generated from the GitHub API by `scripts/` and refreshed
daily by the deploy workflow. Anything between a `START` / `END` marker pair in
`docs/*.md` is machine-written; edit the generator or the data file instead.
