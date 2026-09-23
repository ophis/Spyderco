---
name: spyderco-catalog
description: Use when adding a new Spyderco model family (SKU line such as C41) to Catalogs/, updating a family for new releases, or finding/fixing product photos.
---

`spy` below means `tools/.venv/bin/python tools/spy.py`, run from the repo root. `tools/README.md` is the command reference (check `spy <cmd> --help` for syntax); `REVIEW.md` §1 (model data) and §2 (photos) are the rules. The tool does the mechanics; you do the judgment: SKU spellings, dealers, sections, and every photo decision.

## Workflow A: new family

1. `spy init <ID> --file "<ID> <Name>" --title … --wiki-page … --sections …` (add `--rule` for lightweight/generation sections).
2. `spy fetch wiki <ID>`, `spy fetch official`, `spy fetch forum`.
3. `spy update <ID> --offline`, then review every NEW row in `tools/cache/proposals/<ID>.json` against REVIEW.md §1:
   - SKU spelling: spyderco.com / retailer spelling wins. Record every other spelling with `spy alias <ID> <from> <to>`. The wiki often drops the `P` and has typos.
   - Dealer names normalized; "exclusive" with no dealer is a gap to research.
   - Section per row (lightweight variants in their own section).
   - Forum list: the tool cross-checks forum lines only by SKU. Read `tools/cache/forum.txt` for lines naming this family by model name alone and add missing ones with `spy add-row`.
4. `spy accept <ID> --all-new`, then `spy render <ID>`.
5. Workflow C for every row, then Finish.

## Workflow B: update family

1. `spy fetch wiki <ID>` (plus `fetch official` / `fetch forum`), then `spy update <ID> --offline`.
2. Judge each proposal entry on its own; accept only what you have checked:
   - NEW: as Workflow A step 3, then `spy accept <ID> <src …>`.
   - CHANGED: read the field diff; accept a real wiki update with `spy accept <ID> <src> --changed` (hand-corrected fields are preserved).
   - RELINK: confirm it is the same knife under a new wiki key, then `spy accept <ID> --relink OLD NEW`.
   - GONE: report only; the row stays. Find out why the wiki record vanished before moving on.
   - UNMATCHED: resolve with `alias`, `ignore`, or `add-row`.
3. Read the forum list for model-name-only lines (Workflow A step 3).
4. `spy render <ID>`, Workflow C for new rows, then Finish.

## Workflow C: photo hunt

Source order: spyderco.com `_Both` image → the exclusive dealer's own site → other retailers → any photo of the exact variant online.

1. `spy photos candidates <ID>`. For SKUs with no candidate, find pages with WebSearch (parallel agents for many SKUs), in source order, and add them: `spy photos candidates <ID> --add SKU=URL`.
2. `spy photos fetch <ID>`, then `spy photos sheet <ID> --review`.
3. Read every contact sheet image by eye. A page showing the SKU is necessary, not sufficient: retailers list satin and black-blade pages side by side, and a related-product thumbnail can be the one picked. Match the exact variant: handle, steel stamp, blade finish (satin vs black), edge, blade shape.
4. `spy photos reject <file>` for logos, banners, placeholders, promo images with text, or the wrong variant. `spy photos accept <ID> <SKU> <file>` for exact matches.
5. Preference: one open+folded composite → open main plus a folded clip-side extra → best photo of the exact variant. White background preferred; lower quality beats no photo. For an open-only main: `spy photos gallery <ID> --sku <SKU>`, `spy photos sheet <ID> --gallery`, and accept the folded shot that shows the clip side with `--extra`.
6. Keep accurate photos. To replace a wrong main photo use `spy photos accept … --replace`; it writes a new filename so viewers don't show a cached copy. All image changes go through the tool.

## Finish

1. Walk the REVIEW.md checklist for the touched family.
2. `spy verify` exits 0.
3. Round-trip: `git add` your changes, `spy render --all`, then `git diff --exit-code -- Catalogs/ README.md` exits 0.
4. Commit; the message ends with the repo's attribution lines.

Use repo-relative paths in commands and files.
