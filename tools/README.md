# tools/spy.py

Command reference for building and updating the Spyderco model-family catalogs in `Catalogs/`. `families/*.json` is the data of record; `spy.py render` turns it into Markdown.

Judgment work — SKU/dealer spelling resolution, candidate photo search, visual review, the REVIEW.md checklist — is an agent skill, not this tool: use `.claude/skills/spyderco-catalog/SKILL.md`.

## Setup

    cd tools
    python3 -m venv .venv && .venv/bin/pip install pillow
    npm install

Runtime deps: `python3` + Pillow (`.venv`); `node` + `playwright-core` using the installed Google Chrome channel (needed for `fetch official`/`forum`/`sitemaps` and `browser`/`photos fetch`/`photos gallery`). `render`, `verify`, `update --offline` and the test suite (`python3 -m unittest discover -s tools/tests -t tools`) need only Python and work offline.

## Commands

- `render [ID ...|--all]` — render family JSON into `Catalogs/<file>.md`; also regenerates the README model table.
- `update <ID> [--offline]` — fetch (or read `cache/wiki/` with `--offline`) and write a NEW/CHANGED/GONE/RELINK/UNMATCHED proposal to `cache/proposals/<ID>.json`.
- `accept <ID> <src ...|--all-new> [--changed] [--relink OLD NEW]` — apply proposed rows; a CHANGED src needs `--changed`, a RELINK src needs `--relink OLD NEW` (a wiki record matching a `manual|`/`forum|`/`official|` row's SKU is a RELINK of that row, whose fields are kept).
- `alias <ID> <from> <to>` — map a non-wiki SKU spelling to the canonical SKU; never changes rows.
- `ignore <ID> <src>` — exclude a src key from future `update` proposals.
- `add-row <ID> --sku … --section … [--released --steel --handle --type --qty --alt]` — add a manual row (`src=manual|SKU`).
- `init <ID> --file "<name>" --title … --wiki-page … --sections … [--rule section:field:regex ...]` — create a new family file with no rows.
- `fetch wiki <ID>` — fetch the family's Spydiewiki page → `cache/wiki/<page>.txt`.
- `fetch official` — fetch spyderco.com `products.json` → `cache/official.json`.
- `fetch forum` — fetch forum post 1 (Sprints/Exclusives thread) → `cache/forum.txt`.
- `fetch sitemaps [domain ...]` — crawl dealer sitemaps → `cache/sitemaps.json` (Blade HQ via the browser helper).
- `browser open <url>` — open a URL in the tool's Chrome profile to clear a verification check by hand.
- `photos candidates <ID> [--sku SKU ...] [--add SKU=URL ...]` — build `cache/candidates/<ID>.json` for rows without a photo.
- `photos fetch <ID>` — visit pending candidates in the browser; auto-accepts only page-verified finds, else saves to `cache/review/`.
- `photos gallery <ID> --sku SKU [--page URL]` — download every gallery image of the SKU's source page to `cache/gallery/`.
- `photos sheet <ID> [--review|--gallery|--all]` — numbered contact sheets in `cache/sheets/` for visual review.
- `photos accept <ID> <SKU> <file> [--extra] [--replace] [--url] [--page]` — record a photo into `data/images.json` and copy it into `Catalogs/images/<ID>/`.
- `photos reject <file>` — blacklist a file's md5 in `data/bad_md5.txt`.
- `verify` — offline checks: render vs `Catalogs/*.md`, README table, broken/missing image links, image records for unknown SKUs, rows missing `src`, duplicate `src`, duplicate SKU with the same `released`, unknown `section`; exits 1 if any problem is found.
- `seed-from-md --ref DIR [--force]` — one-time migration: build `families/*.json` and `data/images.json` from the current catalogs (see Migration note).

`photos accept --extra --replace` appends a new extra photo; it does not replace an existing extra (only a main photo is ever overwritten, and under a new hashed filename so viewers don't show a stale cached copy).

`fetch forum` and `photos fetch`/`photos gallery` (the browser helpers) need a live check against the real site before first real use.

## New family workflow

1. `init <ID> --file "<file>" --title "<title>" --wiki-page <page> --sections "<S1>" "<S2>" ...`
2. `fetch wiki <ID>`
3. `update <ID> --offline`
4. review the proposal in `cache/proposals/<ID>.json`
5. `accept <ID> --all-new`
6. `render <ID>`
7. photos — see Photo workflow below

## Update workflow

1. `fetch wiki <ID>`; optionally `fetch official` and `fetch forum` for cross-checks
2. `update <ID> --offline`
3. review NEW/CHANGED/GONE/RELINK/UNMATCHED in the proposal
4. `accept <ID> <src ...|--all-new> [--changed] [--relink OLD NEW]`; resolve UNMATCHED entries with `alias`/`ignore`/`add-row`
5. `render <ID>`

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

Only the transforms moved into `migrate/seed.py` (used by `seed-from-md`) carry over; the rest of the old scripts are superseded.

## Data files

- `families/<ID>.json` — one family: config (`id`, `file`, `title`, `wiki_page`, `readme_label`, `trailing_newline`, `sections`, `section_rules`, `aliases`, `ignore`) and `rows` (data of record — each row has `src`, and wiki-sourced rows also have `src_raw`/`auto`).
- `families/_order.json` — family id render/README order (optional; missing falls back to sorted ids).
- `data/images.json` — SKU → photo record (`file`, `extra`, `url`, `src`, `page`, `verified`).
- `data/bad_md5.txt` — rejected-image md5 blacklist, one per line.
- `data/dealers.json` — dealer-name normalization (`aliases`) and dealer name → sitemap domain (`domains`).
