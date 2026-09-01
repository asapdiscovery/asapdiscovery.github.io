# protocols.io export → `data/outputs/protocols.yaml`

Source data and tooling for the protocols table at
[/outputs/protocols](https://asapdiscovery.org/outputs/protocols).

Hugo does not read this directory — it only scans `content/`, `data/`, `layouts/`,
`static/`, `assets/`, `themes/`, `archetypes/` and `i18n/`. Files here are kept in
version control for provenance and are never published. (Same arrangement as
`rppr/` and `members-export/`.)

## Layout

| Path | What it is |
| --- | --- |
| `exports/` | Raw CSV exports from protocols.io, named `protocols-io-export-YYYY-MM-DD.csv` |
| `convert.py` | Converts the newest export into `data/outputs/protocols.yaml` |

## Why this is not a straight copy

`data/outputs/protocols.yaml` is **not** a rendering of the export. Three kinds of
information are added or repaired on top of it, and a naive overwrite loses all of them:

1. **ASAP taxonomy that protocols.io does not hold** — `category` (6 values, drives the
   badge colours hardcoded in `themes/kube/layouts/shortcodes/protocols-table.html`),
   `target` (29 normalised values, drives the Target filter) and `cores` (4 ASAP core
   names, drives the Core filter).
2. **Author name normalisation** — the raw export contains alternative spellings of the
   same person (`warren.thompson`, `Yurii Kheilik`/`Yurii Kheylik`, `Anu V Chandran`).
   Left uncorrected these fragment the author filter, which matches on exact strings.
   See commit 27558aec.
3. **Description truncation** — descriptions are cut to 300 characters with a trailing
   ellipsis.

So the conversion carries curation forward from the current YAML, keyed on protocol URL,
and reports which protocols are new and still need `category`/`target`/`cores` assigned
by hand.

## Refreshing the table

1. Drop the new export in `exports/`.
2. Run `convert.py`.
3. Assign taxonomy to any protocols it reports as new.
4. Rebuild and check the table renders the expected number of rows.

A CSV cannot be pointed at directly from `data/`: Hugo's data directory reads only
YAML, JSON, TOML and XML, and ignores a `.csv` **silently** — the table would render
zero rows with the build still green.
