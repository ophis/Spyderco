# tools/spy.py

`Catalogs/<file>.md` is the whole record of a family: its rows, photos (the Image cells) and a hidden `<!-- spy … -->` config comment under the title. A fresh checkout needs nothing else to update, add or judge a family.

Judgment work — SKU/dealer spelling resolution, candidate photo search, visual review, the REVIEW.md checklist — is an agent skill, not this tool: use `.claude/skills/spyderco-catalog/SKILL.md`.

## Setup

    cd tools
    python3 -m venv .venv && .venv/bin/pip install pillow
    npm install

Runtime deps: `python3` + Pillow (`.venv`); `node` + `playwright-core` using the installed Google Chrome channel (needed for `fetch official`/`forum`/`sitemaps` and `browser`/`photos fetch`/`photos gallery`). `render`, `verify`, `update --offline` and the test suite (`tools/.venv/bin/python -m unittest discover -s tools/tests -t tools`, from the repo root) need only Python and work offline.

## Catalog config

JSON in the `<!-- spy … -->` comment after the title; edit it through the commands below.

- `id`, `wiki_page`, `readme_label`
- `section_rules`: `[{section, field: sku|handle|wiki_table, regex}]`; first match wins, default = first section.
- `aliases`: `{wiki/official/forum spelling or record key: catalog SKU}`. A record key (`<raw SKU>|<start year>[#n]`) aliases one wiki entry only.
- `skip`: record keys or SKUs never to propose or report.
- `manual`: SKUs of rows intentionally not on the wiki (not reported as ORPHAN).
- `wiki_errors`: `{"<SKU>|<released>": {field: wiki value}}`; a DIFF with that wiki value is hidden and returns when the wiki value changes.

## Commands

- `init <ID> --file "<name>" --title … --wiki-page … --sections … [--rule section:field:regex …] [--readme-label …]` — write `Catalogs/<name>.md` with config, standard preamble and empty sections; refuses if the file exists.
- `update <ID> [--offline]` — fetch the wiki (or read `cache/wiki/`) and write `cache/proposals/<ID>.json`; prints `NEW <key>`, `DIFF <SKU> <field>: md=… wiki=…`, `ORPHAN <SKU>` (row with no wiki entry), `UNMATCHED official|forum <SKU>`. Never edits the catalog.
- `accept <ID> <key …>|--all-new` — insert proposed NEW rows into their section by release date. A NEW row whose SKU and Released already exist is refused (`--all-new` skips it and prints `DUPLICATE`).
- `take <ID> <SKU> <field …> [--released R]` — copy the proposed wiki value(s) of a DIFF into the row.
- `wiki-error <ID> <SKU> <field …> [--released R]` — record the proposed wiki value(s) in `wiki_errors`.
  `accept`/`take`/`wiki-error` refuse if the catalog changed since `update`; `--released` picks the row when the SKU has several.
- `alias <ID> <from> <to>` — map a spelling or one record key to a catalog SKU.
- `skip <ID> <key|SKU>` — never propose that wiki entry / report that SKU.
- `manual <ID> <SKU>` — mark an existing row as intentionally not on the wiki.
- `add-row <ID> --sku … --section … [--released --steel --handle --type --qty --alt]` — add a row by hand (also marks it `manual`).
- `render [ID …|--all]` — rewrite catalogs in normal form (numbering, counts) and the README model table.
- `fetch wiki <ID>` — fetch the family's Spydiewiki page → `cache/wiki/<page>.txt`.
- `fetch official` — fetch spyderco.com `products.json` → `cache/official.json`.
- `fetch forum` — fetch forum post 1 (Sprints/Exclusives thread) → `cache/forum.txt`.
- `fetch sitemaps [domain ...]` — crawl dealer sitemaps → `cache/sitemaps.json` (Blade HQ via the browser helper).
- `browser open <url>` — open a URL in the tool's Chrome profile to clear a verification check by hand.
- `photos candidates <ID> [--sku SKU ...] [--add SKU=URL ...]` — build `cache/candidates/<ID>.json` for rows without a photo.
- `photos fetch <ID>` — visit pending candidates in the browser; auto-accepts only page-verified finds, else saves to `cache/review/`.
- `photos gallery <ID> --sku SKU [--page URL]` — download every gallery image of the SKU's source page (default: the page recorded in `cache/candidates/` when its main photo was accepted) to `cache/gallery/`.
- `photos sheet <ID> [--review|--gallery|--all]` — numbered contact sheets in `cache/sheets/` for visual review.
- `photos accept <ID> <SKU> <file> [--extra] [--replace] [--page URL]` — copy a photo into `Catalogs/images/<ID>/` and add it to the Image cell of every row with that SKU; existing files are never overwritten.
- `photos reject <file>` — blacklist a file's md5 in `data/bad_md5.txt`.
- `verify` — offline; exits 1 on: a catalog not in rendered form, README table out of date, image link to a missing file, invalid config (missing key, unknown rule section/field, bad regex, `wiki_errors`/`manual` entries matching no row), duplicate SKU with the same Released.

Photo provenance (source page) lives only in the gitignored `cache/candidates/`; on a fresh checkout `photos gallery` needs `--page`.

`photos accept --extra --replace` appends a new extra photo; it does not replace an existing extra (only a main photo is ever overwritten, and under a new hashed filename so viewers don't show a stale cached copy).

`fetch forum` and `photos fetch`/`photos gallery` (the browser helpers) need a live check against the real site before first real use.

## New family workflow

1. `init <ID> --file "<file>" --title "<title>" --wiki-page <page> --sections "<S1>" "<S2>" …`
2. `fetch wiki <ID>`, then `update <ID> --offline`
3. review NEW, then `accept <ID> <key …>|--all-new`
4. photos — see Photo workflow

## Update workflow

1. `fetch wiki <ID>`; optionally `fetch official` and `fetch forum`
2. `update <ID> --offline`
3. NEW → `accept`; DIFF → `take` (real wiki update) or `wiki-error` (wiki wrong); ORPHAN → `alias` or `manual`; UNMATCHED → `alias`/`skip`/`add-row`
4. `render --all`, `verify`

## Photo workflow

Preference (REVIEW.md §2): open and folded (clip side) in one photo → open + folded clip side as two photos (`SKU` + `SKU_2`) → best available photo of the exact variant. Lower quality beats no photo.

Source order: spyderco.com (`_Both` image) → the exclusive dealer's own site → other retailers → last resort: any photo of the exact variant that can be found online.

1. `photos candidates <ID>`
2. `photos fetch <ID>` — auto-accepts verified finds; unverified candidates land in `cache/review/`
3. `photos sheet <ID> --review` — visual pick from the contact sheet
4. `photos accept <ID> <SKU> <file> [--extra]` / `photos reject <file>` for rejects
5. for the folded clip-side shot: `photos gallery <ID> --sku <SKU>` then `photos sheet <ID> --gallery`

## Migration note

The user's local, untracked `tools/` on `main` (old scripts, caches, Chrome profiles) collides with this checked-in `tools/` on merge:

1. Before merging: rename the old `tools/` to `tools.old/`.
2. After merging: move its Chrome profiles (`prof`, `prof2`) into `tools/.profiles/`, and its sitemap caches into `tools/cache/`.

## Data files

- `data/bad_md5.txt` — rejected-image md5 blacklist, one per line.
- `data/dealers.json` — dealer-name normalization (`aliases`) and dealer name → sitemap domain (`domains`).
- `cache/` (gitignored, ephemeral): source snapshots, proposals, photo candidates and provenance.
