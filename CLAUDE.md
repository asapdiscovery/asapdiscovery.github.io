# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Hugo source for the ASAP Discovery Consortium website (https://asapdiscovery.org), plus offline Python tooling that reuses the site's data files (notably the NIH RPPR progress-report generator in `rppr/`). See `README.md` for content-authoring conventions (news posts, science updates, members, publications front matter/YAML formats).

## Build, lint, test

```bash
hugo server                          # local preview with live reload
hugo --minify --panicOnWarning       # production build into ./public (what CI runs)

pip install -r requirements-dev.txt  # pytest, pyyaml, yamllint
yamllint --strict .                  # YAML lint (.yamllint.yaml)
pytest tests                         # all tests
pytest tests/test_data.py -k protocols   # a subset
```

- CI (`.github/workflows/gh-pages.yml`) builds with **Hugo 0.169.0 extended** (templates use `hugo.Data` and `.Site.Language.Locale`, which need Hugo ≥0.158) on every push and PR; only pushes to `main` deploy to the `gh-pages` branch. `--panicOnWarning` makes Hugo deprecation warnings fail the build. `.github/workflows/checks.yml` runs yamllint and pytest.
- `.yamllint.yaml` disables formatting rules on purpose and keeps only meaning-changing ones (duplicate keys, syntax, truthy values); don't mass-reformat `data/` to satisfy stricter rules.
- `tests/test_data.py` checks `data/` integrity for the RPPR (component names, event dates, every protocol has events). `tests/test_convert.py` asserts `data/outputs/protocols.yaml` is exactly what `protocols-export/convert.py` generates, so hand edits to that file fail CI.
- The build fetches remote resources (`resources.GetRemote`): the TEP status Google Sheet (CSV) and Roboto fonts in `themes/kube/layouts/shortcodes/TEPs.html` and `partials/TEP.html`. A build therefore needs network access; `config.toml` raises `timeout` to 60s for this.
- `config.toml` sets `ignoreFiles = ['data/outputs/preTEPS/']` — that directory is a notebook/export workspace, not site data.

## Architecture

**Theme is vendored and customized.** `themes/kube/` is checked in (not a submodule) and holds nearly all of the site logic; top-level `layouts/` only has `robots.txt`. When changing rendering, edit `themes/kube/layouts/` directly:
- `section/*.html` — per-section page layouts (selected via `layout:` front matter, e.g. `content/pipeline/_index.md` uses `layout: pipeline`).
- `shortcodes/*.html` — most `content/outputs/*.md` pages are thin wrappers that call a shortcode (`molecules`, `TCPs`, `TPPs`, `TEPs`, `protocols-table`, `structures`, etc.) which renders tables from `data/`.
- `partials/` — reusable cards (`TEP.html`, `molecule.html`, `publication.html`, `person.html`, `research-output.html`, ...).

**Content is data-driven.** Most substantive edits are YAML in `data/`, not Markdown:
- `data/programs/<PROGRAM-NICKNAME>.yaml` — one file per discovery program (e.g. `ASAP-COV-MPRO`); drives the Pipeline page (`section/pipeline.html`) and hit-to-lead/lead-opt/structures shortcodes. Stage fields use statuses like `completed`, and per-stage YAML can override links/status. Commenting out a program file's contents removes it from the pipeline.
- `data/outputs/*.yaml` — research outputs keyed by ID (molecules, TCPs, TPPs, assay cascades, targeting opportunities, circulating variants, software, protocols, ChEMBL datasets). Entries carry `projects:`/`cores:` attribution lists and dated `events:`.
- `data/outputs/TEPs/*.yaml` — Target Enabling Packages, one per target.
- `data/publications/publications.yaml`, `data/members/*.yaml`, `data/jobs/`.

The `projects`, `cores`, and `events[].date` fields in `data/outputs/` and `data/publications/` are load-bearing beyond the website: the RPPR generator filters on them (see below). Every name in those lists must be a key of `rppr/specific-aims.yaml` (e.g. `Project 5`, `Biochemical Assay Core`) or an alias in `rppr/component-aliases.yaml` (e.g. `ADMET Core` reports under `Biochemical Assay Core`); otherwise the output silently drops out of the RPPR. `tests/test_data.py` enforces this.

**Non-published tooling directories** (Hugo does not read these): `rppr/`, `protocols-export/`, `members-export/`.

## RPPR generation (`rppr/`)

Generates NIH PHS 2590 Form Page 5 progress-report Word documents, one per Project/Core, into `rppr/outputs/`.

```bash
conda create -n rppr python-docx "mistune<1.0" sympy pyyaml pandas
conda activate rppr
cd rppr && python generate-rppr.py    # must run from rppr/: paths are relative (../data/...)
```

- Reporting window is hardcoded via `reporting_period_start`/`reporting_period_end` at the top of `generate-rppr.py`; update it each reporting year.
- Inputs: `specific-aims.yaml` (component list, names, aims, flags), `asap-year-1-accomplishments.yaml` / `asap-year-1-plans.yaml` (narrative text per component), plus `../data/outputs/*.yaml`, `../data/outputs/TEPs/*.yaml`, and `../data/publications/publications.yaml`. Outputs/publications are included for a component only if it appears in their `projects`/`cores` and an event/publication date falls in the reporting window. Publications are listed only in the Administrative Core report.
- Mechanism: content is assembled as Markdown, rendered by a custom mistune **0.x** renderer (`PythonDocxRenderer`) into python-docx *source code*, then `exec`'d. Requires `mistune<1.0`. Text with quotes/special characters can break the generated code — escaping happens in `PythonDocxRenderer.text`. Markdown links render as `text [url]`.
- All Word styles come from `2590_continuation-template.docx` (custom styles `BasicUserList`, `BasicUserTable`, `CodeSpan`, `BlockCode`); edit the template to change formatting.
- Warnings printed for outputs with no `events` or publications lacking a PMCID indicate data to fix in `data/`, not code bugs.

## protocols.io table (`protocols-export/`)

`data/outputs/protocols.yaml` is curated, not a raw export. Refresh by dropping a new CSV in `protocols-export/exports/` and running `convert.py`, which carries forward hand-assigned `category`/`target`/`cores` and author-name normalization keyed on protocol URL, and reports new protocols needing taxonomy. See `protocols-export/README.md`. Hugo silently ignores CSV in `data/`, so never point the site at a CSV.
